"""
KAVACH — Incident Pattern Intelligence
======================================

The problem statement asks for an agent that "cross-references near-miss
reports, historical incident data, and OISD/Factory Act regulatory guidance to
identify recurring patterns that manual investigations miss — and surfaces them
as actionable prevention priorities."

That is what this module does, and it makes one uncomfortable point very
concretely: **the accident was already written in the plant's own near-miss
register.** Isolation omitted during a confined-space entry appears three times
in twenty-four months. A single-point gas test appears twice. A drift carried
across a handover appears twice. Nobody connected them, because near-misses are
filed and closed one at a time.

Method (deterministic, no model required):

* **frequency** — how often each contributing factor recurs in the register;
* **co-occurrence** — which factors keep arriving together, scored by lift over
  what independence would predict, which is where the compound pattern shows up;
* **live correlation** — whether the factors of a currently active alert match a
  recurring historical pattern, which turns history into a present-tense warning;
* **prevention priorities** — factors ranked by recurrence and by whether they
  are implicated in the live rule set, each carrying its regulatory basis.

Retrieval is frequency-based rather than embedding-based on purpose: it is
reproducible, needs no API key, and an auditor can recompute it by hand.
"""

from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from itertools import combinations
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[3] / "data"

# Which historical factor each live compound rule is evidence of. This is the
# join between "what is happening now" and "what has happened before".
RULE_TO_FACTOR = {
    "R1": "gas_trend_ignored",
    "R2": "hot_work_proximity",
    "R3": "isolation_omitted",
    "R4": "handover_gap",
    "R5": "single_point_gas_test",
    "R6": "valve_operation_uncoordinated",
    "R7": "single_channel_reliance",
}

# Statutory hook for each factor, so a prevention priority is actionable.
FACTOR_TO_CLAUSE = {
    "isolation_omitted": ("OISD-STD-105", "Work permit system — isolation before entry"),
    "confined_space_entry": ("Factories Act 1948", "S.36(2) — entry into confined spaces"),
    "single_point_gas_test": ("Factories Act 1948", "S.36(2) — testing before entry"),
    "stale_gas_test": ("OISD-STD-105", "Gas test validity before entry"),
    "gas_trend_ignored": ("DGMS", "Continuous monitoring of gas-bearing areas"),
    "single_channel_reliance": ("DGMS", "Gas testing by competent persons"),
    "handover_gap": ("OISD-STD-105", "Shift handover and permit continuity"),
    "hot_work_proximity": ("OISD-STD-105", "Hot work permit — proximity controls"),
    "permit_overlap": ("OISD-STD-105", "Simultaneous operations control"),
    "valve_operation_uncoordinated": ("OISD-STD-105", "Coordination of isolation and maintenance"),
    "sub_threshold_drift": ("DGMS", "Trend review of process parameters"),
    "regulator_passing": ("OISD-STD-105", "Maintenance of pressure control devices"),
    "deferred_maintenance": ("Factories Act 1948", "Duty to maintain plant in safe condition"),
}


class PatternIntelligence:
    def __init__(self) -> None:
        raw = json.loads((DATA_DIR / "incidents" / "near_misses.json").read_text(encoding="utf-8"))
        self.records: list[dict] = raw["records"]
        self.labels: dict[str, str] = raw["factor_labels"]
        self.n = len(self.records)

    # ------------------------------------------------------------ frequency
    @property
    def factor_counts(self) -> Counter:
        c: Counter = Counter()
        for r in self.records:
            c.update(r["factors"])
        return c

    # -------------------------------------------------------- co-occurrence
    def co_occurrence(self, min_support: int = 2) -> list[dict]:
        """Factor pairs that recur together, ranked by lift.

        Lift > 1 means the pair arrives together more often than chance would
        predict — i.e. it is a *pattern*, not a coincidence. This is precisely
        the signal a one-report-at-a-time review cannot see.
        """
        pair_counts: Counter = Counter()
        for r in self.records:
            for a, b in combinations(sorted(set(r["factors"])), 2):
                pair_counts[(a, b)] += 1
        fc = self.factor_counts
        out = []
        for (a, b), n in pair_counts.items():
            if n < min_support:
                continue
            expected = (fc[a] / self.n) * (fc[b] / self.n) * self.n
            lift = round(n / expected, 2) if expected else 0.0
            out.append({
                "factors": [a, b],
                "labels": [self.labels.get(a, a), self.labels.get(b, b)],
                "count": n,
                "support_pct": round(100.0 * n / self.n, 1),
                "lift": lift,
                "records": [r["id"] for r in self.records
                            if a in r["factors"] and b in r["factors"]],
            })
        out.sort(key=lambda d: (-d["count"], -d["lift"]))
        return out

    # ---------------------------------------------------- live correlation
    def match_live(self, rules: list[str]) -> dict[str, Any]:
        """Given the rules firing right now, find the historical precedent."""
        live_factors = [RULE_TO_FACTOR[r] for r in rules if r in RULE_TO_FACTOR]
        precedents = []
        for r in self.records:
            overlap = sorted(set(live_factors) & set(r["factors"]))
            if overlap:
                precedents.append({
                    "id": r["id"], "date": r["date"], "zone": r["zone"],
                    "type": r["type"], "title": r["title"],
                    "shared_factors": overlap,
                    "match_strength": round(len(overlap) / max(1, len(set(live_factors))), 2),
                })
        precedents.sort(key=lambda d: (-d["match_strength"], d["date"]))
        return {
            "live_factors": live_factors,
            "live_factor_labels": [self.labels.get(f, f) for f in live_factors],
            "precedent_count": len(precedents),
            "precedents": precedents[:6],
            "narrative": self._narrative(live_factors, precedents),
        }

    def _narrative(self, live_factors: list[str], precedents: list[dict]) -> str:
        if not precedents:
            return "No historical precedent for this combination in the register."
        exact = [p for p in precedents if p["match_strength"] >= 0.5]
        fc = self.factor_counts
        top = max(live_factors, key=lambda f: fc[f]) if live_factors else None
        bits = [f"{len(precedents)} record(s) in the plant's own register share factors "
                f"with the condition now active"]
        if top:
            bits.append(f"'{self.labels.get(top, top)}' has recurred {fc[top]} times "
                        f"in {self.n} records")
        if exact:
            bits.append(f"the closest precedent is {exact[0]['id']} ({exact[0]['date']}, "
                        f"{exact[0]['title']})")
        return "; ".join(bits) + "."

    # ------------------------------------------------- prevention priorities
    def prevention_priorities(self, live_rules: list[str] | None = None) -> list[dict]:
        live_factors = {RULE_TO_FACTOR[r] for r in (live_rules or []) if r in RULE_TO_FACTOR}
        fc = self.factor_counts
        out = []
        for factor, count in fc.most_common():
            std, clause = FACTOR_TO_CLAUSE.get(factor, ("—", "—"))
            active = factor in live_factors
            # recurrence drives the ranking; an active factor is escalated,
            # because a historical pattern that is happening right now is not a
            # statistic any more.
            score = count * (2.0 if active else 1.0)
            out.append({
                "factor": factor,
                "label": self.labels.get(factor, factor),
                "occurrences": count,
                "recurrence_pct": round(100.0 * count / self.n, 1),
                "active_now": active,
                "priority_score": round(score, 1),
                "regulatory_basis": {"standard": std, "clause": clause},
                "records": [r["id"] for r in self.records if factor in r["factors"]],
            })
        out.sort(key=lambda d: (-d["priority_score"], -d["occurrences"]))
        return out

    def summary(self, live_rules: list[str] | None = None) -> dict[str, Any]:
        return {
            "corpus_size": self.n,
            "factor_frequency": [
                {"factor": f, "label": self.labels.get(f, f), "count": c}
                for f, c in self.factor_counts.most_common()
            ],
            "recurring_combinations": self.co_occurrence(),
            "prevention_priorities": self.prevention_priorities(live_rules),
            "live_match": self.match_live(live_rules or []),
        }


@lru_cache(maxsize=1)
def get_patterns() -> PatternIntelligence:
    return PatternIntelligence()
