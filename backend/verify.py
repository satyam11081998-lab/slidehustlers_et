"""
KAVACH Day-1 verification — run from backend/:  python verify.py

Checks that the digital twin is deterministic and that the scripted
incident curves hit their narrative checkpoints exactly where the
Day-2 risk engines (and the demo) expect them.
"""

from __future__ import annotations

import sys

from app.simulator.engine import Timeline, list_scenarios
from app.risk.baseline import get_baseline
from app.risk.compound import get_risk_engine
from app.risk.metrics import compute_metrics
from app.risk import regulatory, whatif
from app.risk.orchestrator import get_orchestrator
from app.risk.report import generate_markdown

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILURES.append(label)


def first_crossing(values: list[float], threshold: float) -> int | None:
    for t, v in enumerate(values):
        if v >= threshold:
            return t
    return None


def main() -> int:
    print("Scenarios discovered:", [s["id"] for s in list_scenarios()])

    # ---------------------------------------------------------- vizag_replay
    print("\n== vizag_replay ==")
    tl = Timeline("vizag_replay")
    check("duration is 600 min (02:00 -> 12:00)", tl.duration == 600)

    pt = tl.series["PT-GM-104"]
    co_a = tl.series["GD-CO4-203"]
    co_b = tl.series["GD-CO4-204"]

    print("\n  Checkpoint table (PT-GM-104 kPa | GD-CO4-203 ppm | GD-CO4-204 ppm):")
    for t in (0, 145, 270, 390, 450, 460, 492, 509, 516):
        print(
            f"    t={t:>3} {tl.clock(t)}  "
            f"PT={pt[t]:>6.2f}  CO-A={co_a[t]:>6.1f}  CO-B={co_b[t]:>6.1f}"
        )

    check("PT-GM-104 starts at ~6.8 kPa", 6.5 < pt[0] < 7.1, f"{pt[0]:.2f}")
    check("PT-GM-104 ~8.6 kPa at hazard onset (06:30)", 8.3 < pt[270] < 8.9, f"{pt[270]:.2f}")
    check("PT-GM-104 exceeds 10 kPa just before incident", pt[509] > 10.0, f"{pt[509]:.2f}")
    check("PT-GM-104 depressurises after incident", pt[520] < 5.0, f"{pt[520]:.2f}")

    t_alarm = first_crossing(co_a[300:], 50.0)
    t_alarm = None if t_alarm is None else t_alarm + 300
    check(
        "GD-CO4-203 first crosses 50 ppm alarm near 09:40 (t=460±10)",
        t_alarm is not None and 450 <= t_alarm <= 470,
        f"t={t_alarm} ({tl.clock(t_alarm) if t_alarm else '-'})",
    )

    t_high = first_crossing(co_a[300:], 100.0)
    t_high = None if t_high is None else t_high + 300
    check(
        "GD-CO4-203 crosses 100 ppm high limit before incident (t<510)",
        t_high is not None and 470 <= t_high < 510,
        f"t={t_high}",
    )

    gt = tl.ground_truth
    check("ground truth: hazard onset 270 / incident 510",
          gt.get("hazard_onset") == 270 and gt.get("incident_at") == 510)
    check(
        "baseline first uncleared alarm (460) matches curve",
        t_alarm is not None and abs(t_alarm - gt["baseline_first_uncleared_alarm"]) <= 10,
    )

    lead = gt["baseline_first_uncleared_alarm"] - gt["kavach_expected_alert"]
    print(f"  Expected KAVACH lead time vs baseline: {lead} min ({lead / 60:.1f} h)")

    check("events sorted and inside horizon",
          all(0 <= e["t"] <= tl.duration for e in tl.events))
    zone_ids = {z["id"] for z in tl.plant["zones"]}
    check("permit zones all exist in layout",
          all(p["zone"] in zone_ids for p in tl.permits))
    check("ramp/spike sensors all exist",
          all(r["sensor"] in tl.sensors_meta for r in tl.sc.get("ramps", []))
          and all(s["sensor"] in tl.sensors_meta for s in tl.sc.get("spikes", [])))

    tl2 = Timeline("vizag_replay")
    check("determinism: rebuild produces identical series", tl2.series == tl.series)

    st = tl.state_at(470)
    check(
        "state@09:50: CSE-2093 + HW-2101 active, shift A",
        {p["id"] for p in st["permits"] if p["active"]} >= {"CSE-2093", "HW-2101"}
        and st["shift"]["name"] == "A",
    )
    check("state@09:50 has alarm-level sensors", st["summary"]["alarm"] + st["summary"]["high"] >= 1)

    # ------------------------------------------------------------ normal_day
    print("\n== normal_day ==")
    nd = Timeline("normal_day")
    check("duration is 480 min (06:00 -> 14:00)", nd.duration == 480)
    check("ground truth: no hazard windows", nd.ground_truth["hazard_windows"] == [])

    # No sensor should breach its ALARM limit except PT-GM-103 during the
    # scripted calibration window (t 238-248).
    offenders: list[str] = []
    for sid, meta in nd.sensors_meta.items():
        limits = meta.get("limits")
        if not limits or "alarm" not in limits:
            continue
        for t, v in enumerate(nd.series[sid]):
            if v >= limits["alarm"] and not (sid == "PT-GM-103" and 236 <= t <= 250):
                offenders.append(f"{sid}@{t}={v}")
    check("no un-scripted alarm crossings on the benign day", not offenders,
          "; ".join(offenders[:5]))

    cal = first_crossing(nd.series["PT-GM-103"], 9.0)
    check("PT-GM-103 calibration spike lands in 10:00 window", cal is not None and 236 <= cal <= 246,
          f"t={cal}")

    day2()
    day4()

    print(f"\n{'ALL CHECKS PASSED' if not FAILURES else f'{len(FAILURES)} CHECK(S) FAILED'}")
    return 0 if not FAILURES else 1


# ======================================================================
#  DAY 2 — Compound Risk Engine, Baseline, Metrics Lab
# ======================================================================

def day2() -> None:
    print("\n== DAY 2: risk engine ==")

    # ---- vizag_replay: the incident the system must see early -------------
    m = compute_metrics("vizag_replay")
    k, b = m["kavach"], m["baseline"]

    print(f"\n  KAVACH detection : t={k['detection_t']} "
          f"({k['detection_clock']}, {k['detection_band']}) in {k['detection_zone']}")
    print(f"  Baseline first   : t={b['first_uncleared_t']} "
          f"({b['first_uncleared_clock']}) on {b['first_uncleared_sensor']}")
    print(f"  Lead time        : {m['lead_time_min']} min "
          f"({m['lead_time_h']} h)")
    print(f"  Per-rule ticks   : {m['per_rule_ticks']}")

    check("KAVACH compound alert lands at hazard onset (t=270±5)",
          k["detection_t"] is not None and abs(k["detection_t"] - 270) <= 5,
          f"t={k['detection_t']}")
    check("KAVACH first alert is CRITICAL band",
          k["detection_band"] == "critical", f"{k['detection_band']}")
    check("baseline first uncleared alarm near t=460 on GD-CO4-203",
          b["first_uncleared_t"] is not None and abs(b["first_uncleared_t"] - 460) <= 10
          and b["first_uncleared_sensor"] == "GD-CO4-203",
          f"t={b['first_uncleared_t']} {b['first_uncleared_sensor']}")
    check("prediction lead time = 190 min (±10)",
          m["lead_time_min"] is not None and abs(m["lead_time_min"] - 190) <= 10,
          f"{m['lead_time_min']} min")
    check("KAVACH false negatives on the incident = 0",
          k["false_negatives"] == 0, f"{k['false_negatives']}")
    check("KAVACH false positives on the incident = 0",
          k["false_positives"] == 0, f"{k['false_positives']}")
    check("KAVACH beats baseline to the incident by hours",
          k["lead_before_incident_min"] is not None
          and b["lead_before_incident_min"] is not None
          and k["lead_before_incident_min"] - b["lead_before_incident_min"] >= 120,
          f"KAVACH {k['lead_before_incident_min']} vs baseline "
          f"{b['lead_before_incident_min']} min before incident")

    # rules fire where the narrative says they should
    eng = get_risk_engine("vizag_replay")
    r270 = eng.contribs_at("cob4_basement", 270)["rule_ids"]
    r390 = eng.contribs_at("cob4_basement", 390)["rule_ids"]
    r455 = eng.contribs_at("cob4_basement", 455)["rule_ids"]
    print(f"\n  Rules @270: {r270}\n  Rules @390: {r390}\n  Rules @455: {r455}")
    check("R1+R3 (+R5) fire at CSE entry t=270",
          {"R1", "R3", "R5"} <= set(r270), str(r270))
    check("R4 handover-blindspot escalator active at t=270",
          "R4" in r270, str(r270))
    check("R2 hot-work proximity fires at t=390", "R2" in r390, str(r390))
    check("R6 valve/back-pressure fires by t=455", "R6" in r455, str(r455))

    # pre-entry discipline: no alert-band before the crew goes in
    pre = eng.zone_band["cob4_basement"][269]
    check("cob4_basement below ALERT band before entry (t=269)",
          pre < 2, f"band={pre}")

    # ---- normal_day: the restraint test ----------------------------------
    mn = compute_metrics("normal_day")
    kn, bn = mn["kavach"], mn["baseline"]
    print(f"\n  normal_day — KAVACH FP={kn['false_positives']} "
          f"baseline FP={bn['false_positives']} "
          f"suppressions={mn['suppression_count']}")
    check("KAVACH raises ZERO false alerts on the benign day",
          kn["false_positives"] == 0, f"{kn['false_positives']}")
    check("baseline false-alarms on the benign day (>=1)",
          bn["false_positives"] >= 1, f"{bn['false_positives']}")
    check("KAVACH suppressed the calibration reading (R8, >=1)",
          mn["suppression_count"] >= 1, f"{mn['suppression_count']}")

    base_nd = get_baseline("normal_day")
    fu = base_nd.first_uncleared()
    check("baseline's benign-day FP is the PT-GM-103 calibration plateau",
          fu is not None and fu.sensor == "PT-GM-103",
          f"{fu.sensor if fu else None}@{fu.t if fu else None}")

    # ---- determinism: rebuild yields identical metrics -------------------
    m2 = compute_metrics.__wrapped__("vizag_replay")  # bypass cache, recompute
    check("risk metrics are deterministic (recompute identical)",
          m2["lead_time_min"] == m["lead_time_min"]
          and m2["per_rule_ticks"] == m["per_rule_ticks"])


# ======================================================================
#  DAY 4 — Regulatory RAG, Orchestrator, Report, What-if
# ======================================================================

def day4() -> None:
    print("\n== DAY 4: regulatory / orchestrator / report / what-if ==")

    # ---- Regulatory RAG ---------------------------------------------------
    cov = regulatory.get_corpus().coverage()
    print(f"\n  Regulatory sources: {[s['code'] for s in cov['sources']]} "
          f"({cov['clause_count']} clauses); rules covered {cov['rules_covered']}")
    check("regulatory corpus has OISD + Factories Act + DGMS",
          {"OISD-STD-105", "FA-1948", "DGMS"} <= {s["code"] for s in cov["sources"]},
          str([s["code"] for s in cov["sources"]]))
    for rid in ("R1", "R2", "R3", "R5", "R6"):
        cites = regulatory.citations_for_rules([rid])
        check(f"material rule {rid} has >=1 regulatory citation",
              len(cites) >= 1, f"{[c['citation'] for c in cites]}")
    # confined-space citation must include the governing statute clause
    r135 = {c["citation"] for c in regulatory.citations_for_rules(["R1", "R3", "R5"])}
    check("confined-space citations include Factories Act S.36(2)",
          any("S.36(2)" in c for c in r135), str(r135))
    hits = regulatory.search("confined space gas main isolation before entry", 5)
    print(f"  Top retrieval: {[h['citation'] for h in hits[:3]]}")
    check("BM25 retrieval returns ranked clauses for an isolation query",
          len(hits) >= 1 and "score" in hits[0])

    # alerts now carry regulatory_basis
    a = get_risk_engine("vizag_replay").first_alert(min_band=3)
    a_cited = regulatory.attach_to_alert(a)
    check("critical alert carries a regulatory_basis[]",
          len(a_cited.get("regulatory_basis", [])) >= 1,
          f"{[c['citation'] for c in a_cited['regulatory_basis']]}")

    # ---- Orchestrator -----------------------------------------------------
    orch = get_orchestrator("vizag_replay").as_dict()
    trg = orch["trigger"]
    types = [ac["type"] for ac in orch["actions"]]
    print(f"\n  Orchestrator trigger t={trg['t']} ({trg['clock']}) in {trg['zone']}; "
          f"actions={types}")
    check("orchestrator triggers on the critical alert at t=270",
          orch["triggered"] and trg["t"] == 270 and trg["zone"] == "cob4_basement",
          f"t={trg['t']} zone={trg['zone']}")
    check("plan includes suspend / isolate / notify / evacuate / re-test / monitor",
          {"suspend_permit", "isolate_gas_main", "notify", "evacuate",
           "re_test", "monitor"} <= set(types), str(types))
    check("plan suspends the confined-space entry CSE-2093",
          any(p["id"] == "CSE-2093" for p in orch["suspended_permits"]),
          str([p["id"] for p in orch["suspended_permits"]]))
    evac_ids = [z["id"] for z in orch["evacuation"]["immediate"]]
    check("evacuation set (from connectivity) includes cob4_basement",
          "cob4_basement" in evac_ids, str(evac_ids))
    check("every orchestrator action carries a regulatory basis",
          all(len(ac["regulatory_basis"]) >= 1 for ac in orch["actions"]),
          f"{[ac['type'] for ac in orch['actions'] if not ac['regulatory_basis']]}")
    cf = orch["counterfactual"]
    print(f"  Counterfactual: {cf['minutes_earlier']} min earlier; "
          f"prevented {[e['id'] for e in cf['prevented_downstream']]}")
    check("counterfactual = 240 min earlier than the incident",
          cf["minutes_earlier"] == 240, f"{cf['minutes_earlier']}")
    prevented = {e["id"] for e in cf["prevented_downstream"]}
    check("counterfactual pre-empts the hot-work permit and valve throttle",
          {"HW-2101", "WO-8815"} <= prevented, str(prevented))
    # restraint: benign day raises no emergency plan
    orch_n = get_orchestrator("normal_day").as_dict()
    check("orchestrator does NOT trigger on the benign day",
          orch_n["triggered"] is False, f"{orch_n['triggered']}")

    # ---- Report -----------------------------------------------------------
    md = generate_markdown("vizag_replay")
    m = compute_metrics("vizag_replay")
    print(f"\n  Report length: {len(md)} chars")
    check("report cites the lead-time number",
          str(m["lead_time_min"]) in md, f"{m['lead_time_min']}")
    check("report includes statutory + standard + counterfactual",
          "FA-1948" in md and "OISD-STD-105" in md and "Counterfactual" in md)

    # ---- What-if sandbox --------------------------------------------------
    eng = get_risk_engine("vizag_replay")
    iso = whatif.evaluate("vizag_replay", 270,
                          [{"op": "isolate_gas_main", "permit": "CSE-2093"}], eng)
    print(f"\n  what-if [isolate @270]: {iso['narrative']}")
    check("what-if isolate clears R3 and drops out of CRITICAL",
          "R3" in iso["delta"]["rules_removed"]
          and iso["modified"]["band_name"] != "critical",
          f"removed={iso['delta']['rules_removed']} band={iso['modified']['band_name']}")
    mp = whatif.evaluate("vizag_replay", 270,
                         [{"op": "multipoint_gas_test", "permit": "CSE-2093"}], eng)
    check("what-if representative gas test clears R5",
          "R5" in mp["delta"]["rules_removed"], str(mp["delta"]["rules_removed"]))
    corr = whatif.evaluate("vizag_replay", 380,
                           [{"op": "raise_sensor", "sensor": "GD-CO4-204",
                             "t0": 270, "t1": 480, "to": 55}], eng)
    print(f"  what-if [2nd CO channel @380]: {corr['narrative']}")
    check("what-if second rising channel adds corroboration (R7)",
          "R7" in corr["delta"]["rules_added"], str(corr["delta"]["rules_added"]))
    iso2 = whatif.evaluate("vizag_replay", 270,
                           [{"op": "isolate_gas_main", "permit": "CSE-2093"}], eng)
    check("what-if is deterministic (recompute identical)",
          iso2["delta"] == iso["delta"] and iso2["modified"]["score"] == iso["modified"]["score"])

    # ---------------------------------------------------------- Day-5 additions
    print("\n== false-negative RATE (the evaluation-focus headline metric) ==")
    from app.risk.metrics import compute_metrics as _cm
    mv = _cm("vizag_replay")
    k, b = mv["kavach"], mv["baseline"]
    print(f"  exposure {b['hazard_minutes_total']} min | baseline unwarned "
          f"{b['hazard_minutes_unwarned']} ({b['fn_rate_pct']}%) | KAVACH "
          f"{k['hazard_minutes_unwarned']} ({k['fn_rate_pct']}%)")
    check("hazard exposure window is 240 min", b["hazard_minutes_total"] == 240)
    check("KAVACH false-negative rate is 0%", k["fn_rate_pct"] == 0.0)
    check("baseline leaves ~79% of the exposure unwarned",
          78.0 <= b["fn_rate_pct"] <= 79.5, f"{b['fn_rate_pct']}%")
    check("FN-rate reduction is reported and material",
          mv["fn_rate_reduction_pct"] >= 75.0, f"{mv['fn_rate_reduction_pct']} pts")

    print("\n== incident pattern intelligence ==")
    from app.risk.patterns import get_patterns
    pats = get_patterns()
    live = pats.match_live(["R1", "R3", "R5", "R4"])
    print(f"  {live['narrative'][:150]}")
    check("near-miss corpus loaded", pats.n >= 10, f"{pats.n} records")
    check("isolation-omitted is a recurring factor (>=3 records)",
          pats.factor_counts["isolation_omitted"] >= 3,
          str(pats.factor_counts["isolation_omitted"]))
    check("the live 06:30 combination has historical precedent",
          live["precedent_count"] >= 3, f"{live['precedent_count']} records")
    prio = pats.prevention_priorities(["R1", "R3", "R5", "R4"])
    check("top prevention priority is active now and carries a citation",
          prio[0]["active_now"] and prio[0]["regulatory_basis"]["standard"] != "—",
          prio[0]["label"][:48])

    print("\n== compliance audit agent ==")
    from app.risk.compliance import get_compliance
    cv = get_compliance("vizag_replay").audit_run()
    cn = get_compliance("normal_day").audit_run()
    print(f"  incident day: {cv['findings_total']} findings "
          f"({cv['critical']} critical) | normal day: {cn['findings_total']}")
    check("incident-day audit flags the missing isolation as critical",
          any(f["check_id"] == "CSE-ISO" and f["severity"] == "critical"
              for f in cv["findings"]))
    check("incident-day audit flags the single-point gas test",
          any(f["check_id"] == "CSE-GASREP" for f in cv["findings"]))
    check("incident-day audit flags the hot-work SIMOPS conflict",
          any(f["check_id"] == "HW-SIMOPS" for f in cv["findings"]))
    check("every finding carries a corrective action and an owner",
          all(f["corrective_action"] and f["owner"] for f in cv["findings"]))
    check("a CAPA register is generated", len(cv["capa_register"]) == cv["findings_total"])
    check("correctly-run permits produce ZERO findings (no false findings)",
          cn["findings_total"] == 0, f"normal day: {cn['findings_total']}")

    print("\n== knowledge graph ==")
    from app.risk.graph import get_graph
    kg = get_graph("vizag_replay")
    gs = kg.summary()
    sub = kg.subgraph_for_alert("cob4_basement", 270)
    print(f"  {gs['nodes_total']} nodes / {gs['edges_total']} edges; "
          f"alert subgraph {sub['node_count']}/{sub['edge_count']}")
    check("graph covers zones, equipment, sensors, permits, rules, regulations",
          all(gs["nodes_by_type"].get(k, 0) > 0
              for k in ("zone", "equipment", "sensor", "permit", "rule", "regulation")))
    check("alert subgraph implicates the confined-space permit",
          any(n["id"] == "permit:CSE-2093" for n in sub["nodes"]))
    check("alert subgraph carries the rules that fired",
          set(sub["rules_fired"]) >= {"R1", "R3"}, str(sub["rules_fired"]))
    check("alert subgraph reaches the governing regulations",
          any(n["type"] == "regulation" for n in sub["nodes"]))

    print("\n== held-out evaluation (scenarios the rules never saw) ==")
    # A fast slice runs here so regressions are caught on every commit; the full
    # distribution is `python eval_run.py 120`. These two properties are the ones
    # held-out testing originally broke, so they are the ones worth locking down.
    from app.eval.harness import run as _mc
    mc = _mc(n=24, start_seed=1000)
    print(f"  {mc['n']} generated ({mc['hazard_scenarios']} hazard / "
          f"{mc['benign_scenarios']} benign) | KAVACH detected "
          f"{mc['kavach_detection_rate_pct']}% | median lead "
          f"{mc['lead_time'].get('median')} min | false alerts on benign "
          f"{mc['kavach_false_alert_rate_pct']}%")
    check("KAVACH detects every hazard in the held-out sample",
          mc["kavach_detection_rate_pct"] == 100.0,
          f"{mc['kavach_detection_rate_pct']}%")
    check("no false alerts on unseen benign scenarios",
          mc["kavach_false_alert_rate_pct"] == 0.0,
          f"{mc['kavach_false_alert_rate_pct']}%")
    check("median lead time on unseen hazards is materially positive",
          (mc["lead_time"].get("median") or 0) >= 40,
          f"{mc['lead_time'].get('median')} min")
    check("KAVACH beats the baseline in the large majority of unseen hazards",
          mc["kavach_wins"] >= 0.8 * max(1, mc["hazard_scenarios"]),
          f"{mc['kavach_wins']}/{mc['hazard_scenarios']}")


if __name__ == "__main__":
    sys.exit(main())
