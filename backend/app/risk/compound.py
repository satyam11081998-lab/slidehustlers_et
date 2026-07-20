"""
KAVACH — Compound Risk Engine
=============================

The heart of the system. Where the baseline watches each sensor alone, the
CompoundRiskEngine fuses four things a single sensor can never see:

  1. **Signal shape**   — trends, sub-threshold drift, cross-channel movement
                          (from ``app.risk.signals``).
  2. **Work context**   — active permits, work orders, shift handovers.
  3. **Plant topology**  — which zones are physically connected (a pressure
                          rise on the gas main matters to whoever is inside a
                          connected confined space).
  4. **Institutional memory** — a single-point gas test, a handover that
                          omitted a drift, a calibration in progress.

It expresses domain knowledge as eight rules (R1–R8) that each contribute,
with full evidence, to a per-zone risk score (0–100). Scores cross advisory
/ alert / critical bands *with hysteresis* so alerts don't chatter. Every
alert carries the exact rules, signals, permits and events behind it — so
when a juror asks "why?", the system answers.

Determinism: the whole horizon is evaluated once and cached. No randomness,
no clock, no network. Given a scenario, the alert at 06:30 is always at
06:30.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app.simulator.engine import Timeline, get_timeline
from app.risk.signals import ScenarioSignals, get_signals

# --- band model -------------------------------------------------------------
BAND_NAMES = {0: "normal", 1: "advisory", 2: "alert", 3: "critical"}
ENTER = [(1, 40), (2, 60), (3, 80)]      # raise to highest band whose enter-th is met
EXIT = {1: 30, 2: 50, 3: 70}             # must fall below this to leave a band

# Rules whose *appearance* while already elevated counts as an escalation.
MATERIAL_RULES = {"R1", "R2", "R3", "R6"}

RULE_LABELS = {
    "R1": "Gas trend in occupied confined space",
    "R2": "Hot work adjacent to rising gas",
    "R3": "Confined entry without gas-main isolation",
    "R4": "Shift-handover blindspot",
    "R5": "Single-point gas test",
    "R6": "Valve throttling driving back-pressure",
    "R7": "Multi-channel corroboration",
    "R8": "Calibration context — suppressed",
}

_SENSOR_RE = re.compile(r"[A-Z]{2,3}-[A-Z0-9]{2,4}-\d{3}")


def _sensors_in_text(text: str) -> set[str]:
    return set(_SENSOR_RE.findall(text or ""))


class CompoundRiskEngine:
    """Context-aware compound-risk evaluation for one scenario."""

    def __init__(self, scenario_id: str, tl: Timeline | None = None,
                 sig: ScenarioSignals | None = None):
        # ``tl`` / ``sig`` let the what-if sandbox evaluate a modified twin
        # without polluting the cached base engine.
        self.scenario = scenario_id
        self.tl: Timeline = tl or get_timeline(scenario_id)
        self.sig: ScenarioSignals = sig or get_signals(scenario_id)
        self.duration = self.tl.duration

        self.adj = self._build_adjacency()
        self.ack = self._ack_times()          # sensor -> minute first acknowledged
        self.zone_ids = [z["id"] for z in self.tl.plant["zones"]]
        self.zone_kind = {z["id"]: z.get("kind", "") for z in self.tl.plant["zones"]}
        self.zone_name = {z["id"]: z.get("name", "") for z in self.tl.plant["zones"]}

        # horizon results (filled by _run)
        self.zone_score: dict[str, list[float]] = {}
        self.zone_band: dict[str, list[int]] = {}
        self.alerts: list[dict] = []
        self.suppressions: list[dict] = []
        self.rule_ticks: dict[str, int] = {r: 0 for r in RULE_LABELS}
        self._supp_seen: set[tuple] = set()
        self._run()

    # ------------------------------------------------------------ topology etc.

    def _build_adjacency(self) -> dict[str, list[str]]:
        real = {z["id"] for z in self.tl.plant["zones"]}
        adj: dict[str, set[str]] = {zid: set() for zid in real}
        for z in self.tl.plant["zones"]:
            zid = z["id"]
            for c in z.get("connections", []):
                # the layout names a 'vent' pseudo-node linking Platform P2 to
                # the Battery-4 basement; normalise it to the real zone.
                c = "cob4_basement" if c == "cob4_basement_vent" else c
                if c in real:
                    adj[zid].add(c)
                    adj[c].add(zid)          # connectivity is symmetric
        return {k: sorted(v) for k, v in adj.items()}

    def _ack_times(self) -> dict[str, int]:
        """Minute at which each sensor's abnormality was first acknowledged /
        explained away by an operator (from the scenario event log)."""
        ack: dict[str, int] = {}
        for e in self.tl.events:
            sid = e.get("sensor")
            if not sid:
                continue
            blob = f"{e.get('title','')} {e.get('detail','')}".lower()
            # Only a genuine acknowledgement of the *ongoing* condition counts.
            # A transient "cleared / no action" log (e.g. a momentary spike) is
            # NOT an acknowledgement of the underlying sub-threshold drift —
            # treating it as one would hide exactly the handover blindspot R4
            # exists to catch.
            if any(k in blob for k in ("acknowledg", "known drift")):
                ack.setdefault(sid, e["t"])
        # A handover that actually carries the condition forward is an
        # acknowledgement too — the blindspot R4 punishes is the *silent* one.
        # Guarded against negated phrasing ("not mentioned", "does not mention"),
        # which is how the incident scenario records an omitted handover.
        for e in self.tl.events:
            if e.get("type") != "shift_change":
                continue
            blob = f"{e.get('title','')} {e.get('detail','')}".lower()
            if any(n in blob for n in ("not mentioned", "does not mention",
                                       "not communicated", "omit")):
                continue
            if any(k in blob for k in ("records the", "recorded", "communicated",
                                       "carried forward", "handed over")):
                for sid in self.tl.sensors_meta:
                    ack.setdefault(sid, e["t"])
        return ack

    # ------------------------------------------------------------ context @ t

    def _active_permits(self, t: int) -> list[dict]:
        return [p for p in self.tl.permits if p["from"] <= t < p["to"]]

    def _active_wos(self, t: int) -> list[dict]:
        out = []
        for w in self.tl.work_orders:
            started = w.get("started", 10**9)
            completed = w.get("completed")
            if started <= t and (completed is None or t < completed):
                out.append(w)
        return out

    def _handover_active(self, t: int) -> dict | None:
        for s in self.tl.shifts:
            if s["from"] > 0 and s["from"] - 15 <= t <= s["from"] + 60:
                return s
        return None

    def _unack_drift(self, t: int) -> str | None:
        """A gas-main pressure sensor drifting sub-threshold that no operator
        has yet acknowledged — the essence of a handover blindspot."""
        for sid, m in self.tl.sensors_meta.items():
            if m["kind"] != "pressure":
                continue
            if self.sig.is_drifting(sid, t):
                ackt = self.ack.get(sid)
                if ackt is None or t < ackt:
                    return sid
        return None

    def _calibration_wo_for(self, sid: str, t: int) -> dict | None:
        for w in self._active_wos(t):
            blob = f"{w.get('title','')} {w.get('notes','')}"
            if "calibration" in blob.lower() and (
                sid in blob or w.get("zone") == self.tl.sensors_meta[sid]["zone"]
                and sid in _sensors_in_text(blob)
            ):
                return w
        return None

    def _gas_scan_zones(self, zone: str) -> list[str]:
        """Zones to inspect for gas-main abnormality, from `zone`.

        Depth 1 = every directly-connected zone. Depth 2 = only zones that are
        part of the gas network itself, which is how a riser in a battery
        basement is exposed to a main it does not physically touch. Bounded at
        two hops so the whole plant does not become 'connected to everything'.
        """
        seen = {zone} | set(self.adj.get(zone, []))
        for n in list(seen):
            for m in self.adj.get(n, []):
                if m in seen:
                    continue
                if (self.zone_kind.get(m) == "gas_network"
                        or "gas main" in (self.zone_name.get(m, "").lower())):
                    seen.add(m)
        return sorted(seen)

    def _barriers_intact(self, cse: dict) -> bool:
        """True when the entry is being run the way the standard requires.

        Isolation applied, a representative (multi-point) gas test, and
        continuous monitoring. When all three hold and no reading has actually
        breached a warning limit, a rising trend is information, not an alarm —
        crediting intact barriers is the same logic the what-if console
        demonstrates in reverse.
        """
        if not self._gas_main_isolated(cse):
            return False
        if self._single_point_test(cse):
            return False
        gt = cse.get("gas_test") or {}
        return "continuous" in (gt.get("detail") or "").lower()

    @staticmethod
    def _gas_main_isolated(p: dict) -> bool:
        for iso in p.get("isolations", []):
            s = iso.lower()
            if ("gas-main" in s or "gas main" in s) and "not applied" not in s \
                    and any(k in s for k in ("isolat", "purg", "applied")):
                return True
        return False

    @staticmethod
    def _single_point_test(p: dict) -> bool:
        gt = p.get("gas_test")
        if not gt:
            return True  # a confined entry with no gas test is worse still
        d = f"{gt.get('detail','')} {gt.get('result','')}".lower()
        if "multi-point" in d or "multi point" in d:
            return False
        return any(k in d for k in ("single-point", "single point",
                                    "not tested", "no test at"))

    # ------------------------------------------------------------ suppression

    def _suppressed_pressure(self, zone: str, t: int) -> tuple[list[str], list[dict]]:
        """Return (abnormal_pressure_sensors, suppression_notes) for a zone,
        applying R8: a sensor under an active calibration work order is
        contextualised away instead of driving risk."""
        kept: list[str] = []
        notes: list[dict] = []
        for sid in self.sig.pressure_abnormal(zone, t):
            wo = self._calibration_wo_for(sid, t)
            if wo:
                notes.append({
                    "sensor": sid,
                    "wo": wo["id"],
                    "reason": f"{sid} elevated but {wo['id']} calibration active",
                })
            else:
                kept.append(sid)
        return kept, notes

    # ------------------------------------------------------------ per-zone eval

    def contribs_at(self, zone: str, t: int) -> dict[str, Any]:
        """Recompute a zone's contributions & evidence at minute t (drill-down).
        Pure function of the twin — safe to call for any zone / time."""
        t = max(0, min(self.duration, int(t)))
        sig = self.sig
        permits = self._active_permits(t)
        cse = next((p for p in permits
                    if "Confined" in p["type"] and p["zone"] == zone), None)

        rising_here = sig.rising_gas_channels(zone, t)
        gas_elevated = sig.gas_elevated(zone, t)

        # Abnormal gas-main pressure anywhere the gas network can reach this zone.
        #
        # This used to scan only directly-connected zones, which silently made the
        # rule depend on the demo zone's topology: cob4_basement neighbours the gas
        # main, cob3_basement does not, so an identical hazard in Battery 3 was
        # invisible. Held-out testing caught it (4 missed hazards, all in
        # cob3_basement). Gas travels through the connected network, not one hop,
        # so reachability is what matters.
        abn: list[str] = []
        supp: list[dict] = []
        for z in self._gas_scan_zones(zone):
            kept, notes = self._suppressed_pressure(z, t)
            abn += kept
            supp += notes

        contribs: list[dict] = []

        def add(rid: str, weight: float, detail: str, sev: str) -> None:
            contribs.append({"id": rid, "label": RULE_LABELS[rid],
                             "severity": sev, "weight": weight, "detail": detail})

        if cse:
            occupied = f"crew of {len(cse.get('crew', []))}"
            # R1 — gas building in / around an occupied confined space
            if rising_here or abn:
                why = []
                if rising_here:
                    why.append("rising " + ", ".join(rising_here))
                if abn:
                    why.append("gas-main drift on " + ", ".join(abn))
                # Credit intact barriers. With isolation applied, a representative
                # multi-point test and continuous monitoring, and nothing yet at a
                # warning limit, a rising trend is advisory — it must not reach the
                # alert band on its own. Held-out testing showed the undamped rule
                # alerting on CO at 13 ppm against a warn limit of 30, with the crew
                # fully protected: the definition of crying wolf.
                damped = self._barriers_intact(cse) and not gas_elevated
                add("R1", 20 if damped else 45,
                    f"{cse['id']} active ({occupied}); " + "; ".join(why)
                    + (" — barriers verified in place, advisory only" if damped else ""),
                    "medium" if damped else "high")
            # R3 — entry without gas-main isolation while the network is abnormal
            if abn and not self._gas_main_isolated(cse):
                add("R3", 40,
                    f"{cse['id']} isolations omit gas-main; network abnormal "
                    f"({', '.join(abn)})", "high")
            # R5 — the gas test that cleared entry was single-point
            if self._single_point_test(cse) and (rising_here or abn):
                add("R5", 15,
                    f"{cse['id']} cleared on a single-point gas test; "
                    "zone trend now rising", "escalator")
            # R2 — hot work next door to rising gas
            hw = [p for p in permits if "Hot" in p["type"]
                  and p["zone"] in self.adj.get(zone, [])]
            if hw and (rising_here or gas_elevated):
                add("R2", 30,
                    f"{hw[0]['id']} hot work in {hw[0]['zone']} adjacent to "
                    f"rising gas in {zone}", "high")
            # R6 — valve throttling driving back-pressure onto occupied space
            vb = sig.valve_backpressure(t)
            if vb:
                add("R6", 35,
                    "valve(s) throttled while ΔP/pressure rises: "
                    + ", ".join(f"{k}={v}" for k, v in vb["valves"].items()),
                    "high")
            # R4 — handover blindspot amplifies an already-live hazard
            if self._handover_active(t) and self._unack_drift(t) \
                    and any(c["id"] in ("R1", "R3") for c in contribs):
                add("R4", 10,
                    f"shift changeover with unacknowledged drift on "
                    f"{self._unack_drift(t)}", "escalator")
            # R7 — two or more channels corroborate
            if len(rising_here) >= 2:
                add("R7", 10,
                    f"{len(rising_here)} gas channels rising together in {zone}",
                    "confidence")
        else:
            # No entry in progress: KAVACH still *watches* a developing trend,
            # but stays below the alert band (this is the discipline that keeps
            # operators trusting it).
            if rising_here:
                add("R1", 25, f"rising {', '.join(rising_here)} — no active entry",
                    "watch")
            if abn:
                add("R3", 15,
                    f"sub-threshold gas-main drift on {', '.join(abn)}", "watch")
            hw = [p for p in permits if "Hot" in p["type"]
                  and p["zone"] in self.adj.get(zone, [])]
            if hw and gas_elevated:
                add("R2", 30,
                    f"{hw[0]['id']} hot work adjacent to elevated gas in {zone}",
                    "high")

        score = max(0.0, min(100.0, sum(c["weight"] for c in contribs)))
        signals_bundle = self._signals_bundle(zone, t, rising_here, abn)
        return {
            "zone": zone,
            "t": t,
            "clock": self.tl.clock(t),
            "score": round(score, 1),
            "rules": contribs,
            "rule_ids": [c["id"] for c in contribs],
            "signals": signals_bundle,
            "permits": [self._permit_brief(p) for p in permits if p["zone"] == zone
                        or p["zone"] in self.adj.get(zone, [])],
            "suppressions": supp,
        }

    def _signals_bundle(self, zone: str, t: int,
                        rising_here: list[str], abn: list[str]) -> dict:
        sig = self.sig
        return {
            "rising_gas": {s: {"value": round(sig.value(s, t), 1),
                               "slope_per_min": round(sig.slope[s][t], 3)}
                           for s in rising_here},
            "gas_main_pressure": {s: {"value": round(sig.value(s, t), 2),
                                      "drifting": sig.is_drifting(s, t)}
                                  for s in abn},
            "cross_channel_count": len(rising_here),
        }

    @staticmethod
    def _permit_brief(p: dict) -> dict:
        return {
            "id": p["id"], "type": p["type"], "zone": p["zone"],
            "crew": len(p.get("crew", [])),
            "gas_test": (p.get("gas_test") or {}).get("ref"),
            "isolations": p.get("isolations", []),
        }

    # ------------------------------------------------------------ horizon run

    def _run(self) -> None:
        for z in self.zone_ids:
            self.zone_score[z] = [0.0] * (self.duration + 1)
            self.zone_band[z] = [0] * (self.duration + 1)

        prev_band = {z: 0 for z in self.zone_ids}
        prev_rules: dict[str, set[str]] = {z: set() for z in self.zone_ids}

        for t in range(self.duration + 1):
            for z in self.zone_ids:
                ev = self.contribs_at(z, t)
                score = ev["score"]
                band = self._band(prev_band[z], score)
                self.zone_score[z][t] = score
                self.zone_band[z][t] = band

                # tally per-rule contributions only where they drove a real
                # alert (band >= alert), so the numbers reflect the reasoning
                # behind actual alerts, not low-level background watching.
                if band >= 2:
                    for rid in ev["rule_ids"]:
                        if rid in self.rule_ticks:
                            self.rule_ticks[rid] += 1
                for s in ev["suppressions"]:
                    key = (t, s["sensor"], s["wo"])
                    if key not in self._supp_seen:
                        self._supp_seen.add(key)
                        self.suppressions.append(
                            {"t": t, "clock": self.tl.clock(t), **s})

                rules_now = set(ev["rule_ids"])
                # primary alert: first entry into alert/critical
                if band >= 2 and prev_band[z] < 2:
                    self._emit(z, t, band, ev, kind="new")
                # escalation: a new material rule appears while already elevated
                elif band >= 2 and (rules_now - prev_rules[z]) & MATERIAL_RULES:
                    self._emit(z, t, band, ev, kind="escalation")

                prev_band[z] = band
                prev_rules[z] = rules_now

        # R8 is a suppression, not a scoring rule — count its activations here.
        self.rule_ticks["R8"] = len(self.suppressions)
        self.alerts.sort(key=lambda a: (a["t"], a["zone"]))

    def _emit(self, zone: str, t: int, band: int, ev: dict, kind: str) -> None:
        conf = {2: 0.72, 3: 0.85}.get(band, 0.6)
        if ev["signals"]["cross_channel_count"] >= 2:
            conf = min(0.98, conf + 0.08)
        conf = min(0.98, conf + 0.03 * max(0, len(ev["rule_ids"]) - 2))
        self.alerts.append({
            "id": f"KV-{zone}-{t}",
            "zone": zone,
            "zone_name": next((z["name"] for z in self.tl.plant["zones"]
                               if z["id"] == zone), zone),
            "t": t,
            "clock": self.tl.clock(t),
            "band": band,
            "band_name": BAND_NAMES[band],
            "kind": kind,
            "score": ev["score"],
            "confidence": round(conf, 2),
            "headline": self._headline(zone, band, ev),
            "rules": ev["rules"],
            "signals": ev["signals"],
            "permits": ev["permits"],
        })

    def _headline(self, zone: str, band: int, ev: dict) -> str:
        zn = next((z["name"] for z in self.tl.plant["zones"]
                   if z["id"] == zone), zone)
        ids = ", ".join(ev["rule_ids"])
        return (f"{BAND_NAMES[band].upper()} compound risk in {zn} "
                f"[{ids}] — score {ev['score']:.0f}/100")

    @staticmethod
    def _band(cur: int, score: float) -> int:
        new = cur
        for b, th in ENTER:
            if score >= th and b > new:
                new = b
        while new > 0 and score < EXIT[new]:
            new -= 1
        return new

    # ------------------------------------------------------------ public API

    def state_at(self, t: int) -> dict[str, Any]:
        """Compact risk snapshot for the API / WebSocket at minute t."""
        t = max(0, min(self.duration, int(t)))
        zones = {}
        for z in self.zone_ids:
            score = self.zone_score[z][t]
            band = self.zone_band[z][t]
            zones[z] = {"score": round(score, 1), "band": band,
                        "band_name": BAND_NAMES[band]}
        active = [a for a in self.alerts if a["t"] <= t
                  and self.zone_band[a["zone"]][t] >= 2]
        # keep only the latest alert per zone that is still elevated
        latest: dict[str, dict] = {}
        for a in active:
            latest[a["zone"]] = a
        active_now = sorted(latest.values(), key=lambda a: -a["band"])
        top_band = max((self.zone_band[z][t] for z in self.zone_ids), default=0)
        supp_now = [s for s in self.suppressions if s["t"] == t]
        return {
            "scenario": self.scenario,
            "t": t,
            "clock": self.tl.clock(t),
            "top_band": top_band,
            "top_band_name": BAND_NAMES[top_band],
            "zones": zones,
            "active_alerts": active_now,
            "suppressions": supp_now,
        }

    def alerts_list(self) -> list[dict]:
        return list(self.alerts)

    def first_alert(self, zone: str | None = None, min_band: int = 2) -> dict | None:
        for a in self.alerts:
            if a["band"] >= min_band and (zone is None or a["zone"] == zone) \
                    and a["kind"] == "new":
                return a
        return None


@lru_cache(maxsize=8)
def get_risk_engine(scenario_id: str) -> CompoundRiskEngine:
    """One immutable, fully-evaluated engine per scenario (cached)."""
    return CompoundRiskEngine(scenario_id)
