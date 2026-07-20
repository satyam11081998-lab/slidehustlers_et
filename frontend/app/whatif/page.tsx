"use client";

/**
 * KAVACH — What-if Console + Orchestrator + Regulatory Intelligence (route "/whatif")
 * ==================================================================================
 * The Q&A surface. Three deterministic Day-4 capabilities, live off the API:
 *   1. WHAT-IF SANDBOX  — toggle interventions on a copy of the twin and watch
 *      the compound-risk score move (base vs modified), with the rules that
 *      changed and the regulatory basis. "What if they HAD isolated the main?"
 *   2. ORCHESTRATOR     — the emergency-response action plan the critical alert
 *      triggers: ordered actions (each cited), evacuation set, roles, counterfactual.
 *   3. REGULATORY RAG   — coverage across OISD / Factories Act / DGMS + BM25 search.
 *
 * Everything is deterministic on the backend; this page only renders it.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

// ---- types ----
interface Citation { code: string; ref: string; citation: string; title: string; summary: string; url?: string; score?: number; }
interface Option { id: string; label: string; kind: string; recommended_t: number; note: string; interventions: any[]; }
interface EvalSnap { score: number; band_name: string; rule_ids: string[]; focus_zone_name: string; }
interface EvalResult { t: number; clock: string; base: EvalSnap; modified: EvalSnap; delta: { score_delta: number; band_from: string; band_to: string; rules_added: string[]; rules_removed: string[]; }; regulatory_basis: Citation[]; narrative: string; }
interface Action { seq: number; type: string; sla: string; title: string; detail: string; regulatory_basis: Citation[]; }
interface Orchestrator { triggered: boolean; reason?: string; trigger?: any; actions: Action[]; roles?: any[]; evacuation?: any; suspended_permits?: any[]; counterfactual?: any; }
interface Coverage { sources: { code: string; title: string; revision: string; authority: string }[]; clause_count: number; rules_covered: string[]; topics: string[]; }

const MOMENTS: Record<string, { label: string; t: number }[]> = {
  vizag_replay: [
    { label: "06:00 handover", t: 240 }, { label: "06:30 entry", t: 270 },
    { label: "08:30 hot work", t: 390 }, { label: "09:30 valve", t: 450 },
    { label: "09:40 1st alarm", t: 460 },
  ],
  normal_day: [
    { label: "08:00", t: 120 }, { label: "09:00", t: 180 },
    { label: "10:00 calibration", t: 240 }, { label: "12:00", t: 360 },
  ],
};

function bandColor(b: string): string {
  return b === "critical" ? "#ef4b58" : b === "alert" ? "#f5921f"
    : b === "advisory" ? "#f2b134" : "#35c47a";
}
function scoreRGB(s: number): string {
  const st: [number, [number, number, number]][] = [[0, [53, 196, 122]], [45, [242, 177, 52]], [62, [245, 146, 31]], [82, [239, 75, 88]], [100, [214, 60, 72]]];
  s = Math.max(0, Math.min(100, s));
  for (let i = 1; i < st.length; i++) { const [a, c1] = st[i - 1], [b, c2] = st[i]; if (s <= b) { const p = (s - a) / ((b - a) || 1); return `rgb(${[0, 1, 2].map(k => Math.round(c1[k] + (c2[k] - c1[k]) * p)).join(",")})`; } }
  return "rgb(214,60,72)";
}

export default function WhatIfConsole() {
  const [scenario, setScenario] = useState("vizag_replay");
  const [scenarios, setScenarios] = useState<{ id: string; title: string; duration_min: number }[]>([]);
  const [options, setOptions] = useState<Option[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [t, setT] = useState(270);
  const [result, setResult] = useState<EvalResult | null>(null);
  const [orch, setOrch] = useState<Orchestrator | null>(null);
  const [cov, setCov] = useState<Coverage | null>(null);
  const [q, setQ] = useState("confined space gas main isolation");
  const [hits, setHits] = useState<Citation[]>([]);

  const duration = useMemo(() => scenarios.find(s => s.id === scenario)?.duration_min ?? 600, [scenarios, scenario]);

  useEffect(() => { fetch(`${API}/api/scenarios`).then(r => r.json()).then(setScenarios); }, []);
  useEffect(() => { fetch(`${API}/api/regulatory/coverage`).then(r => r.json()).then(setCov); }, []);

  // per-scenario: options + orchestrator; reset selection
  useEffect(() => {
    setSelected(new Set()); setResult(null);
    fetch(`${API}/api/whatif/options?scenario=${scenario}`).then(r => r.json()).then(d => setOptions(d.options || []));
    fetch(`${API}/api/orchestrator?scenario=${scenario}`).then(r => r.json()).then((d: Orchestrator) => {
      setOrch(d);
      if (d.triggered && d.trigger) setT(d.trigger.t);
      else setT(scenario === "normal_day" ? 240 : 270);
    });
  }, [scenario]);

  // evaluate whenever the scenario, chosen interventions, or time change
  const runEval = useCallback(() => {
    const interventions = options.filter(o => selected.has(o.id)).flatMap(o => o.interventions);
    fetch(`${API}/api/whatif`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario, t, interventions }),
    }).then(r => r.json()).then(setResult);
  }, [scenario, t, selected, options]);
  useEffect(() => { if (options.length) runEval(); }, [runEval, options.length]);

  const search = useCallback(() => {
    if (!q.trim()) return;
    fetch(`${API}/api/regulatory/search?q=${encodeURIComponent(q)}&k=5`).then(r => r.json()).then(d => setHits(d.results || []));
  }, [q]);
  useEffect(() => { search(); }, [cov]); // initial search once corpus is known

  const toggle = (id: string) => setSelected(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const escActive = options.some(o => selected.has(o.id) && o.kind === "escalation");

  const clockOf = (min: number) => { const base = scenario === "normal_day" ? 6 * 60 : 2 * 60; const tot = (base + min) % 1440; return `${String(Math.floor(tot / 60)).padStart(2, "0")}:${String(tot % 60).padStart(2, "0")}`; };

  if (!cov) return <div className="wi-loading">LOADING KAVACH INTELLIGENCE…</div>;

  return (
    <div className="cr-app">
      {/* top bar */}
      <div className="cr-topbar">
        <div className="cr-brand">
          <svg className="cr-mark" viewBox="0 0 44 46"><path d="M22 2 L38 8 V22 C38 33 31 40 22 44 C13 40 6 33 6 22 V8 Z" fill="#0e1826" stroke="#29b6f6" strokeWidth="2" /><path d="M13 23 h5 l3 7 l4 -13 l3 6 h5" fill="none" stroke="#7fd3f7" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
          <div><div className="cr-wordmark">KAVACH</div><div className="cr-sub">Intelligence Console · Regulatory · Orchestrator · What-if</div></div>
        </div>
        <div className="cr-scenario">
          <span className="cr-label">Scenario</span>
          <select className="cr-select" value={scenario} onChange={e => setScenario(e.target.value)}>
            {scenarios.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}
          </select>
        </div>
        <div className="wi-nav">
          <a className="wi-link primary" href="/">← Control Room</a>
          <a className="wi-link" href="/console">Dev Console</a>
        </div>
      </div>

      <div className="wi-grid">
        {/* ============ LEFT: what-if sandbox + orchestrator ============ */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* --- what-if console --- */}
          <div className="cr-card">
            <div className="cr-card-head"><h3>What-if sandbox</h3></div>
            <p className="wi-sub">Toggle interventions on a sandbox copy of the twin; KAVACH re-runs the compound engine and shows the risk move at the selected minute. Deterministic — same levers, same numbers.</p>

            <div className="wi-chips">
              {options.map(o => (
                <button key={o.id} className={`wi-chip ${selected.has(o.id) ? "on" : ""} ${selected.has(o.id) && o.kind === "escalation" ? "esc" : ""}`} onClick={() => toggle(o.id)}>
                  <div className="wi-chip-top">
                    <span className={`wi-kind ${o.kind === "escalation" ? "esc" : "mit"}`}>{o.kind === "escalation" ? "escalate" : "mitigate"}</span>
                    <span className="wi-chip-label">{o.label}</span>
                  </div>
                  <div className="wi-chip-note">{o.note}</div>
                </button>
              ))}
            </div>

            <div className="wi-time">
              <span className="cr-label">Evaluate at</span>
              <input type="range" min={0} max={duration} value={t} onChange={e => setT(Number(e.target.value))} />
              <span className="wi-tval">{clockOf(t)} · t={t}</span>
            </div>
            <div className="wi-moments">
              {(MOMENTS[scenario] || []).map(m => (
                <button key={m.t} className={`wi-moment ${t === m.t ? "on" : ""}`} onClick={() => setT(m.t)}>{m.label}</button>
              ))}
            </div>

            {result && (
              <div className="wi-result">
                <div className="wi-gauges">
                  <div className="wi-gauge">
                    <div className="wi-g-label">Baseline (as-recorded)</div>
                    <div className="wi-g-score" style={{ color: scoreRGB(result.base.score) }}>{Math.round(result.base.score)}<small style={{ fontSize: 16, color: "#6f7a99" }}>/100</small></div>
                    <div className="wi-g-band" style={{ color: bandColor(result.base.band_name) }}>{result.base.band_name}</div>
                    <div className="wi-bar"><span style={{ width: `${result.base.score}%`, background: scoreRGB(result.base.score) }} /></div>
                  </div>
                  <div className="wi-arrow">→</div>
                  <div className="wi-gauge">
                    <div className="wi-g-label">With interventions</div>
                    <div className="wi-g-score" style={{ color: scoreRGB(result.modified.score) }}>{Math.round(result.modified.score)}<small style={{ fontSize: 16, color: "#6f7a99" }}>/100</small></div>
                    <div className="wi-g-band" style={{ color: bandColor(result.modified.band_name) }}>{result.modified.band_name}</div>
                    <div className="wi-bar"><span style={{ width: `${result.modified.score}%`, background: scoreRGB(result.modified.score) }} /></div>
                  </div>
                </div>

                <div className="wi-narr">{result.narrative}</div>
                {(result.delta.rules_removed.length > 0 || result.delta.rules_added.length > 0) && (
                  <div className="wi-difftags">
                    {result.delta.rules_removed.map(r => <span key={r} className="wi-tag rem">− {r} cleared</span>)}
                    {result.delta.rules_added.map(r => <span key={r} className="wi-tag add">+ {r} fired</span>)}
                  </div>
                )}
                {result.regulatory_basis.length > 0 && (
                  <div className="wi-cites">
                    {result.regulatory_basis.map((c, i) => <span key={i} className="wi-cite" title={c.summary}><b>{c.citation}</b> — {c.title}</span>)}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* --- orchestrator --- */}
          <div className="cr-card">
            <div className="cr-card-head"><h3>Emergency response orchestrator</h3></div>
            {orch && orch.triggered ? (
              <>
                <div className="wi-trigbar">
                  <span className="wi-band">CRITICAL</span>
                  <span className="wi-trig-txt">Triggered in <b>{orch.trigger.zone_name}</b> at <b>{orch.trigger.clock}</b> · rules [{orch.trigger.rules.join(", ")}] · score {Math.round(orch.trigger.score)}/100</span>
                </div>
                <div className="wi-actions">
                  {orch.actions.map(a => (
                    <div className="wi-action" key={a.seq}>
                      <div className="wi-seq">{a.seq}</div>
                      <div>
                        <div className="wi-a-head"><span className="wi-a-title">{a.title}</span><span className="wi-a-sla">{a.sla}</span></div>
                        <div className="wi-a-detail">{a.detail}</div>
                        {a.regulatory_basis.length > 0 && (
                          <div className="wi-cites">{a.regulatory_basis.map((c, i) => <span key={i} className="wi-cite" title={c.summary}><b>{c.citation}</b></span>)}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {orch.evacuation && (
                  <div className="wi-evac">
                    <div className="wi-evac-col">
                      <div className="wi-evac-h">Evacuate immediately</div>
                      {orch.evacuation.immediate.map((z: any) => <div key={z.id} className="wi-evac-z crit">{z.name}</div>)}
                    </div>
                    <div className="wi-evac-col">
                      <div className="wi-evac-h">Clear (precautionary)</div>
                      {orch.evacuation.precautionary.map((z: any) => <div key={z.id} className="wi-evac-z">{z.name}</div>)}
                    </div>
                    <div className="wi-evac-col">
                      <div className="wi-evac-h">Notify</div>
                      {(orch.roles || []).map((r: any, i: number) => <div key={i} className="wi-evac-z">{r.role}{r.name ? ` · ${r.name}` : ""}</div>)}
                    </div>
                  </div>
                )}

                {orch.counterfactual && orch.counterfactual.minutes_earlier != null && (
                  <div className="wi-cf">
                    <div className="wi-cf-big">{Math.floor(orch.counterfactual.minutes_earlier / 60)}h {String(orch.counterfactual.minutes_earlier % 60).padStart(2, "0")}m earlier</div>
                    <p>{orch.counterfactual.statement}</p>
                    {orch.counterfactual.prevented_downstream?.length > 0 && (
                      <div className="wi-prev">Would have pre-empted: {orch.counterfactual.prevented_downstream.map((e: any, i: number) => <b key={i}>{e.id} ({e.clock}){i < orch.counterfactual.prevented_downstream.length - 1 ? ", " : ""}</b>)}</div>
                    )}
                  </div>
                )}
              </>
            ) : (
              <p className="cr-alert-empty"><span className="ok">No compound-critical condition.</span> {orch?.reason || "No emergency response required on this shift — the correct outcome on a benign day."}</p>
            )}
          </div>
        </div>

        {/* ============ RIGHT: regulatory intelligence ============ */}
        <div className="cr-card">
          <div className="cr-card-head"><h3>Regulatory intelligence</h3></div>
          <p className="wi-sub">{cov.clause_count} clauses · {cov.sources.length} sources · covers rules {cov.rules_covered.join(", ")}. Every alert and action above is cited from this corpus.</p>
          <div className="wi-srcrow">
            {cov.sources.map(s => (
              <div className="wi-src" key={s.code}><b>{s.code}</b><span>{s.title}{s.revision ? ` · ${s.revision}` : ""}</span></div>
            ))}
          </div>
          <div className="wi-search">
            <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => { if (e.key === "Enter") search(); }} placeholder="Search the corpus (BM25)…" />
            <button className="wi-link" onClick={search}>Search</button>
          </div>
          <div>
            {hits.map((h, i) => (
              <div className="wi-hit" key={i}>
                <div className="wi-hit-top"><span className="wi-hit-cite">{h.citation}</span>{h.score != null && <span className="wi-hit-score">score {h.score}</span>}</div>
                <div className="wi-hit-title">{h.title}</div>
                <div className="wi-hit-sum">{h.summary}</div>
              </div>
            ))}
            {hits.length === 0 && <p className="cr-alert-empty">No matching clause.</p>}
          </div>
          <p className="wi-sub" style={{ marginTop: 14, marginBottom: 0 }}>Sources are faithful summaries of public provisions for demonstration; verify against the official gazette / standard before operational use.</p>
        </div>
      </div>
    </div>
  );
}
