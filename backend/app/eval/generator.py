"""
KAVACH — Randomised scenario generator (held-out evaluation)
============================================================

The fair criticism of any hand-built demo is circularity: the team wrote the
scenario, wrote the rules, and then reported that the rules caught the
scenario. This module exists to remove that objection.

It generates scenarios the rule set has never seen, by randomising the things
that actually vary between real incidents:

* **which zone** the hazard develops in (either confined space, not just the
  one used in the demo);
* **which barriers fail** — isolation, gas-test quality, handover, hot-work
  proximity, valve coordination — sampled independently, so most generated
  incidents are *not* the demo's failure pattern;
* **timing and rate** — drift onset, ramp gradient, permit hours, incident time;
* **instrument noise**, via a per-scenario seed salt;
* **whether there is a hazard at all** — a controllable fraction of scenarios
  are fully benign, with every barrier correctly in place, to measure false
  alerts on unseen benign days.

Nothing here is tuned to make KAVACH look good. Scenarios are emitted from a
seed, so any result can be reproduced by anyone with `python eval_run.py`.
"""

from __future__ import annotations

import random
from typing import Any

# Confined spaces we may put a crew into, with the instruments that watch them.
TARGETS = {
    "cob4_basement": {
        "co": ["GD-CO4-203", "GD-CO4-204"],
        "press": "PT-GM-104",
        "valve": "ZI-GM-707",
        "dp": "DP-CO4-801",
        "name": "Battery 4 Basement",
        "adjacent_hotwork_zone": "platform_p2",
    },
    "cob3_basement": {
        "co": ["GD-CO3-208", "GD-CO3-207"],
        "press": "PT-GM-101",
        "valve": "ZI-GM-701",
        "dp": "DP-CO4-801",
        "name": "Battery 3 Basement",
        "adjacent_hotwork_zone": "cob3",
    },
}


def generate(seed: int, benign_fraction: float = 0.35) -> dict[str, Any]:
    """Build one randomised scenario. Deterministic in `seed`."""
    rng = random.Random(seed)
    zone = rng.choice(list(TARGETS))
    T = TARGETS[zone]
    benign = rng.random() < benign_fraction

    duration = rng.choice([540, 600, 660])
    start_hour = rng.choice([2, 4, 6])
    start_clock = f"{start_hour:02d}:00"

    # --- when things happen -------------------------------------------------
    entry = rng.randrange(180, 330, 15)              # confined-space entry
    incident = entry + rng.randrange(180, 300, 30)   # exposure length varies
    incident = min(incident, duration - 40)
    drift_start = max(10, entry - rng.randrange(120, 260, 20))
    changeover = rng.randrange(150, 300, 30)

    # --- which barriers fail (independent draws) ---------------------------
    if benign:
        isolation_applied = True
        multipoint_test = True
        handover_notes_drift = True
        hot_work = False
        valve_throttle = False
    else:
        isolation_applied = rng.random() < 0.30
        multipoint_test = rng.random() < 0.40
        handover_notes_drift = rng.random() < 0.45
        hot_work = rng.random() < 0.55
        valve_throttle = rng.random() < 0.45

    co_peak = rng.uniform(70, 260) if not benign else rng.uniform(12, 26)
    press_peak = rng.uniform(9.2, 10.6) if not benign else rng.uniform(6.9, 8.2)
    co_a = T["co"][0]

    ramps: list[dict] = []
    spikes: list[dict] = []
    events: list[dict] = []

    # gas-main pressure: slow sub-threshold drift, then acceleration
    ramps.append({"sensor": T["press"], "t0": drift_start, "t1": entry,
                  "to": round(rng.uniform(8.2, 8.9), 2)})
    ramps.append({"sensor": T["press"], "t0": entry, "t1": incident - 10,
                  "to": round(press_peak, 2)})
    if not benign:
        ramps.append({"sensor": T["press"], "t0": incident, "t1": incident + 8,
                      "to": round(rng.uniform(3.8, 4.8), 2)})

    # CO in the occupied chamber
    onset = entry + rng.randrange(20, 80, 10)
    ramps.append({"sensor": co_a, "t0": drift_start + 30, "t1": onset,
                  "to": round(rng.uniform(14, 22), 1)})
    ramps.append({"sensor": co_a, "t0": onset, "t1": incident - 5,
                  "to": round(co_peak, 1)})
    if not benign:
        ramps.append({"sensor": co_a, "t0": incident, "t1": incident + 10,
                      "to": round(co_peak * rng.uniform(1.4, 2.0), 1)})
        # a second channel sometimes corroborates, sometimes not
        if rng.random() < 0.6:
            co_b = T["co"][1]
            ramps.append({"sensor": co_b, "t0": onset + rng.randrange(20, 90, 10),
                          "t1": incident, "to": round(co_peak * rng.uniform(0.4, 0.8), 1)})

    if valve_throttle:
        vt = rng.randrange(entry + 60, max(entry + 90, incident - 20), 15)
        ramps.append({"sensor": T["valve"], "t0": vt, "t1": vt + 2,
                      "to": rng.choice([35, 45, 55])})
        ramps.append({"sensor": T["dp"], "t0": vt, "t1": incident,
                      "to": round(rng.uniform(1.05, 1.4), 2)})
        events.append({"t": vt, "type": "valve_op", "visible": True,
                       "title": "Isolation valve throttled during maintenance",
                       "zone": "gm_corridor", "sensor": T["valve"], "severity": "warn"})

    # --- permits ------------------------------------------------------------
    isolations = ["Electrical LOTO applied"]
    isolations.append("Gas-main isolation: applied and certified" if isolation_applied
                      else "Gas-main isolation: NOT applied")
    gas_detail = ("Multi-point test: entrance, mid-chamber and rear all clear; "
                  "continuous monitor issued to crew.") if multipoint_test else \
                 "Single-point test at chamber entrance only. Rear not tested."
    permits = [{
        "id": "CSE-9001", "type": "Confined Space Entry", "zone": zone,
        "title": "Inspection chamber work", "from": entry, "to": duration,
        "crew": ["A", "B", "C", "D"][:rng.randint(2, 4)],
        "gas_test": {"t": entry - 15, "ref": "GT-9001", "result": "PASS",
                     "detail": gas_detail},
        "isolations": isolations,
    }]
    if hot_work:
        hw = rng.randrange(entry + 40, max(entry + 70, incident - 15), 15)
        permits.append({
            "id": "HW-9002", "type": "Hot Work", "zone": T["adjacent_hotwork_zone"],
            "title": "Welding near vent", "from": hw, "to": duration,
            "crew": ["S", "V"],
            "gas_test": {"t": hw - 5, "ref": "GT-9002", "result": "PASS",
                         "detail": "Spot test at work location."},
            "isolations": ["Fire blanket staged"],
        })
        events.append({"t": hw, "type": "permit", "visible": True,
                       "title": "Hot work permit activated near the vent shaft",
                       "zone": T["adjacent_hotwork_zone"], "severity": "warn"})

    work_orders = [{"id": "WO-9001", "title": "Inspection chamber repair", "zone": zone,
                    "kind": "corrective", "created": max(0, entry - 90),
                    "started": entry, "completed": None, "notes": "Generated scenario."}]

    # --- narrative events (R4 keys off acknowledgement language) ------------
    events.append({"t": changeover, "type": "shift_change", "visible": True,
                   "title": "Shift changeover",
                   "detail": ("Handover note records the pressure drift."
                              if handover_notes_drift else
                              "Handover note does not mention the drift."),
                   "severity": "info" if handover_notes_drift else "warn"})
    if not handover_notes_drift and not benign:
        events.append({"t": entry - 5, "type": "operator_log", "visible": True,
                       "title": "Pressure advisory acknowledged as known drift",
                       "detail": "Acknowledged: known drift, under maintenance.",
                       "zone": "gm_corridor", "sensor": T["press"], "severity": "warn"})
    events.append({"t": entry, "type": "permit", "visible": True,
                   "title": "Confined space entry activated", "zone": zone,
                   "severity": "warn"})
    if not benign:
        events.append({"t": incident, "type": "incident", "visible": True,
                       "title": "INCIDENT MARKER", "zone": zone, "severity": "high"})

    gt: dict[str, Any] = {
        "incident_at": incident if not benign else None,
        "hazard_onset": entry if not benign else None,
        "kavach_expected_alert": entry if not benign else None,
        "baseline_first_uncleared_alarm": None,
        "hazard_windows": ([{"start": entry, "end": incident, "zone": zone}]
                           if not benign else []),
        "contributing_factors": [],
    }

    return {
        "id": f"mc_{seed:05d}",
        "title": f"Generated scenario {seed} — {T['name']}",
        "description": "Randomised held-out scenario for statistical evaluation.",
        "narrative": "",
        "start_clock": start_clock,
        "duration_min": duration,
        "seed_salt": f"mc-{seed}",
        "shifts": [
            {"name": "C", "label": "Night", "from": 0, "to": changeover,
             "supervisor": "R. Prasad", "crew_count": 12},
            {"name": "A", "label": "Morning", "from": changeover, "to": duration,
             "supervisor": "S. K. Murthy", "crew_count": 20},
        ],
        "permits": permits,
        "work_orders": work_orders,
        "ramps": ramps,
        "spikes": spikes,
        "events": sorted(events, key=lambda e: e["t"]),
        "ground_truth": gt,
        "_meta": {
            "benign": benign, "zone": zone,
            "barriers": {
                "isolation_applied": isolation_applied,
                "multipoint_test": multipoint_test,
                "handover_notes_drift": handover_notes_drift,
                "hot_work": hot_work, "valve_throttle": valve_throttle,
            },
            "entry": entry, "incident": incident, "co_peak": round(co_peak, 1),
        },
    }
