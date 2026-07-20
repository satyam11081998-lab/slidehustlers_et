"""
KAVACH — Plant Digital Twin Simulation Engine
===============================================

Builds a fully deterministic, minute-resolution timeline for a scripted
scenario over the synthetic plant defined in ``data/plant_layout.json``.

Design principles
-----------------
* **Deterministic**: every sensor stream is seeded with ``crc32(scenario::sensor)``,
  so a given scenario produces bit-identical data on every machine, every run.
  The demo can never surprise us.
* **Pre-computed**: the entire timeline is materialised up-front
  (~34 sensors x ~600 minutes), which makes scrubbing to any instant O(1)
  and lets the Day-2 risk engines evaluate the full horizon offline.
* **Scriptable**: scenarios declare sensor ``ramps`` (piecewise trajectories
  that chain and hold) and ``spikes`` (transient excursions with a smooth
  sine envelope), plus permits, work orders, shifts and narrative events.
"""

from __future__ import annotations

import json
import math
import random
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
SCENARIO_DIR = DATA_DIR / "scenarios"

STATUS_ORDER = ["ok", "warn", "alarm", "high"]


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def plant_layout() -> dict[str, Any]:
    """The synthetic plant: zones, equipment, sensors (cached)."""
    return _load_json(DATA_DIR / "plant_layout.json")


def list_scenarios() -> list[dict[str, Any]]:
    """Lightweight scenario summaries for the API."""
    out = []
    for path in sorted(SCENARIO_DIR.glob("*.json")):
        sc = _load_json(path)
        out.append(
            {
                "id": sc["id"],
                "title": sc["title"],
                "description": sc.get("description", ""),
                "start_clock": sc["start_clock"],
                "duration_min": sc["duration_min"],
            }
        )
    return out


def scenario_def(scenario_id: str) -> dict[str, Any]:
    path = SCENARIO_DIR / f"{scenario_id}.json"
    if not path.exists():
        raise KeyError(f"Unknown scenario: {scenario_id!r}")
    return _load_json(path)


def _seed(*parts: str) -> int:
    """Cross-platform, cross-run stable seed (Python's hash() is salted)."""
    return zlib.crc32("::".join(parts).encode("utf-8"))


def _clock_str(start_clock: str, minutes: float) -> str:
    h, m = (int(x) for x in start_clock.split(":"))
    total = (h * 60 + m + int(round(minutes))) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


class Timeline:
    """A fully materialised scenario run over the plant model."""

    def __init__(self, scenario_id: str, sc_def: dict[str, Any] | None = None):
        # ``sc_def`` lets the what-if sandbox inject a modified scenario
        # definition without touching the on-disk file or the cached timeline.
        self.id = scenario_id
        self.plant = plant_layout()
        self.sc = sc_def if sc_def is not None else scenario_def(scenario_id)
        self.duration: int = int(self.sc["duration_min"])
        self.start_clock: str = self.sc["start_clock"]
        self.sensors_meta: dict[str, dict] = {s["id"]: s for s in self.plant["sensors"]}
        self.events: list[dict] = sorted(self.sc.get("events", []), key=lambda e: e["t"])
        self.permits: list[dict] = self.sc.get("permits", [])
        self.work_orders: list[dict] = self.sc.get("work_orders", [])
        self.shifts: list[dict] = self.sc.get("shifts", [])
        self.ground_truth: dict = self.sc.get("ground_truth", {})
        self.series: dict[str, list[float]] = {}
        self._build_series()

    # ------------------------------------------------------------------ build

    def _build_series(self) -> None:
        ramps_by: dict[str, list[dict]] = {}
        for r in self.sc.get("ramps", []):
            ramps_by.setdefault(r["sensor"], []).append(r)
        for rs in ramps_by.values():
            rs.sort(key=lambda r: r["t0"])

        spikes_by: dict[str, list[dict]] = {}
        for s in self.sc.get("spikes", []):
            spikes_by.setdefault(s["sensor"], []).append(s)

        salt = self.sc.get("seed_salt", self.id)
        for sid, meta in self.sensors_meta.items():
            rng = random.Random(_seed(salt, sid))
            base = float(meta["base"])
            sd = float(meta.get("noise_sd", 0.0))
            nd = int(meta.get("round", 2))
            ramps = ramps_by.get(sid, [])
            spikes = spikes_by.get(sid, [])

            values: list[float] = []
            for t in range(self.duration + 1):
                level = self._level_at(base, ramps, t)
                v = level
                for sp in spikes:
                    dur = max(2, int(sp.get("duration", 5)))
                    if sp["t"] <= t < sp["t"] + dur:
                        prog = (t - sp["t"]) / (dur - 1)
                        v += (float(sp["to"]) - level) * math.sin(math.pi * min(1.0, prog))
                if sd > 0:
                    v += rng.gauss(0.0, sd)
                values.append(round(v, nd) if nd > 0 else round(v))
            self.series[sid] = values

    @staticmethod
    def _level_at(base: float, ramps: list[dict], t: int) -> float:
        """Piecewise trajectory: before first ramp -> base; inside a ramp ->
        interpolate; between/after ramps -> hold the last completed target."""
        level = base
        for r in ramps:
            t0, t1, to = int(r["t0"]), int(r["t1"]), float(r["to"])
            frm = float(r.get("from", level))
            if t < t0:
                return level
            if t <= t1:
                if t1 == t0:
                    return to
                p = (t - t0) / (t1 - t0)
                if r.get("shape") == "exp":
                    p = p * p
                return frm + (to - frm) * p
            level = to
        return level

    # ------------------------------------------------------------------ state

    def clock(self, t: float) -> str:
        return _clock_str(self.start_clock, t)

    def sensor_status(self, sid: str, value: float) -> str:
        limits = self.sensors_meta[sid].get("limits")
        if not limits:
            return "ok"
        if "high" in limits and value >= limits["high"]:
            return "high"
        if "alarm" in limits and value >= limits["alarm"]:
            return "alarm"
        if "warn" in limits and value >= limits["warn"]:
            return "warn"
        return "ok"

    def _wo_status(self, wo: dict, t: int) -> str:
        if wo.get("completed") is not None and t >= wo["completed"]:
            return "completed"
        if t >= wo.get("started", 10**9):
            return "in_progress"
        if t >= wo.get("created", 10**9):
            return "scheduled"
        return "future"

    def state_at(self, t: float) -> dict[str, Any]:
        ti = max(0, min(self.duration, int(round(t))))

        sensors: dict[str, dict] = {}
        summary = {"warn": 0, "alarm": 0, "high": 0}
        for sid, meta in self.sensors_meta.items():
            v = self.series[sid][ti]
            status = self.sensor_status(sid, v)
            if status in summary:
                summary[status] += 1
            sensors[sid] = {
                "v": v,
                "unit": meta["unit"],
                "kind": meta["kind"],
                "zone": meta["zone"],
                "name": meta["name"],
                "status": status,
            }

        permits = []
        for p in self.permits:
            if ti >= p["from"]:
                permits.append(
                    {
                        "id": p["id"],
                        "type": p["type"],
                        "zone": p["zone"],
                        "title": p["title"],
                        "from": p["from"],
                        "to": p["to"],
                        "from_clock": self.clock(p["from"]),
                        "to_clock": self.clock(min(p["to"], self.duration)),
                        "crew": p.get("crew", []),
                        "gas_test": p.get("gas_test"),
                        "isolations": p.get("isolations", []),
                        "active": p["from"] <= ti < p["to"],
                    }
                )

        work_orders = [
            {**wo, "status": self._wo_status(wo, ti)}
            for wo in self.work_orders
            if ti >= wo.get("created", 0)
        ]

        shift = next((s for s in self.shifts if s["from"] <= ti < s["to"]), None)
        changeover = any(
            s["from"] > 0 and abs(ti - s["from"]) <= 15 for s in self.shifts
        )

        recent = [
            {**e, "clock": self.clock(e["t"])}
            for e in self.events
            if e["t"] <= ti and e.get("visible", True)
        ][-15:]

        incident_at = self.ground_truth.get("incident_at")
        return {
            "scenario": self.id,
            "t": ti,
            "clock": self.clock(ti),
            "duration": self.duration,
            "sensors": sensors,
            "summary": summary,
            "permits": permits,
            "work_orders": work_orders,
            "shift": shift,
            "shift_changeover": changeover,
            "events": recent,
            "incident_occurred": incident_at is not None and ti >= incident_at,
        }

    def visible_timeline(self) -> dict[str, Any]:
        """Scrubber payload: visible events + permit windows (no ground truth)."""
        return {
            "scenario": self.id,
            "title": self.sc["title"],
            "description": self.sc.get("description", ""),
            "narrative": self.sc.get("narrative", ""),
            "start_clock": self.start_clock,
            "duration": self.duration,
            "events": [
                {
                    "t": e["t"],
                    "clock": self.clock(e["t"]),
                    "type": e["type"],
                    "title": e["title"],
                    "severity": e.get("severity", "info"),
                }
                for e in self.events
                if e.get("visible", True)
            ],
            "permit_windows": [
                {
                    "id": p["id"],
                    "type": p["type"],
                    "zone": p["zone"],
                    "from": p["from"],
                    "to": min(p["to"], self.duration),
                }
                for p in self.permits
            ],
        }

    def series_for(self, sensor_id: str, step: int = 1) -> dict[str, Any]:
        if sensor_id not in self.series:
            raise KeyError(f"Unknown sensor: {sensor_id!r}")
        step = max(1, int(step))
        pts = self.series[sensor_id][::step]
        meta = self.sensors_meta[sensor_id]
        return {
            "sensor": sensor_id,
            "name": meta["name"],
            "unit": meta["unit"],
            "limits": meta.get("limits"),
            "step": step,
            "values": pts,
        }


@lru_cache(maxsize=8)
def get_timeline(scenario_id: str) -> Timeline:
    """Timelines are immutable once built — cache one per scenario."""
    return Timeline(scenario_id)
