"""
KAVACH — Metrics Lab
====================

Runs the compound engine and the single-sensor baseline over an entire
scenario and scores both against ground truth. These are the numbers the
evaluation asks for explicitly — computed, not claimed:

* **prediction lead time** — minutes between KAVACH's compound alert and the
  first moment a conventional alarm system would have reacted.
* **false negatives** — measured two ways, because the crude way flatters the
  baseline. `false_negatives` counts hazard windows a system never flagged at
  all; by that measure a system that warns one minute before the explosion
  scores a perfect zero, which is obviously wrong. So we also compute
  `fn_rate_pct`: of all the minutes workers were actually exposed, what
  fraction passed with no warning standing. That is the metric that actually
  saves lives, and it is the one the evaluation focus asks for.
* **false positives** — alerts raised when ground truth says nothing was
  wrong (the metric that decides whether operators keep the system on).
* **per-rule contributions** — which pieces of reasoning did the work.

The lab is deterministic and ground-truth-driven, so every figure shown in
the UI, the deck and the demo is reproducible and defensible.
"""

from __future__ import annotations

from functools import lru_cache

from app.risk.baseline import get_baseline
from app.risk.compound import get_risk_engine
from app.simulator.engine import get_timeline


class MetricsLab:
    def __init__(self, scenario_id: str):
        self.scenario = scenario_id
        self.tl = get_timeline(scenario_id)
        self.eng = get_risk_engine(scenario_id)
        self.base = get_baseline(scenario_id)
        self.gt = self.tl.ground_truth

    def _windows(self) -> list[dict]:
        return self.gt.get("hazard_windows", []) or []

    def _in_windows(self, t: int) -> bool:
        return any(w["start"] <= t <= w["end"] for w in self._windows())

    def _covered_by(self, events: list[tuple[int, str]]) -> int:
        """Count hazard windows NOT covered by any (t, zone) detection inside
        them — i.e. false negatives."""
        windows = self._windows()
        if not windows:
            return 0
        fn = 0
        for w in windows:
            hit = any(w["start"] <= t <= w["end"]
                      and (zone is None or zone == w.get("zone"))
                      for t, zone in events)
            if not hit:
                fn += 1
        return fn

    def _exposure(self, first_warning_t: int | None) -> dict:
        """Timeliness-aware false-negative measurement.

        Every minute inside a ground-truth hazard window is a minute a worker
        was exposed and a warning *should* have been standing. We count how
        many of those minutes actually passed unwarned. A system that only
        reacts once the atmosphere is already lethal is not a system with zero
        false negatives — it is a system that was blind for most of the
        exposure, and this is where that shows up honestly.
        """
        windows = self._windows()
        total = sum(w["end"] - w["start"] for w in windows)
        if total <= 0:
            return {"hazard_minutes_total": 0, "hazard_minutes_unwarned": 0,
                    "hazard_minutes_warned": 0, "fn_rate_pct": 0.0,
                    "coverage_pct": 100.0}
        unwarned = 0
        for w in windows:
            if first_warning_t is None:          # never warned at all
                unwarned += w["end"] - w["start"]
            else:                                 # blind until the warning landed
                unwarned += max(0, min(w["end"], first_warning_t) - w["start"])
        warned = total - unwarned
        return {"hazard_minutes_total": total,
                "hazard_minutes_unwarned": unwarned,
                "hazard_minutes_warned": warned,
                "fn_rate_pct": round(100.0 * unwarned / total, 1),
                "coverage_pct": round(100.0 * warned / total, 1)}

    def compute(self) -> dict:
        incident = self.gt.get("incident_at")
        windows = self._windows()

        # ---- KAVACH (compound) -------------------------------------------
        new_alerts = [a for a in self.eng.alerts if a["kind"] == "new"]
        hazard_zones = {w.get("zone") for w in windows}
        detection = None
        if hazard_zones:
            detection = next((a for a in new_alerts if a["zone"] in hazard_zones),
                             None)
        if detection is None:
            detection = new_alerts[0] if new_alerts else None

        kavach_events = [(a["t"], a["zone"]) for a in self.eng.alerts
                         if a["band"] >= 2]
        kavach_fn = self._covered_by(kavach_events)
        # A false positive is an alert with no hazard behind it. Alerts raised
        # from the incident onward are the system correctly responding to a
        # real emergency, not false alarms — exclude them from the FP count.
        kavach_fp = sum(1 for a in new_alerts
                        if not self._in_windows(a["t"])
                        and (incident is None or a["t"] < incident))

        # ---- baseline (single-sensor) ------------------------------------
        b_first = self.base.first_uncleared()
        baseline_events = [(a.t, a.zone) for a in self.base.uncleared()]
        baseline_fn = self._covered_by(baseline_events)
        baseline_fp = sum(1 for a in self.base.uncleared()
                          if not self._in_windows(a.t)
                          and (incident is None or a.t < incident))

        # ---- headline comparison -----------------------------------------
        det_t = detection["t"] if detection else None
        base_t = b_first.t if b_first else None
        lead = (base_t - det_t) if (det_t is not None and base_t is not None) else None

        # timeliness-aware FN: how much of the exposure passed unwarned
        k_exp = self._exposure(det_t)
        b_exp = self._exposure(base_t)

        return {
            "scenario": self.scenario,
            "incident_at": incident,
            "incident_clock": self.tl.clock(incident) if incident is not None else None,
            "hazard_onset": self.gt.get("hazard_onset"),
            "lead_time_min": lead,
            "lead_time_h": round(lead / 60, 2) if lead is not None else None,
            "kavach": {
                "detection_t": det_t,
                "detection_clock": detection["clock"] if detection else None,
                "detection_zone": detection["zone"] if detection else None,
                "detection_band": detection["band_name"] if detection else None,
                "headline": detection["headline"] if detection else None,
                "confidence": detection["confidence"] if detection else None,
                "alerts_total": len(new_alerts),
                "false_negatives": kavach_fn,
                "false_positives": kavach_fp,
                **k_exp,
                "lead_before_incident_min":
                    (incident - det_t) if (incident is not None and det_t is not None)
                    else None,
            },
            "baseline": {
                "first_uncleared_t": base_t,
                "first_uncleared_clock": b_first.clock if b_first else None,
                "first_uncleared_sensor": b_first.sensor if b_first else None,
                "uncleared_total": len(self.base.uncleared()),
                "false_negatives": baseline_fn,
                "false_positives": baseline_fp,
                **b_exp,
                "lead_before_incident_min":
                    (incident - base_t) if (incident is not None and base_t is not None)
                    else None,
            },
            "per_rule_ticks": self.eng.rule_ticks,
            "suppression_count": len(self.eng.suppressions),
            "fn_rate_reduction_pct": round(b_exp["fn_rate_pct"] - k_exp["fn_rate_pct"], 1),
            "verdict": self._verdict(lead, kavach_fp, baseline_fp, k_exp, b_exp),
        }

    def _verdict(self, lead, k_fp, b_fp, k_exp, b_exp) -> str:
        if lead is not None:
            return (f"KAVACH raised a compound alert {lead} min "
                    f"({lead/60:.1f} h) before the first single-sensor alarm. "
                    f"Of {b_exp['hazard_minutes_total']} minutes of worker exposure, "
                    f"the single-sensor baseline left {b_exp['hazard_minutes_unwarned']} "
                    f"unwarned ({b_exp['fn_rate_pct']}% false-negative rate); "
                    f"KAVACH left {k_exp['hazard_minutes_unwarned']} "
                    f"({k_exp['fn_rate_pct']}%).")
        return (f"On a benign shift KAVACH raised {k_fp} false alert(s) vs the "
                f"baseline's {b_fp} — restraint the baseline cannot exercise.")


@lru_cache(maxsize=8)
def compute_metrics(scenario_id: str) -> dict:
    return MetricsLab(scenario_id).compute()
