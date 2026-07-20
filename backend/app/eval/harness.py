"""
KAVACH — Held-out evaluation harness
====================================

Runs the *unmodified* engines over generated scenarios and scores them the same
way `metrics.py` scores the demo scenario. Nothing about the rules, weights or
thresholds is touched here; if the engine underperforms on unseen data, this is
where it shows, and the numbers are reported as they come out.

For each scenario we record:

* whether a hazard existed at all (ground truth from the generator);
* when KAVACH first raised an alert of band >= alert in the hazard zone;
* when a conventional single-sensor alarm would first have fired;
* lead time, exposure coverage (the timeliness-aware false-negative rate), and
  false alerts on benign scenarios.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.eval.generator import generate

SCENARIO_DIR = Path(__file__).resolve().parents[3] / "data" / "scenarios"


def _clear_caches() -> None:
    """Engines cache per scenario id; drop everything between runs."""
    from app.simulator import engine as _eng
    from app.risk import baseline as _b, compound as _c, metrics as _m, signals as _s
    for fn in (_eng.get_timeline, _b.get_baseline, _c.get_risk_engine,
               _m.compute_metrics, getattr(_s, "get_signals", None)):
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()


def evaluate_seed(seed: int, benign_fraction: float = 0.35) -> dict[str, Any]:
    sc = generate(seed, benign_fraction)
    meta = sc.pop("_meta")
    path = SCENARIO_DIR / f"{sc['id']}.json"
    path.write_text(json.dumps(sc), encoding="utf-8")
    try:
        _clear_caches()
        from app.risk.baseline import get_baseline
        from app.risk.compound import get_risk_engine
        from app.risk.metrics import compute_metrics

        m = compute_metrics(sc["id"])
        eng = get_risk_engine(sc["id"])
        base = get_baseline(sc["id"])
        zone = meta["zone"]
        incident = meta["incident"] if not meta["benign"] else None

        # first KAVACH alert at alert-or-critical band in the hazard zone
        k_t = None
        for a in eng.alerts:
            if a["zone"] == zone and a["band"] >= 2:
                k_t = a["t"]
                break
        b = base.first_uncleared()
        b_t = b.t if b else None

        res = {
            "seed": seed, "scenario": sc["id"], "zone": zone,
            "benign": meta["benign"], "barriers": meta["barriers"],
            "entry": meta["entry"], "incident": incident,
            "kavach_t": k_t, "baseline_t": b_t,
            "kavach_fn_rate": m["kavach"].get("fn_rate_pct"),
            "baseline_fn_rate": m["baseline"].get("fn_rate_pct"),
            "kavach_fp": m["kavach"].get("false_positives"),
            "baseline_fp": m["baseline"].get("false_positives"),
        }
        if not meta["benign"]:
            res["kavach_warning_min"] = (incident - k_t) if k_t is not None else 0
            res["baseline_warning_min"] = (incident - b_t) if b_t is not None else 0
            res["lead_time_min"] = ((b_t - k_t) if (k_t is not None and b_t is not None)
                                    else None)
            res["kavach_detected"] = k_t is not None and k_t <= incident
            res["baseline_detected"] = b_t is not None and b_t <= incident
        else:
            res["kavach_false_alert"] = k_t is not None
            res["baseline_false_alert"] = b_t is not None
        return res
    finally:
        path.unlink(missing_ok=True)
        _clear_caches()


def run(n: int = 100, start_seed: int = 1000,
        benign_fraction: float = 0.35) -> dict[str, Any]:
    rows = [evaluate_seed(start_seed + i, benign_fraction) for i in range(n)]
    haz = [r for r in rows if not r["benign"]]
    ben = [r for r in rows if r["benign"]]

    def pct(xs: list[float]) -> dict[str, float]:
        if not xs:
            return {}
        s = sorted(xs)
        q = lambda p: s[min(len(s) - 1, int(p * (len(s) - 1)))]
        return {"min": s[0], "p25": q(.25), "median": q(.5), "p75": q(.75), "max": s[-1],
                "mean": round(sum(s) / len(s), 1)}

    leads = [r["lead_time_min"] for r in haz if r.get("lead_time_min") is not None]
    k_warn = [r["kavach_warning_min"] for r in haz]
    b_warn = [r["baseline_warning_min"] for r in haz]
    k_fn = [r["kavach_fn_rate"] for r in haz if r["kavach_fn_rate"] is not None]
    b_fn = [r["baseline_fn_rate"] for r in haz if r["baseline_fn_rate"] is not None]

    return {
        "n": n, "hazard_scenarios": len(haz), "benign_scenarios": len(ben),
        "kavach_detection_rate_pct": round(
            100.0 * sum(1 for r in haz if r["kavach_detected"]) / max(1, len(haz)), 1),
        "baseline_detection_rate_pct": round(
            100.0 * sum(1 for r in haz if r["baseline_detected"]) / max(1, len(haz)), 1),
        "lead_time": pct(leads),
        "kavach_warning_min": pct(k_warn),
        "baseline_warning_min": pct(b_warn),
        "kavach_fn_rate_pct": pct(k_fn),
        "baseline_fn_rate_pct": pct(b_fn),
        "kavach_false_alert_rate_pct": round(
            100.0 * sum(1 for r in ben if r["kavach_false_alert"]) / max(1, len(ben)), 1),
        "baseline_false_alert_rate_pct": round(
            100.0 * sum(1 for r in ben if r["baseline_false_alert"]) / max(1, len(ben)), 1),
        "kavach_wins": sum(1 for r in haz if (r.get("lead_time_min") or 0) > 0),
        "ties_or_losses": sum(1 for r in haz if (r.get("lead_time_min") or 0) <= 0),
        "rows": rows,
    }
