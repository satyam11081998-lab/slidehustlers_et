"""
KAVACH — Emergency Response Orchestrator
========================================

Detection is only half of "zero-harm". The orchestrator is what a control room
would actually *do* the moment KAVACH declares a compound-critical condition —
expressed as a deterministic state machine, not an LLM guessing procedures.

On the first CRITICAL alert it produces one ordered, citation-backed action
plan:

  RAISE → SUSPEND permits → ISOLATE the gas main → NOTIFY roles →
  EVACUATE by connectivity → RE-TEST / MONITOR before any re-entry.

Every action carries a ``regulatory_basis`` (from ``app.risk.regulatory``) and
an evidence snapshot, and the plan states the **counterfactual**: in the
recorded composite the incident occurred at 10:30; had this plan been actioned
at the 06:30 alert, the crew would have been withdrawn 3h 40m before the
incident window's end — and the 08:30 hot-work permit and 09:30 valve throttle
that deepened the hazard would never have been issued.

Deterministic: same scenario → same plan, every run. No clock, no network.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.risk.compound import CompoundRiskEngine, get_risk_engine
from app.risk.regulatory import citations_for_actions
from app.simulator.engine import Timeline, get_timeline

# Static roles the plan always engages, beyond the live shift supervisor.
STANDING_ROLES = [
    {"role": "Safety Officer", "why": "authorise stop-work and permit suspension"},
    {"role": "Control Room", "why": "network isolation, alarm broadcast, logging"},
    {"role": "Fire & Gas Rescue", "why": "standby for confined-space withdrawal"},
]


class Orchestrator:
    """Builds the emergency-response plan for one scenario's first critical."""

    def __init__(self, scenario_id: str, tl: Timeline | None = None,
                 eng: CompoundRiskEngine | None = None):
        self.scenario = scenario_id
        self.tl = tl or get_timeline(scenario_id)
        self.eng = eng or get_risk_engine(scenario_id)
        self.trigger = self.eng.first_alert(min_band=3)  # first CRITICAL 'new'
        self.plan = self._build()

    # ------------------------------------------------------------------ helpers
    def _zone_name(self, zid: str) -> str:
        return next((z["name"] for z in self.tl.plant["zones"] if z["id"] == zid), zid)

    def _zone_kind(self, zid: str) -> str:
        return next((z.get("kind", "") for z in self.tl.plant["zones"]
                     if z["id"] == zid), "")

    def _supervisor_at(self, t: int) -> dict:
        s = next((s for s in self.tl.shifts if s["from"] <= t < s["to"]), None)
        if not s:
            return {"role": "Shift Supervisor", "name": None, "shift": None}
        return {"role": "Shift Supervisor", "name": s.get("supervisor"),
                "shift": s.get("label") or s.get("name")}

    def _permits_in_scope(self, zone: str, t: int) -> list[dict]:
        scope = {zone, *self.eng.adj.get(zone, [])}
        out = []
        for p in self.tl.permits:
            if p["from"] <= t < p["to"] and p["zone"] in scope:
                out.append({"id": p["id"], "type": p["type"], "zone": p["zone"],
                            "crew": len(p.get("crew", []))})
        return out

    def _future_escalators(self, zone: str, t: int, until: int) -> list[dict]:
        """Permits / valve ops that WOULD be issued after the trigger and that a
        respected suspension would have prevented — the downstream harm avoided."""
        scope = {zone, *self.eng.adj.get(zone, [])}
        out = []
        for p in self.tl.permits:
            if t < p["from"] <= until and p["zone"] in scope:
                out.append({"kind": "permit", "id": p["id"], "type": p["type"],
                            "zone": p["zone"], "t": p["from"],
                            "clock": self.tl.clock(p["from"])})
        for w in self.tl.work_orders:
            st = w.get("started")
            if st is not None and t < st <= until and "throttle" in \
                    f"{w.get('title','')} {w.get('notes','')}".lower():
                out.append({"kind": "work_order", "id": w["id"],
                            "type": w.get("kind", "work order"),
                            "zone": w.get("zone"), "t": st,
                            "clock": self.tl.clock(st)})
        out.sort(key=lambda e: e["t"])
        return out

    # ------------------------------------------------------------------ build
    def _build(self) -> dict[str, Any]:
        gt = self.tl.ground_truth
        incident = gt.get("incident_at")
        if not self.trigger:
            return {
                "scenario": self.scenario,
                "triggered": False,
                "reason": "No compound-critical condition arose — no emergency "
                          "response required. (This is the correct outcome on a "
                          "benign shift.)",
                "actions": [],
                "evacuation": None,
                "counterfactual": None,
            }

        a = self.trigger
        t, zone = a["t"], a["zone"]
        clock = a["clock"]
        rule_ids = [r["id"] for r in a["rules"]]

        # --- evacuation set from the connectivity graph --------------------
        neighbours = self.eng.adj.get(zone, [])
        evac_immediate = [zone] + [z for z in neighbours
                                   if self._zone_kind(z) == "confined_space"]
        evac_precaution = [z for z in neighbours if z not in evac_immediate]
        evacuation = {
            "immediate": [{"id": z, "name": self._zone_name(z),
                           "kind": self._zone_kind(z)} for z in evac_immediate],
            "precautionary": [{"id": z, "name": self._zone_name(z),
                               "kind": self._zone_kind(z)} for z in evac_precaution],
            "muster": "Designated muster point upwind of the Battery-4 complex",
            "basis": citations_for_actions(["evacuate"]),
        }

        permits = self._permits_in_scope(zone, t)
        supervisor = self._supervisor_at(t)
        roles = [supervisor] + STANDING_ROLES

        def act(seq: int, typ: str, sla: str, title: str, detail: str,
                extra: dict | None = None) -> dict:
            d = {
                "seq": seq,
                "type": typ,
                "sla": sla,
                "title": title,
                "detail": detail,
                "regulatory_basis": citations_for_actions([typ]),
            }
            if extra:
                d.update(extra)
            return d

        actions = [
            act(1, "raise", "T+0",
                f"Declare COMPOUND-CRITICAL — {self._zone_name(zone)}",
                f"KAVACH score {a['score']:.0f}/100 at {clock} from rules "
                f"[{', '.join(rule_ids)}] (confidence {a['confidence']}). "
                "Broadcast control-room alarm; freeze the area.",
                {"evidence": {"rules": a["rules"], "signals": a["signals"],
                              "permits": a["permits"],
                              "confidence": a["confidence"], "score": a["score"]}}),
            act(2, "suspend_permit", "T+0",
                "STOP WORK — suspend active permits in the hazard network",
                ("Suspend: " + ", ".join(f"{p['id']} ({p['type']}, "
                 f"crew {p['crew']})" for p in permits) if permits
                 else "No active permits to suspend.")
                + " Block issuance of any new hot-work / entry permits in "
                f"{self._zone_name(zone)} and connected zones until cleared.",
                {"permits": permits}),
            act(3, "isolate_gas_main", "T+2 min",
                "Positively isolate the Battery-4 riser",
                "Close AND blind isolation valve V-707 (ZI-GM-707) at the riser; "
                "do NOT merely throttle — throttling raises back-pressure on the "
                "PT-GM-104 leg. Reduce the isolated section to atmospheric "
                "pressure before any intervention."),
            act(4, "notify", "T+2 min",
                "Notify and mobilise response roles",
                "Escalate to: " + ", ".join(
                    f"{r['role']}" + (f" ({r['name']})" if r.get("name") else "")
                    for r in roles) + ".",
                {"roles": roles}),
            act(5, "evacuate", "T+5 min",
                "Evacuate confined space; clear connected zones",
                f"Withdraw and account for the crew in {self._zone_name(zone)} "
                "(confined space, no re-entry). Clear connected zones to the "
                "muster point and confirm headcount.",
                {"evacuation_zones": [z["id"] for z in evacuation["immediate"]]
                 + [z["id"] for z in evacuation["precautionary"]]}),
            act(6, "re_test", "before any re-entry",
                "Re-test the chamber rear and riser side",
                "The entry gas test was single-point at the chamber entrance. "
                "Re-test the rear/riser side with a representative, competent-"
                "person test before considering re-entry."),
            act(7, "monitor", "continuous",
                "Continuous CH4/CO monitoring until the trend reverses",
                "Establish continuous monitoring on the Battery-4 network and "
                "hold all work until pressure and CO trends reverse and isolation "
                "is verified positive."),
        ]

        until = incident if incident is not None else self.tl.duration
        prevented = self._future_escalators(zone, t, until)

        counterfactual = {
            "recorded_incident_t": incident,
            "recorded_incident_clock": self.tl.clock(incident) if incident is not None else None,
            "kavach_action_t": t,
            "kavach_action_clock": clock,
            "minutes_earlier": (incident - t) if incident is not None else None,
            "hours_earlier": round((incident - t) / 60, 2) if incident is not None else None,
            "prevented_downstream": prevented,
            "statement": (
                f"In the recorded composite the incident occurred at "
                f"{self.tl.clock(incident)}. Actioning this plan at the "
                f"{clock} compound alert would have withdrawn the crew "
                f"{incident - t} minutes ({(incident - t) / 60:.1f} h) earlier, "
                f"and pre-empted {len(prevented)} downstream escalation(s) that "
                "deepened the hazard."
            ) if incident is not None else "",
        }

        return {
            "scenario": self.scenario,
            "triggered": True,
            "trigger": {"t": t, "clock": clock, "zone": zone,
                        "zone_name": self._zone_name(zone), "band": a["band"],
                        "band_name": a["band_name"], "score": a["score"],
                        "rules": rule_ids, "confidence": a["confidence"]},
            "actions": actions,
            "roles": roles,
            "evacuation": evacuation,
            "suspended_permits": permits,
            "counterfactual": counterfactual,
        }

    # ------------------------------------------------------------------ public
    def state_at(self, t: int) -> dict[str, Any]:
        """Live orchestrator status for the UI: armed before the trigger,
        active from the trigger minute onward."""
        if not self.plan["triggered"]:
            return {"scenario": self.scenario, "status": "clear",
                    "triggered": False, "t": t, "clock": self.tl.clock(t)}
        trig_t = self.plan["trigger"]["t"]
        status = "active" if t >= trig_t else "armed"
        return {
            "scenario": self.scenario,
            "t": t,
            "clock": self.tl.clock(t),
            "status": status,
            "triggered": t >= trig_t,
            "trigger_t": trig_t,
            "actions_engaged": len(self.plan["actions"]) if t >= trig_t else 0,
        }

    def as_dict(self) -> dict[str, Any]:
        return self.plan


@lru_cache(maxsize=8)
def get_orchestrator(scenario_id: str) -> Orchestrator:
    return Orchestrator(scenario_id)
