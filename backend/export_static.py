"""
KAVACH — static export for zero-backend hosting

    python export_static.py

Writes everything the control room needs into `frontend/public/demo/`, so the
UI can run with no API server at all.

Why this exists: the engines are fully deterministic, so a hosted demo does not
need to recompute anything. Precomputing removes every runtime failure mode
from the public link — no serverless cold start, no WebSocket support needed
(Vercel has none), no backend to fall over while a judge is watching. The
locally-run stack is unchanged and still the real system; this is the same
numbers, frozen.

Payload per scenario: one frame per simulated minute, in exactly the shape the
WebSocket emits, plus metrics, alerts, baseline and the chart series.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.risk.baseline import get_baseline            # noqa: E402
from app.risk.compound import get_risk_engine         # noqa: E402
from app.risk.metrics import compute_metrics          # noqa: E402
from app.simulator.engine import get_timeline, list_scenarios  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "demo"
STEP = 2          # matches the UI's chart decimation
SPARKS = {
    "vizag_replay": ["PT-GM-104", "GD-CO4-203", "DP-CO4-801", "GD-CO4-204"],
    "normal_day": ["PT-GM-103", "GD-BPP-209", "PT-GM-104", "GD-CO4-203"],
}


def risk_series(scenario: str, step: int) -> dict:
    """Byte-for-byte the payload of GET /api/risk/series.

    This must mirror the endpoint exactly — the UI indexes `zones[hero]` and
    treats `baseline` as a percentage of each sensor's own alarm limit. An
    earlier version of this exporter invented its own shape and crashed the
    offline path, so the logic is duplicated deliberately rather than
    approximated.
    """
    tl = get_timeline(scenario)
    eng = get_risk_engine(scenario)
    step = max(1, int(step))
    ts = list(range(0, tl.duration + 1, step))
    zones = {z: [round(eng.zone_score[z][t], 1) for t in ts] for z in eng.zone_ids}

    def baseline_pct(t: int) -> float:
        best = 0.0
        for sid, meta in tl.sensors_meta.items():
            alarm = (meta.get("limits") or {}).get("alarm")
            if alarm:
                best = max(best, tl.series[sid][t] / alarm * 100.0)
        return round(min(120.0, best), 1)

    hero = max(eng.zone_ids, key=lambda z: max(eng.zone_score[z]))
    return {"scenario": scenario, "step": step, "duration": tl.duration,
            "t": ts, "zones": zones, "baseline": [baseline_pct(t) for t in ts],
            "hero": hero}


def export(scenario: str) -> Path:
    tl = get_timeline(scenario)
    eng = get_risk_engine(scenario)
    bl = get_baseline(scenario)

    frames = []
    for t in range(0, tl.duration + 1):
        frames.append({
            "state": tl.state_at(t),
            "risk": eng.state_at(t),
        })

    payload = {
        "scenario": scenario,
        "title": tl.sc["title"],
        "duration": tl.duration,
        "frames": frames,
        "metrics": compute_metrics(scenario),
        "alerts": [a for a in eng.alerts_list() if a.get("kind") == "new"],
        "baseline": {**bl.summary(), "alarms": [a.to_dict() for a in bl.alarms()]},
        "risk_series": risk_series(scenario, STEP),
        "series": {
            sid: {**tl.series_for(sid, STEP), "step": STEP}
            for sid in SPARKS.get(scenario, [])
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{scenario}.json"
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return path


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ids = [s["id"] for s in list_scenarios() if not s["id"].startswith("mc_")]
    index = []
    for sid in ids:
        p = export(sid)
        mb = p.stat().st_size / 1e6
        print(f"  {sid:16s} -> {p.name}  {mb:.2f} MB")
        index.append({"id": sid, "title": get_timeline(sid).sc["title"]})
    (OUT / "index.json").write_text(json.dumps(index), encoding="utf-8")
    print(f"\nWrote {len(ids)} scenario(s) to {OUT}")
    print("The control room will use these automatically when no API is configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
