"use client";

/**
 * KAVACH — engineering dev console (kept at /console).
 * The raw digital-twin view used during Days 1–2: sensors by zone, permit
 * board, work orders, event feed, KAVACH compound-risk block, and full
 * transport control. The control-room UI at "/" is the demo face; this page
 * stays as the low-level instrument view for debugging and walkthroughs.
 */

import { useCallback, useEffect, useRef, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

// ---------------------------------------------------------------- types

interface SensorRead {
  v: number;
  unit: string;
  kind: string;
  zone: string;
  name: string;
  status: "ok" | "warn" | "alarm" | "high";
}

interface RiskZone { score: number; band: number; band_name: string; }
interface RiskAlert {
  id: string;
  zone_name: string;
  clock: string;
  band_name: string;
  score: number;
  confidence: number;
  headline: string;
  kind: string;
  rules: { id: string; label: string; detail: string }[];
}
interface RiskBlock {
  top_band: number;
  top_band_name: string;
  zones: Record<string, RiskZone>;
  active_alerts: RiskAlert[];
  suppressions: { sensor: string; wo: string; reason: string }[];
}

interface Snapshot {
  session: { scenario: string; cursor: number; speed: number; playing: boolean };
  state: {
    t: number;
    clock: string;
    duration: number;
    sensors: Record<string, SensorRead>;
    summary: { warn: number; alarm: number; high: number };
    permits: any[];
    work_orders: any[];
    shift: { name: string; label: string; supervisor: string; crew_count: number } | null;
    shift_changeover: boolean;
    events: any[];
    incident_occurred: boolean;
  };
  risk?: RiskBlock;
}

interface PlantZone { id: string; name: string; hazard_class: string; }
interface TimelineInfo {
  title: string;
  duration: number;
  events: { t: number; clock: string; type: string; title: string; severity: string }[];
}

// ---------------------------------------------------------------- helpers

const permitBadge = (type: string) =>
  type.includes("Confined") ? "cse" : type.includes("Hot") ? "hw" : "gen";

const tickColor: Record<string, string> = {
  permit: "var(--warn)",
  alarm: "var(--alarm)",
  incident: "var(--high)",
  valve_op: "var(--accent)",
  shift_change: "var(--accent)",
};

const bandColor = ["var(--muted)", "var(--warn)", "var(--alarm)", "var(--high)"];
const bandLabel = ["OK", "ADVISORY", "ALERT", "CRITICAL"];

const JUMPS = [
  { label: "02:30 drift begins", t: 30 },
  { label: "06:00 handover", t: 240 },
  { label: "06:30 CSE entry", t: 270 },
  { label: "08:30 hot work", t: 390 },
  { label: "09:40 first alarm", t: 460 },
  { label: "10:29 T-1min", t: 509 },
];

// ---------------------------------------------------------------- page

export default function DevConsole() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [zones, setZones] = useState<PlantZone[]>([]);
  const [timeline, setTimeline] = useState<TimelineInfo | null>(null);
  const [wsOn, setWsOn] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // static data
  useEffect(() => {
    fetch(`${API_BASE}/api/plant`).then((r) => r.json()).then((p) => setZones(p.zones));
    fetch(`${API_BASE}/api/timeline?scenario=vizag_replay`).then((r) => r.json()).then(setTimeline);
  }, []);

  // websocket with auto-reconnect
  useEffect(() => {
    let closed = false;
    const connect = () => {
      const ws = new WebSocket(`${WS_BASE}/ws/stream?session_id=console&scenario=vizag_replay`);
      wsRef.current = ws;
      ws.onopen = () => setWsOn(true);
      ws.onmessage = (e) => setSnap(JSON.parse(e.data));
      ws.onclose = () => {
        setWsOn(false);
        if (!closed) retryRef.current = setTimeout(connect, 1500);
      };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => {
      closed = true;
      if (retryRef.current) clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, []);

  const send = useCallback((action: string, value?: number) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, value }));
    }
  }, []);

  if (!snap) {
    return <div className="loading">CONNECTING TO PLANT DIGITAL TWIN…</div>;
  }

  const { state, session } = snap;
  const duration = state.duration;
  const sensorsByZone = new Map<string, [string, SensorRead][]>();
  for (const [sid, s] of Object.entries(state.sensors)) {
    if (!sensorsByZone.has(s.zone)) sensorsByZone.set(s.zone, []);
    sensorsByZone.get(s.zone)!.push([sid, s]);
  }

  return (
    <div className="shell">
      {/* ---------------- header ---------------- */}
      <header className="hdr">
        <div className="brand">
          KAVACH
          <small>Industrial Safety Intelligence — dev console</small>
        </div>
        <div className="scenario-title">{timeline?.title ?? session.scenario}</div>
        <div className="clock">{state.clock}</div>
        <div className="chips">
          {state.shift && <span className="chip shift">Shift {state.shift.name} · {state.shift.supervisor}</span>}
          {state.shift_changeover && <span className="chip changeover">SHIFT CHANGEOVER</span>}
          <span className="chip warn">WARN {state.summary.warn}</span>
          <span className="chip alarm">ALARM {state.summary.alarm}</span>
          <span className="chip high">HIGH {state.summary.high}</span>
          {state.incident_occurred && <span className="chip incident">INCIDENT</span>}
          <span className={`conn ${wsOn ? "on" : ""}`} title={wsOn ? "live" : "reconnecting"} />
        </div>
      </header>

      {/* ---------------- transport ---------------- */}
      <div className="transport">
        <button className="btn" onClick={() => send(session.playing ? "pause" : "play")}>
          {session.playing ? "❚❚ Pause" : "► Play"}
        </button>
        <select
          value={session.speed}
          onChange={(e) => send("speed", Number(e.target.value))}
          title="simulation minutes per real second"
        >
          {[0.5, 1, 2, 5, 10, 30, 60].map((v) => (
            <option key={v} value={v}>{v} min/s</option>
          ))}
        </select>
        <div className="scrub-wrap">
          {timeline?.events.map((e, i) => (
            <span
              key={i}
              className="tick"
              title={`${e.clock} ${e.title}`}
              style={{
                left: `${(e.t / duration) * 100}%`,
                background: tickColor[e.type] ?? "var(--muted)",
              }}
            />
          ))}
          <input
            className="scrub"
            type="range"
            min={0}
            max={duration}
            value={state.t}
            onChange={(e) => send("seek", Number(e.target.value))}
          />
        </div>
        <span className="t-readout">t={state.t} / {duration} min</span>
        <div className="jumps">
          {JUMPS.map((j) => (
            <button key={j.t} onClick={() => send("seek", j.t)}>{j.label}</button>
          ))}
        </div>
      </div>

      {/* ---------------- main grid ---------------- */}
      <div className="grid">
        <section className="panel">
          <h2>Sensor field — {Object.keys(state.sensors).length} instruments</h2>
          {zones.map((z) => {
            const list = sensorsByZone.get(z.id);
            if (!list) return null;
            return (
              <div className="zone-block" key={z.id}>
                <div className="zone-name">
                  {z.name}
                  <small>{z.hazard_class}</small>
                </div>
                <div className="sensor-grid">
                  {list.map(([sid, s]) => (
                    <div className={`sensor s-${s.status}`} key={sid} title={s.name}>
                      <div className="sid">{sid}</div>
                      <div className="sval">
                        {s.v}
                        <small>{s.unit}</small>
                      </div>
                      <div className="sname">{s.name}</div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </section>

        <aside style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {snap.risk && (
            <section className="panel">
              <h2>
                KAVACH compound risk
                <span
                  className="chip"
                  style={{
                    marginLeft: 8,
                    background: bandColor[snap.risk.top_band],
                    color: "#000",
                  }}
                >
                  {snap.risk.top_band_name.toUpperCase()}
                </span>
              </h2>
              <div className="risk-zones">
                {Object.entries(snap.risk.zones)
                  .filter(([, z]) => z.score > 0)
                  .sort((a, b) => b[1].score - a[1].score)
                  .map(([zid, z]) => (
                    <span
                      key={zid}
                      className="risk-chip"
                      title={`${zid} — ${bandLabel[z.band]}`}
                      style={{ borderColor: bandColor[z.band], color: bandColor[z.band] }}
                    >
                      {zid} {z.score.toFixed(0)}
                    </span>
                  ))}
              </div>
              {snap.risk.active_alerts.length === 0 && (
                <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 8 }}>
                  No compound alerts — KAVACH watching.
                </div>
              )}
              {snap.risk.active_alerts.map((a) => (
                <div
                  className="risk-alert"
                  key={a.id}
                  style={{ borderLeft: `3px solid ${bandColor[3]}` }}
                >
                  <div className="ra-head">
                    <span className="badge" style={{ background: bandColor[3], color: "#000" }}>
                      {a.band_name.toUpperCase()}
                    </span>
                    <span className="ra-when">{a.clock}</span>
                    <span className="ra-conf">conf {(a.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="ra-headline">{a.headline}</div>
                  <ul className="ra-rules">
                    {a.rules.map((r, i) => (
                      <li key={i}>
                        <b>{r.id}</b> {r.detail}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              {snap.risk.suppressions.map((s, i) => (
                <div className="risk-supp" key={i} title={s.reason}>
                  ⊘ Suppressed {s.sensor} — {s.wo} calibration
                </div>
              ))}
            </section>
          )}

          <section className="panel">
            <h2>Permit board</h2>
            {state.permits.length === 0 && (
              <div style={{ color: "var(--muted)", fontSize: 12 }}>No permits issued yet.</div>
            )}
            {state.permits.map((p) => (
              <div className={`permit ${p.active ? "" : "inactive"}`} key={p.id}>
                <div className="prow">
                  <span className={`badge ${permitBadge(p.type)}`}>{p.type}</span>
                  <span className="pid">{p.id}</span>
                </div>
                <div className="ptitle">{p.title}</div>
                <div className="pmeta">
                  {p.from_clock}–{p.to_clock} · crew {p.crew.length} · {p.zone}
                </div>
              </div>
            ))}
          </section>

          <section className="panel">
            <h2>Work orders</h2>
            {state.work_orders.map((w) => (
              <div className="wo" key={w.id}>
                <span className="wid">{w.id}</span>
                {w.title}
                <span className={`wstat ${w.status}`}>{w.status.replace("_", " ")}</span>
              </div>
            ))}
          </section>

          <section className="panel">
            <h2>Event feed</h2>
            {[...state.events].reverse().map((e, i) => (
              <div className="evt" key={`${e.t}-${i}`}>
                <span className={`dot ${e.severity}`} />
                <span className="etime">{e.clock}</span>
                <div>
                  <div className="etitle">{e.title}</div>
                  {e.detail && <div className="edetail">{e.detail}</div>}
                </div>
              </div>
            ))}
          </section>
        </aside>
      </div>
    </div>
  );
}
