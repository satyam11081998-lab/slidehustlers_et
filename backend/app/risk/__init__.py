"""
KAVACH — Risk Intelligence package
==================================

The "brain" that sits on top of the deterministic digital twin
(``app.simulator.engine``) and turns raw sensor streams + operational
context into *compound* risk intelligence.

Modules
-------
* ``signals``  — derived signals (trend slope, EWMA deviation, sub-threshold
  drift, cross-channel corroboration, valve/back-pressure correlation).
* ``baseline`` — a naive single-sensor threshold alarm system, used as the
  side-by-side comparator the evaluation explicitly asks us to beat.
* ``compound`` — the CompoundRiskEngine: context-aware rules (R1–R8) that
  fuse signals + permits + work orders + shift + plant connectivity into
  zone risk scores and evidence-carrying alerts.
* ``metrics``  — the MetricsLab: runs both engines over a whole scenario and
  scores them against ground truth (lead time, false negatives, false
  positives, per-rule contributions).
* ``explain``  — optional LLM alert narration with a deterministic template
  fallback (the demo never depends on a network call).

Everything here is deterministic: same scenario in, same numbers out, on
every machine. The LLM layer is a strictly optional garnish.
"""

from app.risk.baseline import BaselineAlarm, SingleSensorBaseline
from app.risk.compound import CompoundRiskEngine, get_risk_engine
from app.risk.metrics import MetricsLab, compute_metrics
from app.risk.signals import ScenarioSignals, get_signals

__all__ = [
    "BaselineAlarm",
    "SingleSensorBaseline",
    "CompoundRiskEngine",
    "get_risk_engine",
    "MetricsLab",
    "compute_metrics",
    "ScenarioSignals",
    "get_signals",
]
