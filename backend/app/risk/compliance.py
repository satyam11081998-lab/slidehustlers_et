"""
KAVACH — Quality & Compliance Audit Agent
=========================================

The problem statement asks for a layer that "continuously monitors safety
procedures, inspection records, and statutory compliance documentation against
regulatory standards (OISD, DGMS, Factory Act) — flagging deviations before
audits and generating corrective action workflows automatically."

The distinction from the compound-risk engine matters. The risk engine asks
*"is this combination dangerous right now?"*. This agent asks a different and
complementary question: *"is this permit compliant with the standard, whether
or not anything has gone wrong yet?"* — which is what an inspector asks.

A deviation here is not necessarily a hazard. It is a gap between what the
statute requires and what the record shows, and it is exactly what turns into
a finding at audit. Each deviation carries a severity, the governing clause,
and a corrective action (CAPA) with an owner — so the output is a workflow,
not a complaint.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.simulator.engine import get_timeline

# Requirements are expressed per permit type, each traceable to a clause.
CHECKS: dict[str, list[dict]] = {
    "Confined Space Entry": [
        {"id": "CSE-ISO", "requirement": "Positive isolation of connected gas mains applied and certified before entry",
         "standard": "OISD-STD-105", "clause": "Work permit system — isolation before vessel/confined-space entry",
         "severity": "critical",
         "capa": "Suspend entry. Apply and certify gas-main isolation. Re-issue the permit only after isolation sign-off.",
         "owner": "Shift Supervisor / Safety Officer"},
        {"id": "CSE-GASREP", "requirement": "Gas test representative of the whole volume (multi-point), not entrance only",
         "standard": "Factories Act 1948", "clause": "S.36(2) — testing before entry into a confined space",
         "severity": "high",
         "capa": "Re-test at entrance, mid-chamber and rear by a competent person; record all points on the permit.",
         "owner": "Competent Person (gas testing)"},
        {"id": "CSE-MONITOR", "requirement": "Continuous atmospheric monitoring for the duration of occupancy",
         "standard": "DGMS", "clause": "Continuous monitoring of gas-bearing areas",
         "severity": "high",
         "capa": "Issue a continuous personal monitor to the entry crew and log readings at fixed intervals.",
         "owner": "Entry Supervisor"},
    ],
    "Hot Work": [
        {"id": "HW-GAS", "requirement": "Gas test immediately before work and proximity clearance from gas-bearing areas",
         "standard": "OISD-STD-105", "clause": "Hot work permit — gas testing and proximity controls",
         "severity": "high",
         "capa": "Re-test at the work location; establish a clearance distance from vents and connected openings.",
         "owner": "Fire Watch / Safety Officer"},
        {"id": "HW-SIMOPS", "requirement": "No conflicting simultaneous operations in connected zones",
         "standard": "OISD-STD-105", "clause": "Control of simultaneous operations (SIMOPS)",
         "severity": "critical",
         "capa": "Cross-check all active permits in connected zones; reschedule the conflicting activity.",
         "owner": "Permit Issuing Authority"},
    ],
}


class ComplianceAgent:
    """Audits live permits against statutory requirements, continuously."""

    def __init__(self, scenario_id: str) -> None:
        self.scenario = scenario_id
        self.tl = get_timeline(scenario_id)
        self.zones = {z["id"]: z for z in self.tl.plant["zones"]}
        self.adj = self._adjacency()

    def _adjacency(self) -> dict[str, set[str]]:
        adj: dict[str, set[str]] = {z["id"]: set(z.get("connections", []))
                                    for z in self.tl.plant["zones"]}
        norm = {}
        for k, v in adj.items():
            norm[k] = {c.replace("cob4_basement_vent", "cob4_basement") for c in v}
        for k, v in list(norm.items()):        # make symmetric
            for c in v:
                norm.setdefault(c, set()).add(k)
        return norm

    # ------------------------------------------------------------ auditing
    def _isolation_applied(self, permit: dict) -> bool:
        """True only if a *gas* isolation is recorded as actually applied.

        Matches the stem 'isolat' so that both "isolation applied" and "leg
        confirmed isolated and purged" count — an earlier version keyed on the
        exact word "isolation" and therefore flagged a correctly-isolated
        permit, which is precisely the kind of false finding that destroys an
        auditor's trust in the tool.
        """
        for item in permit.get("isolations", []):
            s = item.lower()
            if "isolat" in s and "gas" in s and "not applied" not in s:
                return True
        return False

    def _gas_test_multipoint(self, permit: dict) -> bool:
        gt = permit.get("gas_test") or {}
        detail = (gt.get("detail") or "").lower()
        return "multi-point" in detail or ("mid-chamber" in detail and "rear" in detail)

    def _continuous_monitor(self, permit: dict) -> bool:
        gt = permit.get("gas_test") or {}
        return "continuous" in (gt.get("detail") or "").lower()

    def _simops_conflict(self, permit: dict, active: list[dict]) -> list[str]:
        zone = permit["zone"]
        neighbours = self.adj.get(zone, set()) | {zone}
        return [p["id"] for p in active
                if p["id"] != permit["id"] and p["zone"] in neighbours]

    def audit_at(self, t: int) -> dict[str, Any]:
        state = self.tl.state_at(t)
        active = [p for p in state["permits"] if p["active"]]
        deviations: list[dict] = []

        for permit in active:
            for chk in CHECKS.get(permit["type"], []):
                ok = True
                observed = ""
                if chk["id"] == "CSE-ISO":
                    ok = self._isolation_applied(permit)
                    observed = "; ".join(permit.get("isolations", [])) or "none recorded"
                elif chk["id"] == "CSE-GASREP":
                    ok = self._gas_test_multipoint(permit)
                    observed = ((permit.get("gas_test") or {}).get("detail")
                                or "no gas test recorded")
                elif chk["id"] == "CSE-MONITOR":
                    ok = self._continuous_monitor(permit)
                    observed = ((permit.get("gas_test") or {}).get("detail")
                                or "no monitoring recorded")
                elif chk["id"] == "HW-GAS":
                    ok = bool(permit.get("gas_test"))
                    observed = ((permit.get("gas_test") or {}).get("detail")
                                or "no gas test recorded")
                elif chk["id"] == "HW-SIMOPS":
                    conflicts = self._simops_conflict(permit, active)
                    ok = not conflicts
                    observed = ("conflicting permits in connected zones: "
                                + ", ".join(conflicts)) if conflicts else "no conflicts"
                if not ok:
                    deviations.append({
                        "check_id": chk["id"], "permit": permit["id"],
                        "permit_type": permit["type"], "zone": permit["zone"],
                        "requirement": chk["requirement"], "observed": observed,
                        "severity": chk["severity"],
                        "regulatory_basis": {"standard": chk["standard"], "clause": chk["clause"]},
                        "corrective_action": chk["capa"], "owner": chk["owner"],
                        "raised_at": t, "raised_clock": self.tl.clock(t),
                    })

        checks_run = sum(len(CHECKS.get(p["type"], [])) for p in active)
        passed = checks_run - len(deviations)
        return {
            "scenario": self.scenario, "t": t, "clock": self.tl.clock(t),
            "active_permits": [p["id"] for p in active],
            "checks_run": checks_run, "checks_passed": passed,
            "compliance_pct": round(100.0 * passed / checks_run, 1) if checks_run else 100.0,
            "deviation_count": len(deviations),
            "critical_deviations": sum(1 for d in deviations if d["severity"] == "critical"),
            "deviations": deviations,
        }

    def audit_run(self, step: int = 5) -> dict[str, Any]:
        """Sweep the whole scenario — 'flagging deviations before audits'."""
        first_seen: dict[str, dict] = {}
        for t in range(0, self.tl.duration + 1, step):
            for d in self.audit_at(t)["deviations"]:
                key = f"{d['permit']}::{d['check_id']}"
                if key not in first_seen:
                    first_seen[key] = d
        findings = sorted(first_seen.values(), key=lambda d: d["raised_at"])
        return {
            "scenario": self.scenario,
            "findings_total": len(findings),
            "critical": sum(1 for d in findings if d["severity"] == "critical"),
            "high": sum(1 for d in findings if d["severity"] == "high"),
            "findings": findings,
            "capa_register": [
                {"id": f"CAPA-{i+1:03d}", "finding": d["check_id"], "permit": d["permit"],
                 "action": d["corrective_action"], "owner": d["owner"],
                 "severity": d["severity"], "raised_clock": d["raised_clock"],
                 "regulatory_basis": d["regulatory_basis"]}
                for i, d in enumerate(findings)
            ],
        }


@lru_cache(maxsize=8)
def get_compliance(scenario_id: str) -> ComplianceAgent:
    return ComplianceAgent(scenario_id)
