"""
KAVACH — Derived Signals
========================

Turns each raw sensor stream into the *shape* features that compound-risk
rules reason over. A threshold alarm looks only at ``value >= limit`` at a
single instant; KAVACH looks at how a value is *moving* and whether several
channels are moving together — which is exactly what lets it see a hazard
build hours before any single sensor crosses a line.

For every sensor we pre-compute, at minute resolution:

* ``slope``   — rolling least-squares trend (units / minute) over a window.
* ``ewma``    — exponentially-weighted moving average, and the instantaneous
                deviation ``value - ewma`` (a spike / step detector).
* ``rising``  — a sustained, meaningful upward trend (noise-robust).
* ``drift``   — the KAVACH signature: a *sub-threshold* rising trend, i.e.
                the value is climbing steadily while still below its warn
                limit. This is the signal a threshold system cannot raise.

Zone-level roll-ups (cross-channel corroboration, valve/back-pressure
correlation) are also exposed. Everything is materialised once per scenario
and cached, so rule evaluation and the API stay O(1).
"""

from __future__ import annotations

from functools import lru_cache

from app.simulator.engine import Timeline, get_timeline

# --- tuning constants -------------------------------------------------------
# Windows are in minutes. Deltas are "how much the value must move across the
# window to count", expressed in each sensor's own engineering unit, chosen a
# little above the per-sensor noise band so trends are real, not jitter.

SLOPE_WINDOW = 45          # rolling trend window for "rising"
DRIFT_WINDOW = 60          # longer window for slow sub-threshold drift
EWMA_ALPHA = 0.08          # ~ last 25 min dominate the moving average

# Minimum rise across SLOPE_WINDOW for a channel to be "rising", by kind.
RISE_DELTA: dict[str, float] = {
    "pressure": 0.20,      # kPa
    "diff_pressure": 0.08,  # kPa
    "gas_co": 3.0,         # ppm
    "gas_h2s": 0.7,        # ppm
    "gas_ch4": 1.0,        # %LEL
    "flow": 400.0,         # Nm3/h
}

# Minimum rise across DRIFT_WINDOW for a *sub-threshold* drift, by kind.
DRIFT_DELTA: dict[str, float] = {
    "pressure": 0.15,      # kPa
    "diff_pressure": 0.06,
    "gas_co": 3.0,
    "gas_h2s": 0.6,
    "gas_ch4": 0.8,
}

GAS_KINDS = {"gas_co", "gas_h2s", "gas_ch4"}


def _slope(ys: list[float], i: int, window: int) -> float:
    """Least-squares slope (per minute) of ys over [i-window+1 .. i]."""
    lo = max(0, i - window + 1)
    n = i - lo + 1
    if n < 3:
        return 0.0
    sx = sy = sxx = sxy = 0.0
    for x in range(lo, i + 1):
        y = ys[x]
        sx += x
        sy += y
        sxx += x * x
        sxy += x * y
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0
    return (n * sxy - sx * sy) / denom


def _ewma(ys: list[float], alpha: float) -> list[float]:
    out: list[float] = []
    e = ys[0]
    for v in ys:
        e = alpha * v + (1 - alpha) * e
        out.append(e)
    return out


class ScenarioSignals:
    """All derived signals for one scenario, pre-materialised."""

    def __init__(self, scenario_id: str, tl: Timeline | None = None):
        # ``tl`` lets the what-if sandbox reuse a modified timeline instead of
        # the cached one.
        self.tl: Timeline = tl or get_timeline(scenario_id)
        self.scenario = scenario_id
        self.duration = self.tl.duration
        self.meta = self.tl.sensors_meta

        # zone -> sensor ids (from the authoritative plant layout)
        self.sensors_by_zone: dict[str, list[str]] = {}
        for sid, m in self.meta.items():
            self.sensors_by_zone.setdefault(m["zone"], []).append(sid)

        self.slope: dict[str, list[float]] = {}
        self.ewma: dict[str, list[float]] = {}
        self.rising: dict[str, list[bool]] = {}
        self.drift: dict[str, list[bool]] = {}
        self._build()

    def _build(self) -> None:
        for sid, m in self.meta.items():
            ys = self.tl.series[sid]
            kind = m["kind"]
            warn = (m.get("limits") or {}).get("warn")

            slope = [_slope(ys, t, SLOPE_WINDOW) for t in range(len(ys))]
            self.slope[sid] = slope
            self.ewma[sid] = _ewma(ys, EWMA_ALPHA)

            rise_delta = RISE_DELTA.get(kind)
            drift_delta = DRIFT_DELTA.get(kind)

            rising: list[bool] = []
            drift: list[bool] = []
            for t in range(len(ys)):
                # rising: positive slope AND a real rise across the window
                if rise_delta is None:
                    rising.append(False)
                else:
                    lo = max(0, t - SLOPE_WINDOW + 1)
                    rise = ys[t] - ys[lo]
                    rising.append(slope[t] > 0 and rise >= rise_delta)

                # drift: sub-threshold, sustained rise across the long window
                if drift_delta is None or warn is None:
                    drift.append(False)
                else:
                    lo = max(0, t - DRIFT_WINDOW + 1)
                    rise = ys[t] - ys[lo]
                    drift.append(
                        ys[t] < warn and slope[t] > 0 and rise >= drift_delta
                    )
            self.rising[sid] = rising
            self.drift[sid] = drift

    # ---------------------------------------------------------------- queries

    def value(self, sid: str, t: int) -> float:
        return self.tl.series[sid][self._clamp(t)]

    def is_rising(self, sid: str, t: int) -> bool:
        return self.rising[sid][self._clamp(t)]

    def is_drifting(self, sid: str, t: int) -> bool:
        return self.drift[sid][self._clamp(t)]

    def zone_gas_sensors(self, zone: str) -> list[str]:
        return [s for s in self.sensors_by_zone.get(zone, [])
                if self.meta[s]["kind"] in GAS_KINDS]

    def rising_gas_channels(self, zone: str, t: int) -> list[str]:
        """Gas channels in a zone that are currently rising (for corroboration)."""
        t = self._clamp(t)
        return [s for s in self.zone_gas_sensors(zone) if self.rising[s][t]]

    def gas_elevated(self, zone: str, t: int) -> bool:
        """Any gas channel in the zone above its warn limit, or rising."""
        t = self._clamp(t)
        for s in self.zone_gas_sensors(zone):
            warn = (self.meta[s].get("limits") or {}).get("warn")
            if warn is not None and self.tl.series[s][t] >= warn:
                return True
            if self.rising[s][t]:
                return True
        return False

    def pressure_abnormal(self, zone: str, t: int) -> list[str]:
        """Gas-main pressure sensors in a zone that are drifting or over warn.

        This is the 'connected network is abnormal' signal: either a genuine
        over-warn pressure, or the tell-tale sub-threshold drift.
        """
        t = self._clamp(t)
        out: list[str] = []
        for s in self.sensors_by_zone.get(zone, []):
            if self.meta[s]["kind"] != "pressure":
                continue
            warn = (self.meta[s].get("limits") or {}).get("warn")
            if warn is None:
                continue
            v = self.tl.series[s][t]
            # abnormal if actively drifting, over warn, OR sitting sustained
            # just below warn (so a momentary flattening of the drift slope
            # doesn't make an elevated gas main look healthy again).
            if self.drift[s][t] or v >= warn - 0.6:
                out.append(s)
        return out

    def valve_backpressure(self, t: int) -> dict | None:
        """A valve throttled (< 90%) while ΔP or gas-main pressure is rising.

        Returns evidence dict or None. This couples a *deliberate operational
        action* (valve op) to its rising-back-pressure consequence — the R6
        signature.
        """
        t = self._clamp(t)
        throttled = [
            s for s, m in self.meta.items()
            if m["kind"] == "valve_position" and self.tl.series[s][t] < 90
        ]
        if not throttled:
            return None
        rising_pressure = [
            s for s, m in self.meta.items()
            if m["kind"] in ("pressure", "diff_pressure") and self.rising[s][t]
        ]
        if not rising_pressure:
            return None
        return {
            "valves": {s: self.tl.series[s][t] for s in throttled},
            "rising_pressure": {
                s: round(self.tl.series[s][t], 2) for s in rising_pressure
            },
        }

    def _clamp(self, t: int) -> int:
        return max(0, min(self.duration, int(t)))


@lru_cache(maxsize=8)
def get_signals(scenario_id: str) -> ScenarioSignals:
    """One immutable signal set per scenario (cached)."""
    return ScenarioSignals(scenario_id)
