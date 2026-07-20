"""
KAVACH — Single-Sensor Baseline
===============================

The comparator KAVACH is explicitly scored against. This models a
conventional plant alarm system: each sensor is watched *in isolation*
against its own threshold, with a short persistence filter to reject
transient spikes (real systems do this to cut nuisance trips). It has **no
operational context** — it doesn't know about permits, work orders, shift
handovers, or what neighbouring sensors are doing. That blindness is the
whole point: it is why real plants with working detectors still miss
compound hazards, and why it false-alarms on a calibration test it has no
way to explain.

Detection semantics
-------------------
* A sensor is "in alarm" at minute ``t`` when ``value >= alarm`` (or
  ``>= high``). We find contiguous alarm runs.
* A run shorter than ``PERSIST_MIN`` is a transient — emitted as
  ``cleared=True`` (self-cleared, no operator action needed).
* A run of ``PERSIST_MIN`` or longer is an **uncleared alarm** — the
  actionable event a control-room operator must respond to.

``first_uncleared`` is the moment a conventional system would first demand
attention. For the incident replay that is 09:40 (t≈460), a full **190
minutes after** KAVACH's compound alert. For the benign day it fires on the
calibration plateau — a textbook false positive KAVACH suppresses with
work-order context.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache

from app.simulator.engine import Timeline, get_timeline

PERSIST_MIN = 3  # an alarm must hold this many minutes to count as "uncleared"


@dataclass
class BaselineAlarm:
    t: int              # minute the alarm run began
    clock: str
    sensor: str
    name: str
    zone: str
    level: str          # "alarm" | "high"
    value: float        # peak value during the run
    duration: int       # run length in minutes
    cleared: bool       # True = transient (self-cleared), False = uncleared

    def to_dict(self) -> dict:
        return asdict(self)


class SingleSensorBaseline:
    """Naive per-sensor threshold detector over a whole scenario."""

    def __init__(self, scenario_id: str):
        self.tl: Timeline = get_timeline(scenario_id)
        self.scenario = scenario_id
        self._alarms: list[BaselineAlarm] = self._scan()

    def _scan(self) -> list[BaselineAlarm]:
        out: list[BaselineAlarm] = []
        for sid, meta in self.tl.sensors_meta.items():
            limits = meta.get("limits") or {}
            alarm = limits.get("alarm")
            if alarm is None:
                continue
            high = limits.get("high")
            series = self.tl.series[sid]

            t = 0
            n = len(series)
            while t < n:
                if series[t] >= alarm:
                    start = t
                    peak = series[t]
                    reached_high = high is not None and series[t] >= high
                    while t < n and series[t] >= alarm:
                        peak = max(peak, series[t])
                        if high is not None and series[t] >= high:
                            reached_high = True
                        t += 1
                    duration = t - start
                    out.append(
                        BaselineAlarm(
                            t=start,
                            clock=self.tl.clock(start),
                            sensor=sid,
                            name=meta["name"],
                            zone=meta["zone"],
                            level="high" if reached_high else "alarm",
                            value=round(peak, 2),
                            duration=duration,
                            cleared=duration < PERSIST_MIN,
                        )
                    )
                else:
                    t += 1
        out.sort(key=lambda a: a.t)
        return out

    # ---------------------------------------------------------------- queries

    def alarms(self) -> list[BaselineAlarm]:
        return list(self._alarms)

    def uncleared(self) -> list[BaselineAlarm]:
        return [a for a in self._alarms if not a.cleared]

    def first_uncleared(self) -> BaselineAlarm | None:
        for a in self._alarms:
            if not a.cleared:
                return a
        return None

    def active_at(self, t: int) -> list[BaselineAlarm]:
        """Alarms whose run covers minute t (for the live UI)."""
        return [a for a in self._alarms if a.t <= t < a.t + a.duration]

    def summary(self) -> dict:
        first = self.first_uncleared()
        return {
            "scenario": self.scenario,
            "total_alarms": len(self._alarms),
            "uncleared_count": len(self.uncleared()),
            "first_uncleared_t": first.t if first else None,
            "first_uncleared_clock": first.clock if first else None,
            "first_uncleared_sensor": first.sensor if first else None,
        }


@lru_cache(maxsize=8)
def get_baseline(scenario_id: str) -> SingleSensorBaseline:
    get_timeline(scenario_id)  # validate scenario exists
    return SingleSensorBaseline(scenario_id)
