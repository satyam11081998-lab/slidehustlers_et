"""
KAVACH — Equipment / Permit / Risk Knowledge Graph
==================================================

The problem statement suggests knowledge graphs over "equipment-permit-risk
relationships". This module builds exactly that, from the same source data the
engines use — so the graph is not a decorative diagram, it is the reasoning
substrate rendered explicit.

Node types:  zone · equipment · sensor · permit · work_order · rule · regulation
Edge types:  connects_to · located_in · monitors · authorises · performed_on ·
             fired_in · cites · implicates

The graph answers the question an investigator actually asks — *"what is
connected to this alert, and through what?"* — by returning the subgraph
reachable from a zone at a given minute. That is the difference between a list
of coincidences and a causal account.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.risk.compound import get_risk_engine
from app.simulator.engine import get_timeline

RULE_LABELS = {
    "R1": "Gas trend in occupied confined space",
    "R2": "Hot work adjacent to rising gas",
    "R3": "Confined entry without gas-main isolation",
    "R4": "Shift-handover blindspot",
    "R5": "Single-point gas test",
    "R6": "Valve back-pressure with occupied space",
    "R7": "Multi-channel corroboration",
    "R8": "Calibration suppression",
}
RULE_REGS = {
    "R1": ["DGMS — continuous monitoring of gas-bearing areas"],
    "R2": ["OISD-STD-105 — hot work permit, proximity controls"],
    "R3": ["OISD-STD-105 — isolation before confined-space entry",
           "Factories Act 1948, S.36(2)"],
    "R4": ["OISD-STD-105 — shift handover and permit continuity"],
    "R5": ["Factories Act 1948, S.36(2) — testing before entry"],
    "R6": ["OISD-STD-105 — coordination of isolation and maintenance"],
}


class KnowledgeGraph:
    def __init__(self, scenario_id: str) -> None:
        self.scenario = scenario_id
        self.tl = get_timeline(scenario_id)
        self.eng = get_risk_engine(scenario_id)
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self._build_static()

    # ------------------------------------------------------------- builders
    def _node(self, nid: str, ntype: str, label: str, **attrs) -> None:
        self.nodes[nid] = {"id": nid, "type": ntype, "label": label, **attrs}

    def _edge(self, src: str, rel: str, dst: str, **attrs) -> None:
        self.edges.append({"source": src, "rel": rel, "target": dst, **attrs})

    def _build_static(self) -> None:
        plant = self.tl.plant
        for z in plant["zones"]:
            self._node(f"zone:{z['id']}", "zone", z["name"],
                       hazard_class=z.get("hazard_class"))
        for z in plant["zones"]:
            for c in z.get("connections", []):
                c = c.replace("cob4_basement_vent", "cob4_basement")
                if f"zone:{c}" in self.nodes:
                    self._edge(f"zone:{z['id']}", "connects_to", f"zone:{c}")
        for e in plant.get("equipment", []):
            self._node(f"equip:{e['id']}", "equipment", e["name"], kind=e.get("type"))
            self._edge(f"equip:{e['id']}", "located_in", f"zone:{e['zone']}")
        for s in plant["sensors"]:
            self._node(f"sensor:{s['id']}", "sensor", s["name"],
                       kind=s["kind"], unit=s["unit"], limits=s.get("limits"))
            self._edge(f"sensor:{s['id']}", "monitors", f"zone:{s['zone']}")
            if s.get("equipment"):
                self._edge(f"sensor:{s['id']}", "monitors", f"equip:{s['equipment']}")
        for p in self.tl.permits:
            self._node(f"permit:{p['id']}", "permit", f"{p['id']} — {p['type']}",
                       ptype=p["type"], crew=len(p.get("crew", [])),
                       window=[p["from"], p["to"]],
                       isolations=p.get("isolations", []))
            self._edge(f"permit:{p['id']}", "authorises", f"zone:{p['zone']}")
        for w in self.tl.work_orders:
            self._node(f"wo:{w['id']}", "work_order", f"{w['id']} — {w['title']}",
                       kind=w.get("kind"))
            self._edge(f"wo:{w['id']}", "performed_on", f"zone:{w['zone']}")
        for rid, label in RULE_LABELS.items():
            self._node(f"rule:{rid}", "rule", f"{rid} — {label}")
            for reg in RULE_REGS.get(rid, []):
                self._node(f"reg:{reg}", "regulation", reg)
                self._edge(f"rule:{rid}", "cites", f"reg:{reg}")

    # -------------------------------------------------------------- queries
    def neighbours(self, nid: str) -> list[dict]:
        return [e for e in self.edges if e["source"] == nid or e["target"] == nid]

    def subgraph_for_alert(self, zone: str, t: int) -> dict[str, Any]:
        """Everything implicated in the risk at this zone and minute.

        This is the investigator's view: the zone, what physically connects to
        it, the instruments watching it, the permits and work orders in force,
        the rules that fired, and the regulations those rules cite.
        """
        st = self.eng.state_at(t)
        zinfo = st["zones"].get(zone, {})
        rules = []
        for a in st.get("active_alerts", []):
            if a.get("zone") == zone:
                rules = [r.get("id") if isinstance(r, dict) else r
                         for r in a.get("rules", [])]
        keep = {f"zone:{zone}"}
        for e in self.edges:                       # 1-hop physical neighbourhood
            if e["source"] == f"zone:{zone}" and e["rel"] == "connects_to":
                keep.add(e["target"])
            if e["target"] == f"zone:{zone}" and e["rel"] == "connects_to":
                keep.add(e["source"])
        zone_ids = {n.split(":", 1)[1] for n in keep if n.startswith("zone:")}
        for n in self.nodes.values():              # attach what lives there
            if n["type"] == "sensor":
                for e in self.edges:
                    if (e["source"] == n["id"] and e["rel"] == "monitors"
                            and e["target"] in keep):
                        keep.add(n["id"])
            elif n["type"] in ("permit", "work_order", "equipment"):
                for e in self.edges:
                    if e["source"] == n["id"] and e["target"] in keep:
                        active = True
                        if n["type"] == "permit":
                            w = n.get("window") or [0, 10 ** 9]
                            active = w[0] <= t < w[1]
                        if active:
                            keep.add(n["id"])
        for rid in rules:                           # the reasoning itself
            if f"rule:{rid}" in self.nodes:
                keep.add(f"rule:{rid}")
                self._edge_once(f"rule:{rid}", "fired_in", f"zone:{zone}")
                for e in self.edges:
                    if e["source"] == f"rule:{rid}" and e["rel"] == "cites":
                        keep.add(e["target"])
        nodes = [self.nodes[n] for n in keep if n in self.nodes]
        edges = [e for e in self.edges
                 if e["source"] in keep and e["target"] in keep]
        return {
            "scenario": self.scenario, "t": t, "clock": self.tl.clock(t),
            "focus_zone": zone, "zone_score": zinfo.get("score"),
            "zone_band": zinfo.get("band_name"),
            "rules_fired": rules,
            "node_count": len(nodes), "edge_count": len(edges),
            "nodes": nodes, "edges": edges,
        }

    def _edge_once(self, src: str, rel: str, dst: str) -> None:
        if not any(e["source"] == src and e["rel"] == rel and e["target"] == dst
                   for e in self.edges):
            self._edge(src, rel, dst)

    def summary(self) -> dict[str, Any]:
        by_type: dict[str, int] = {}
        for n in self.nodes.values():
            by_type[n["type"]] = by_type.get(n["type"], 0) + 1
        rels: dict[str, int] = {}
        for e in self.edges:
            rels[e["rel"]] = rels.get(e["rel"], 0) + 1
        return {"scenario": self.scenario, "nodes_total": len(self.nodes),
                "edges_total": len(self.edges),
                "nodes_by_type": by_type, "edges_by_relation": rels}


@lru_cache(maxsize=8)
def get_graph(scenario_id: str) -> KnowledgeGraph:
    return KnowledgeGraph(scenario_id)
