"""
KAVACH — FastAPI service
========================

REST + WebSocket API over the plant digital twin.

Playback model: a *session* holds a cursor (simulation minute) over a
scenario timeline. The WebSocket loop advances the cursor while playing and
streams full state snapshots ~4x/second. A dedicated reader task applies
control messages (play / pause / seek / speed) the instant they arrive;
controls are also accepted via REST.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.simulator.engine import get_timeline, list_scenarios, plant_layout
from app.risk.baseline import get_baseline
from app.risk.compound import get_risk_engine
from app.risk.explain import narrate
from app.risk.metrics import compute_metrics
from app.risk import regulatory
from app.risk.orchestrator import get_orchestrator
from app.risk.report import generate_markdown
from app.risk import whatif
from app.risk.patterns import get_patterns
from app.risk.compliance import get_compliance
from app.risk.graph import get_graph

TICK_SECONDS = 0.25
DEFAULT_SPEED = 2.0  # simulation minutes per real second

app = FastAPI(
    title="KAVACH API",
    version="0.1.1",
    description="Industrial Safety Intelligence — plant digital twin service",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # prototype; tighten for production deployment
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- sessions


@dataclass
class Session:
    scenario: str
    cursor: float = 0.0
    speed: float = DEFAULT_SPEED
    playing: bool = False

    def as_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "cursor": round(self.cursor, 2),
            "speed": self.speed,
            "playing": self.playing,
        }


SESSIONS: dict[str, Session] = {}


def _get_session(session_id: str) -> Session:
    if session_id not in SESSIONS:
        raise HTTPException(404, f"Unknown session: {session_id}")
    return SESSIONS[session_id]


def _apply_control(s: Session, action: str, value: float | None = None) -> None:
    duration = get_timeline(s.scenario).duration
    if action == "play":
        if s.cursor >= duration:  # replay from start if at the end
            s.cursor = 0.0
        s.playing = True
    elif action == "pause":
        s.playing = False
    elif action == "seek" and value is not None:
        s.cursor = max(0.0, min(float(duration), float(value)))
    elif action == "speed" and value is not None:
        s.speed = max(0.1, min(60.0, float(value)))
    elif action == "scenario_switch":
        pass  # reserved for Day 3+
    else:
        raise HTTPException(400, f"Bad control action: {action}")


# ---------------------------------------------------------------- schemas


class SessionCreate(BaseModel):
    scenario_id: str = "vizag_replay"
    speed: float = DEFAULT_SPEED


class SessionControl(BaseModel):
    action: str  # play | pause | seek | speed
    value: float | None = None


# ---------------------------------------------------------------- routes


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "kavach", "version": app.version, "scenarios": len(list_scenarios())}


@app.get("/api/plant")
def plant() -> dict:
    return plant_layout()


@app.get("/api/scenarios")
def scenarios() -> list[dict]:
    return list_scenarios()


@app.get("/api/state")
def state(scenario: str = "vizag_replay", t: float = 0) -> dict:
    try:
        return get_timeline(scenario).state_at(t)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/timeline")
def timeline(scenario: str = "vizag_replay") -> dict:
    try:
        return get_timeline(scenario).visible_timeline()
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/series")
def series(scenario: str = "vizag_replay", sensor: str = "PT-GM-104", step: int = 5) -> dict:
    try:
        return get_timeline(scenario).series_for(sensor, step)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


# ---------------------------------------------------------------- risk API


@app.get("/api/risk")
def risk(scenario: str = "vizag_replay", t: float = 0) -> dict:
    """Compound-risk snapshot at minute t: per-zone scores/bands, active
    alerts (each with its evidence AND regulatory basis), and any calibration
    suppressions."""
    try:
        snap = get_risk_engine(scenario).state_at(int(t))
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    snap["active_alerts"] = [regulatory.attach_to_alert(a)
                             for a in snap["active_alerts"]]
    return snap


@app.get("/api/risk/alerts")
def risk_alerts(scenario: str = "vizag_replay", narrate_alerts: bool = False) -> dict:
    """Every compound alert KAVACH raises across the scenario, in order. Each
    alert carries its ``regulatory_basis`` (OISD / Factories Act / DGMS clauses
    keyed off the rules that fired). Set narrate_alerts=1 to also attach a
    natural-language explanation (deterministic template unless an LLM key is
    configured)."""
    try:
        eng = get_risk_engine(scenario)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    alerts = [regulatory.attach_to_alert(a) for a in eng.alerts_list()]
    if narrate_alerts:
        alerts = [{**a, "narrative": narrate(a)} for a in alerts]
    return {"scenario": scenario, "count": len(alerts), "alerts": alerts}


@app.get("/api/risk/series")
def risk_series(scenario: str = "vizag_replay", step: int = 2) -> dict:
    """Decimated horizon series for the hero chart: per-zone KAVACH risk score
    (0-100) over time, plus a single-sensor 'baseline' curve = the worst sensor
    expressed as a percentage of its own alarm limit. Static per scenario; the
    UI overlays a moving 'now' cursor."""
    try:
        eng = get_risk_engine(scenario)
        tl = get_timeline(scenario)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    step = max(1, int(step))
    ts = list(range(0, tl.duration + 1, step))
    zones = {z: [round(eng.zone_score[z][t], 1) for t in ts] for z in eng.zone_ids}

    def baseline_pct(t: int) -> float:
        best = 0.0
        for sid, meta in tl.sensors_meta.items():
            alarm = (meta.get("limits") or {}).get("alarm")
            if alarm:
                best = max(best, tl.series[sid][t] / alarm * 100.0)
        return round(min(120.0, best), 1)

    baseline = [baseline_pct(t) for t in ts]
    hero = max(eng.zone_ids, key=lambda z: max(eng.zone_score[z]))
    return {
        "scenario": scenario, "step": step, "duration": tl.duration,
        "t": ts, "zones": zones, "baseline": baseline, "hero": hero,
    }


@app.get("/api/metrics")
def metrics(scenario: str = "vizag_replay") -> dict:
    """KAVACH vs single-sensor baseline scored against ground truth:
    lead time, false negatives / positives, per-rule contributions."""
    try:
        return compute_metrics(scenario)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/baseline")
def baseline(scenario: str = "vizag_replay") -> dict:
    """The single-sensor baseline's alarm log (the comparator view)."""
    try:
        b = get_baseline(scenario)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {**b.summary(), "alarms": [a.to_dict() for a in b.alarms()]}


@app.get("/api/patterns")
def patterns(scenario: str = "vizag_replay", t: int | None = None) -> dict:
    """Incident Pattern Intelligence — recurring factors across the plant's own
    near-miss register, correlated with whatever is firing right now."""
    rules: list[str] = []
    if t is not None:
        try:
            st = get_risk_engine(scenario).state_at(int(t))
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        for a in st.get("active_alerts", []):
            rules += [r.get("id") if isinstance(r, dict) else r
                      for r in a.get("rules", [])]
    return get_patterns().summary(sorted(set(rules)))


@app.get("/api/compliance")
def compliance(scenario: str = "vizag_replay", t: int | None = None) -> dict:
    """Quality & Compliance Audit Agent. Without `t`, sweeps the whole scenario
    and returns the findings register plus corrective actions."""
    try:
        agent = get_compliance(scenario)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return agent.audit_at(int(t)) if t is not None else agent.audit_run()


@app.get("/api/graph")
def graph(scenario: str = "vizag_replay", zone: str | None = None,
          t: int | None = None) -> dict:
    """Equipment-permit-risk knowledge graph. With `zone` and `t`, returns the
    subgraph implicated in the risk at that place and minute."""
    try:
        g = get_graph(scenario)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    if zone is not None and t is not None:
        return g.subgraph_for_alert(zone, int(t))
    return {**g.summary(), "nodes": list(g.nodes.values()), "edges": g.edges}


# ---------------------------------------------------------- Day-4: regulatory


@app.get("/api/regulatory/coverage")
def regulatory_coverage() -> dict:
    """Compliance-coverage summary: sources (OISD / Factories Act / DGMS),
    clause count, rules covered — the 'regulatory compliance coverage' the
    evaluation asks for."""
    return regulatory.get_corpus().coverage()


@app.get("/api/regulatory/search")
def regulatory_search(q: str, k: int = 5) -> dict:
    """Deterministic BM25 retrieval over the regulatory corpus."""
    return {"query": q, "results": regulatory.search(q, k)}


@app.get("/api/regulatory/for-rules")
def regulatory_for_rules(rules: str) -> dict:
    """Citations underpinning a comma-separated set of compound rules,
    e.g. ?rules=R1,R3,R5."""
    ids = [r.strip().upper() for r in rules.split(",") if r.strip()]
    return {"rules": ids, "citations": regulatory.citations_for_rules(ids)}


# ---------------------------------------------------------- Day-4: orchestrator


@app.get("/api/orchestrator")
def orchestrator(scenario: str = "vizag_replay") -> dict:
    """The full emergency-response plan for the scenario's first critical alert:
    ordered actions (each with regulatory basis), evacuation set from the
    connectivity graph, roles, and the counterfactual."""
    try:
        return get_orchestrator(scenario).as_dict()
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/orchestrator/state")
def orchestrator_state(scenario: str = "vizag_replay", t: float = 0) -> dict:
    """Live orchestrator status at minute t (armed / active / clear)."""
    try:
        return get_orchestrator(scenario).state_at(int(t))
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


# ---------------------------------------------------------- Day-4: report


@app.get("/api/report")
def report(scenario: str = "vizag_replay") -> dict:
    """The auto-generated incident / prevention report as Markdown."""
    try:
        return {"scenario": scenario, "format": "markdown",
                "markdown": generate_markdown(scenario)}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


# ---------------------------------------------------------- Day-4: what-if


class WhatIf(BaseModel):
    scenario: str = "vizag_replay"
    t: float = 270
    interventions: list[dict] = []


@app.get("/api/whatif/options")
def whatif_options(scenario: str = "vizag_replay") -> dict:
    """Preset intervention levers the what-if console renders as one-click chips."""
    return whatif.options_for(scenario)


@app.post("/api/whatif")
def whatif_evaluate(body: WhatIf) -> dict:
    """Apply interventions to a sandbox copy of the twin and return the
    before/after compound-risk diff at minute t."""
    try:
        eng = get_risk_engine(body.scenario)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return whatif.evaluate(body.scenario, int(body.t), body.interventions, eng)


@app.post("/api/session")
def create_session(body: SessionCreate) -> dict:
    get_timeline(body.scenario_id)  # validate scenario exists
    sid = uuid.uuid4().hex[:8]
    SESSIONS[sid] = Session(scenario=body.scenario_id, speed=body.speed)
    return {"session_id": sid, **SESSIONS[sid].as_dict()}


@app.get("/api/session/{session_id}/state")
def session_state(session_id: str) -> dict:
    s = _get_session(session_id)
    return {
        "session": s.as_dict(),
        "state": get_timeline(s.scenario).state_at(s.cursor),
    }


@app.post("/api/session/{session_id}/control")
def session_control(session_id: str, body: SessionControl) -> dict:
    s = _get_session(session_id)
    _apply_control(s, body.action, body.value)
    return s.as_dict()


# ---------------------------------------------------------------- websocket


@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket) -> None:
    """Streams state snapshots ~4x/s. A dedicated reader task applies control
    frames (play/pause/seek/speed) the instant they arrive, so rapid slider
    drags never lag behind the tick clock."""
    await ws.accept()
    session_id = ws.query_params.get("session_id") or uuid.uuid4().hex[:8]
    scenario = ws.query_params.get("scenario") or "vizag_replay"
    if session_id not in SESSIONS:
        SESSIONS[session_id] = Session(scenario=scenario)
    s = SESSIONS[session_id]
    tl = get_timeline(s.scenario)
    risk_eng = get_risk_engine(s.scenario)
    disconnected = asyncio.Event()

    async def reader() -> None:
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                    _apply_control(s, msg.get("action", ""), msg.get("value"))
                except (json.JSONDecodeError, HTTPException):
                    pass  # ignore malformed / bad control frames
        except Exception:  # includes WebSocketDisconnect
            disconnected.set()

    reader_task = asyncio.create_task(reader())
    try:
        while not disconnected.is_set():
            if s.playing:
                s.cursor = min(float(tl.duration), s.cursor + s.speed * TICK_SECONDS)
                if s.cursor >= tl.duration:
                    s.playing = False
            await ws.send_json(
                {
                    "type": "state",
                    "session_id": session_id,
                    "session": s.as_dict(),
                    "state": tl.state_at(s.cursor),
                    "risk": risk_eng.state_at(int(s.cursor)),
                }
            )
            await asyncio.sleep(TICK_SECONDS)
    except (WebSocketDisconnect, RuntimeError):
        pass  # client went away mid-send
    finally:
        reader_task.cancel()
