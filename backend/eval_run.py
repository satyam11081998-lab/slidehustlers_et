"""
KAVACH — held-out statistical evaluation (CLI)

    python eval_run.py [n] [start_seed]

Generates `n` randomised scenarios the rule set has never seen, runs the
unmodified engines over them, and prints the distribution of results — including
the cases where KAVACH does worse than the conventional baseline.

The point of this script is falsifiability. The headline demo is one morning;
this is the experiment. Anyone can rerun it and get the same numbers, because
scenarios are generated from seeds.
"""

from __future__ import annotations

import json
import sys
import time

from app.eval.harness import run


def band(label: str, d: dict) -> None:
    if not d:
        print(f"  {label:24s} —")
        return
    print(f"  {label:24s} min {d['min']:>6} | p25 {d['p25']:>6} | median {d['median']:>6} "
          f"| p75 {d['p75']:>6} | max {d['max']:>6}")


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    t0 = time.time()
    r = run(n=n, start_seed=seed)

    print(f"\nKAVACH held-out evaluation — {r['n']} generated scenarios "
          f"({r['hazard_scenarios']} with a hazard, {r['benign_scenarios']} benign) "
          f"in {time.time()-t0:.0f}s\n")
    print("DETECTION")
    print(f"  KAVACH   detected {r['kavach_detection_rate_pct']}% of hazards")
    print(f"  baseline detected {r['baseline_detection_rate_pct']}% of hazards")
    print("\nLEAD TIME — how much earlier KAVACH warned than the conventional alarm")
    band("lead time (min)", r["lead_time"])
    print("\nWARNING BEFORE THE INCIDENT")
    band("KAVACH (min)", r["kavach_warning_min"])
    band("baseline (min)", r["baseline_warning_min"])
    print("\nFALSE-NEGATIVE RATE — share of worker exposure left unwarned")
    band("KAVACH (%)", r["kavach_fn_rate_pct"])
    band("baseline (%)", r["baseline_fn_rate_pct"])
    print("\nRESTRAINT — unseen benign scenarios, every barrier correctly in place")
    print(f"  KAVACH raised a false alert in {r['kavach_false_alert_rate_pct']}% of them")
    print(f"  baseline raised a false alert in {r['baseline_false_alert_rate_pct']}% of them")
    print(f"\nKAVACH warned earlier in {r['kavach_wins']}/{r['hazard_scenarios']} hazard "
          f"scenarios; tied or worse in {r['ties_or_losses']}.")

    losses = [x for x in r["rows"]
              if not x["benign"] and (x.get("lead_time_min") or 0) <= 0]
    if losses:
        print("\nWhere KAVACH did NOT beat the baseline (reported, not hidden):")
        for x in losses[:6]:
            print(f"  seed {x['seed']} {x['zone']:14s} lead {x.get('lead_time_min')} min "
                  f"| barriers {x['barriers']}")

    with open("eval_results.json", "w", encoding="utf-8") as fh:
        json.dump(r, fh, indent=1)
    print("\nFull per-scenario results written to eval_results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
