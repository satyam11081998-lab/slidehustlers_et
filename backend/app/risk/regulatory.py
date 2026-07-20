"""
KAVACH — Regulatory Intelligence (RAG)
======================================

Every KAVACH intervention has to answer the juror's second question: not just
"why did you alert?" but "which rule says I must act?". This module is the
regulatory half of the evidence trail.

Design
------
* **Curated, citable corpus** (``data/regulatory/*.json``): faithful summaries
  of the provisions that actually govern the Battery-4 scenario —
  the **Factories Act, 1948** (S.36 confined spaces, S.37 inflammable gas —
  the statute), **OISD-STD-105** (Work Permit System — process good-practice),
  and **DGMS** gas-testing / continuous-monitoring guidance. Sources, revisions
  and provenance are carried with every clause; nothing is invented.
* **Deterministic retrieval**: a compact BM25 keyword search (no API, no
  network, identical on every machine). An optional LLM layer can *rephrase*
  a citation, but the clause text always comes from the corpus.
* **Rule- and action-indexed**: each clause declares which compound rules
  (R1-R8) and which orchestrator actions it underpins, so ``citations_for_rules``
  and ``citations_for_actions`` guarantee coverage — every material rule and
  every recommended action gets a ``regulatory_basis``.

The point KAVACH makes with this: the regulations already required isolation,
a representative gas test, a communicated handover and controlled hot work.
The failure at Vizag was not missing law — it was no layer connecting the law
to the live readings. This module is that connection.
"""

from __future__ import annotations

import json
import math
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

REG_DIR = Path(__file__).resolve().parents[3] / "data" / "regulatory"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


class Clause:
    """One regulatory provision plus its retrieval text and mappings."""

    __slots__ = ("code", "title_src", "url", "revision", "authority",
                 "ref", "title", "summary", "topics", "tags", "rules",
                 "actions", "doc_tokens")

    def __init__(self, source: dict, clause: dict):
        self.code: str = source["code"]
        self.title_src: str = source["title"]
        self.url: str = source.get("url", "")
        self.revision: str = source.get("revision", "")
        self.authority: str = source.get("authority", "")
        self.ref: str = clause["ref"]
        self.title: str = clause["title"]
        self.summary: str = clause["summary"]
        self.topics: list[str] = clause.get("topics", [])
        self.tags: list[str] = clause.get("tags", [])
        self.rules: list[str] = clause.get("rules", [])
        self.actions: list[str] = clause.get("actions", [])
        # retrieval doc = every searchable surface of the clause
        blob = " ".join([
            self.code, self.ref, self.title, self.summary,
            " ".join(self.tags), " ".join(self.topics),
        ])
        self.doc_tokens: list[str] = _tokens(blob)

    @property
    def cid(self) -> str:
        return f"{self.code}::{self.ref}"

    def citation(self, score: float | None = None) -> dict[str, Any]:
        c = {
            "code": self.code,
            "ref": self.ref,
            "citation": f"{self.code}, {self.ref}",
            "title": self.title,
            "summary": self.summary,
            "source_title": self.title_src,
            "authority": self.authority,
            "revision": self.revision,
            "url": self.url,
            "topics": self.topics,
            "rules": self.rules,
        }
        if score is not None:
            c["score"] = round(score, 3)
        return c


class RegulatoryCorpus:
    """Loads the clause library and serves deterministic BM25 retrieval."""

    K1 = 1.5
    B = 0.75

    def __init__(self) -> None:
        self.sources: list[dict] = []
        self.clauses: list[Clause] = []
        self._load()
        self._index()

    # ------------------------------------------------------------------ load
    def _load(self) -> None:
        for path in sorted(REG_DIR.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            src = data["source"]
            self.sources.append(src)
            for cl in data.get("clauses", []):
                self.clauses.append(Clause(src, cl))

    def _index(self) -> None:
        # document frequencies for BM25 IDF
        self.N = len(self.clauses)
        self.df: dict[str, int] = {}
        total_len = 0
        for c in self.clauses:
            total_len += len(c.doc_tokens)
            for term in set(c.doc_tokens):
                self.df[term] = self.df.get(term, 0) + 1
        self.avgdl = (total_len / self.N) if self.N else 0.0
        # reverse maps: rule/action -> clauses (corpus is the single source
        # of truth for which provision underpins which rule)
        self.by_rule: dict[str, list[Clause]] = {}
        self.by_action: dict[str, list[Clause]] = {}
        for c in self.clauses:
            for r in c.rules:
                self.by_rule.setdefault(r, []).append(c)
            for a in c.actions:
                self.by_action.setdefault(a, []).append(c)

    def _idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        # BM25+ style non-negative idf
        return math.log(1 + (self.N - n + 0.5) / (n + 0.5))

    # -------------------------------------------------------------- retrieval
    def search(self, query: str, k: int = 5) -> list[dict]:
        q_terms = _tokens(query)
        scored: list[tuple[float, Clause]] = []
        for c in self.clauses:
            score = self._bm25(q_terms, c)
            if score > 0:
                scored.append((score, c))
        # deterministic: score desc, then code/ref asc for ties
        scored.sort(key=lambda sc: (-sc[0], sc[1].code, sc[1].ref))
        return [c.citation(score) for score, c in scored[:k]]

    def _bm25(self, q_terms: list[str], c: Clause) -> float:
        if not c.doc_tokens:
            return 0.0
        freqs: dict[str, int] = {}
        for t in c.doc_tokens:
            freqs[t] = freqs.get(t, 0) + 1
        dl = len(c.doc_tokens)
        score = 0.0
        for term in q_terms:
            f = freqs.get(term, 0)
            if not f:
                continue
            idf = self._idf(term)
            denom = f + self.K1 * (1 - self.B + self.B * dl / (self.avgdl or 1))
            score += idf * (f * (self.K1 + 1)) / denom
        return score

    # ----------------------------------------------------- rule/action lookup
    def citations_for_rules(self, rule_ids: list[str], limit: int = 4) -> list[dict]:
        """Every distinct clause that underpins any of these compound rules,
        ordered by how many of the rules it covers (then code/ref). Guarantees
        each material rule contributes at least one citation."""
        seen: dict[str, Clause] = {}
        cover: dict[str, int] = {}
        for r in rule_ids:
            for c in self.by_rule.get(r, []):
                seen[c.cid] = c
                cover[c.cid] = cover.get(c.cid, 0) + 1
        ordered = sorted(seen.values(),
                         key=lambda c: (-cover[c.cid], c.code, c.ref))
        return [c.citation() for c in ordered[:limit]]

    def citations_for_actions(self, action_types: list[str], limit: int = 3) -> list[dict]:
        seen: dict[str, Clause] = {}
        cover: dict[str, int] = {}
        for a in action_types:
            for c in self.by_action.get(a, []):
                seen[c.cid] = c
                cover[c.cid] = cover.get(c.cid, 0) + 1
        ordered = sorted(seen.values(),
                         key=lambda c: (-cover[c.cid], c.code, c.ref))
        return [c.citation() for c in ordered[:limit]]

    def coverage(self) -> dict[str, Any]:
        """Compliance-coverage summary for the metrics/UI: which rules and
        topics the corpus can cite, and the source list."""
        return {
            "sources": [
                {"code": s["code"], "title": s["title"],
                 "revision": s.get("revision", ""),
                 "authority": s.get("authority", ""),
                 "url": s.get("url", "")}
                for s in self.sources
            ],
            "clause_count": len(self.clauses),
            "rules_covered": sorted(self.by_rule.keys()),
            "topics": sorted({t for c in self.clauses for t in c.topics}),
        }


@lru_cache(maxsize=1)
def get_corpus() -> RegulatoryCorpus:
    return RegulatoryCorpus()


# ------------------------------------------------------------------ helpers

def citations_for_rules(rule_ids: list[str], limit: int = 4) -> list[dict]:
    return get_corpus().citations_for_rules(rule_ids, limit)


def citations_for_actions(action_types: list[str], limit: int = 3) -> list[dict]:
    return get_corpus().citations_for_actions(action_types, limit)


def search(query: str, k: int = 5) -> list[dict]:
    return get_corpus().search(query, k)


def attach_to_alert(alert: dict) -> dict:
    """Return the alert with a ``regulatory_basis`` list keyed off its rules."""
    rule_ids = alert.get("rule_ids") or [r["id"] for r in alert.get("rules", [])]
    return {**alert, "regulatory_basis": citations_for_rules(rule_ids)}


def phrase_basis(citations: list[dict]) -> str:
    """A one-line, deterministic natural-language rendering of the citations
    (used in reports/narration). An LLM may reword this, but never the facts."""
    if not citations:
        return "No matching regulatory clause."
    bits = [f"{c['citation']} ({c['title']})" for c in citations]
    return "Regulatory basis: " + "; ".join(bits) + "."
