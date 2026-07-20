"""
KAVACH — What-if Sandbox
========================

The Q&A weapon. A juror asks "what if they *had* isolated the gas main?" or
"what if a second CO channel was rising too?" — and instead of hand-waving,
KAVACH re-runs the compound engine on a modified copy of the twin and shows the
risk score move, live, with the rules that changed.

How it works
------------
Each intervention edits a **deep copy** of the scenario definition (never the
cached original), then a fresh ``Timeline → Signals → CompoundRiskEngine`` is
built on that copy. Because signals (trend, drift, corroboration) are recomputed
from the modified series, a change like "open valve V-707" genuinely propagates
through the physics, not just a cosmetic score nudge. The base engine is
evaluated from cache, so the response is always a clean before/after diff.

Deterministic: the same interventions always yield the same numbers. No LLM in
the loop.

Supported ops (see ``options_for``):
  * ``isolate_gas_main``   — apply positive isolation to a confined-entry permit
  * ``multipoint_gas_test``— upgrade a single-point gas test to representative
  * ``cancel_permit``      — withdraw a permit (e.g. the hot-work permit)
  * ``remove_ramps``       — undo a scripted trajectory (e.g. the V-707 throttle)
  * ``raise_sensor``       — inject a rising trajectory on a sensor
  * ``add_permit``         — introduce a new permit (e.g. extra hot work)
"""

from __future__ import annotations

import copy
from typing import Any

from app.risk.compound import CompoundRiskEngine
from app.risk.regulatory import citations_for_rules
from app.risk.signals import ScenarioSignals
from app.simulator.engine import Timeline, scenario_def

# Presets the UI renders as one-click levers. Kept per-scenario and explicit so
# the demo is scripted and un-surprising.
_OPTIONS: dict[str, list[dict]] = {
    "vizag_replay": [
        {"id": "isolate", "label": "Isolate the gas main (V-707) for CSE-2093",
         "kind": "mitigation", "recommended_t": 270,
         "note": "Positive isolation the entry permit omitted — should clear R3.",
         "interventions": [{"op": "isolate_gas_main", "permit": "CSE-2093"}]},
        {"id": "multipoint", "label": "Use a representative (multi-point) gas test",
         "kind": "mitigation", "recommended_t": 270,
         "note": "Test the chamber rear/riser side, not just the entrance — should clear R5.",
         "interventions": [{"op": "multipoint_gas_test", "permit": "CSE-2093"}]},
        {"id": "no_hotwork", "label": "Never issue the 08:30 hot-work permit",
         "kind": "mitigation", "recommended_t": 400,
         "note": "Withdraw HW-2101 — should clear R2 after 08:30.",
         "interventions": [{"op": "cancel_permit", "permit": "HW-2101"}]},
        {"id": "no_throttle", "label": "Don't throttle valve V-707 at 09:30",
         "kind": "mitigation", "recommended_t": 470,
         "note": "Undo the back-pressure driver — should clear R6 after 09:30.",
         "interventions": [{"op": "remove_ramps", "sensor": "ZI-GM-707"}]},
        {"id": "corroborate", "label": "Inject a 2nd rising CO channel (GD-CO4-204)",
         "kind": "escalation", "recommended_t": 300,
         "note": "A second basement channel rising — boosts corroboration (R7) and confidence.",
         "interventions": [{"op": "raise_sensor", "sensor": "GD-CO4-204",
                            "t0": 270, "t1": 330, "to": 40}]},
    ],
    "normal_day": [
        {"id": "real_leak", "label": "Inject a real (un-explained) pressure rise",
         "kind": "escalation", "recommended_t": 300,
         "note": "Raise PT-GM-104 with no work-order cover — KAVACH should now react, not suppress.",
         "interventions": [{"op": "raise_sensor", "sensor": "PT-GM-104",
                            "t0": 240, "t1": 320, "to": 9.4}]},
        {"id": "add_entry", "label": "Add a confined-space entry with no isolation",
         "kind": "escalation", "recommended_t": 320,
         "note": "Introduce an unsafe entry over the injected rise.",
         "interventions": [
             {"op": "raise_sensor", "sensor": "PT-GM-104", "t0": 240, "t1": 320, "to": 9.4},
             {"op": "add_permit", "permit": {
                 "id": "CSE-9001", "type": "Confined Space Entry", "zone": "cob4_basement",
                 "title": "What-if entry (sandbox)", "from": 300, "to": 480,
                 "crew": ["sandbox-1", "sandbox-2"],
                 "gas_test": {"t": 295, "ref": "GT-SBX", "result": "PASS",
                              "detail": "Single-point test at entrance only."},
                 "isolations": ["Gas-main isolation: NOT applied (sandbox)"]}}],
         },
    ],
}


def options_for(scenario_id: str) -> dict[str, Any]:
    return {"scenario": scenario_id, "options": _OPTIONS.get(scenario_id, [])}


def _apply(sc: dict, interventions: list[dict]) -> list[dict]:
    """Mutate the (already-copied) scenario def; return the applied log."""
    applied: list[dict] = []
    sc.setdefault("ramps", [])
    sc.setdefault("permits", [])
    for iv in interventions:
        op = iv.get("op")
        if op == "isolate_gas_main":
            pid = iv.get("permit")
            for p in sc["permits"]:
                if p["id"] == pid:
                    p["isolations"] = [i for i in p.get("isolations", [])
                                       if "gas-main" not in i.lower()
                                       and "gas main" not in i.lower()]
                    p["isolations"].append(
                        "Gas-main isolation: applied (positive isolation — V-707 "
                        "closed & blinded, riser leg depressurised)")
                    applied.append({"op": op, "permit": pid})
        elif op == "multipoint_gas_test":
            pid = iv.get("permit")
            for p in sc["permits"]:
                if p["id"] == pid and p.get("gas_test"):
                    p["gas_test"]["detail"] = (
                        "Multi-point test: chamber entrance, rear and riser side "
                        "all tested; CO within limits.")
                    applied.append({"op": op, "permit": pid})
        elif op == "cancel_permit":
            pid = iv.get("permit")
            before = len(sc["permits"])
            sc["permits"] = [p for p in sc["permits"] if p["id"] != pid]
            if len(sc["permits"]) != before:
                applied.append({"op": op, "permit": pid})
        elif op == "remove_ramps":
            sid = iv.get("sensor")
            sc["ramps"] = [r for r in sc["ramps"] if r["sensor"] != sid]
            applied.append({"op": op, "sensor": sid})
        elif op == "raise_sensor":
            sid = iv["sensor"]
            t0 = int(iv.get("t0", 0))
            t1 = int(iv.get("t1", t0 + 30))
            to = float(iv["to"])
            sc["ramps"].append({"sensor": sid, "t0": t0, "t1": t1, "to": to})
            applied.append({"op": op, "sensor": sid, "to": to, "t0": t0, "t1": t1})
        elif op == "add_permit":
            sc["permits"].append(copy.deepcopy(iv["permit"]))
            applied.append({"op": op, "permit": iv["permit"]["id"]})
    return applied


def _focus_zone(scenario_id: str, base: CompoundRiskEngine, t: int) -> str:
    windows = base.tl.ground_truth.get("hazard_windows") or []
    if windows and windows[0].get("zone"):
        return windows[0]["zone"]
    # else the highest-scoring zone at t
    return max(base.zone_ids, key=lambda z: base.zone_score[z][t])


def _snapshot(eng: CompoundRiskEngine, zone: str, t: int) -> dict:
    ev = eng.contribs_at(zone, t)
    snap = eng.state_at(t)
    return {
        "top_band": snap["top_band"],
        "top_band_name": snap["top_band_name"],
        "focus_zone": zone,
        "focus_zone_name": next((z["name"] for z in eng.tl.plant["zones"]
                                 if z["id"] == zone), zone),
        "score": ev["score"],
        "band": eng.zone_band[zone][t],
        "band_name": {0: "normal", 1: "advisory", 2: "alert",
                      3: "critical"}[eng.zone_band[zone][t]],
        "rule_ids": ev["rule_ids"],
        "rules": ev["rules"],
        "zones": {z: {"score": eng.zone_score[z][t],
                      "band": eng.zone_band[z][t]} for z in eng.zone_ids},
    }


def evaluate(scenario_id: str, t: int, interventions: list[dict],
             base_engine: CompoundRiskEngine) -> dict[str, Any]:
    """Run the sandbox: base (cached) vs. modified (fresh) at minute t."""
    from app.simulator.engine import get_timeline
    tl = get_timeline(scenario_id)
    t = max(0, min(tl.duration, int(t)))
    zone = _focus_zone(scenario_id, base_engine, t)

    # --- build the modified twin on a deep copy of the scenario def --------
    sc = copy.deepcopy(scenario_def(scenario_id))
    applied = _apply(sc, interventions or [])
    tl2 = Timeline(scenario_id, sc_def=sc)
    sig2 = ScenarioSignals(scenario_id, tl=tl2)
    eng2 = CompoundRiskEngine(scenario_id, tl=tl2, sig=sig2)

    base_snap = _snapshot(base_engine, zone, t)
    mod_snap = _snapshot(eng2, zone, t)

    base_rules = set(base_snap["rule_ids"])
    mod_rules = set(mod_snap["rule_ids"])
    delta = {
        "score_delta": round(mod_snap["score"] - base_snap["score"], 1),
        "band_from": base_snap["band_name"],
        "band_to": mod_snap["band_name"],
        "rules_added": sorted(mod_rules - base_rules),
        "rules_removed": sorted(base_rules - mod_rules),
    }
    narrative = _narrate(base_snap, mod_snap, delta, applied)
    return {
        "scenario": scenario_id,
        "t": t,
        "clock": tl.clock(t),
        "interventions": applied,
        "base": base_snap,
        "modified": mod_snap,
        "delta": delta,
        "regulatory_basis": citations_for_rules(mod_snap["rule_ids"]),
        "narrative": narrative,
    }


def _narrate(base: dict, mod: dict, delta: dict, applied: list[dict]) -> str:
    if not applied:
        return (f"No change: {base['focus_zone_name']} stays "
                f"{base['band_name'].upper()} at {base['score']:.0f}/100.")
    direction = ("falls" if delta["score_delta"] < 0
                 else "rises" if delta["score_delta"] > 0 else "is unchanged")
    parts = [f"{base['focus_zone_name']} score {direction} "
             f"{base['score']:.0f} → {mod['score']:.0f}/100 "
             f"({base['band_name'].upper()} → {mod['band_name'].upper()})."]
    if delta["rules_removed"]:
        parts.append("Cleared: " + ", ".join(delta["rules_removed"]) + ".")
    if delta["rules_added"]:
        parts.append("New: " + ", ".join(delta["rules_added"]) + ".")
    return " ".join(parts)
