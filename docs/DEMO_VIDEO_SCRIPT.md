# KAVACH — Demo Video Script & Shot List
Target length: **4:50–5:00** · Record with OBS (1080p, 30 fps) · Voice: calm, factual — the numbers do the selling.

## Setup before recording
1. Backend: `cd backend && .venv\Scripts\activate && uvicorn app.main:app --port 8000` (deterministic mode = default).
2. Frontend: `cd frontend && npm run build && npm run start` (production build — smoother than dev mode).
3. Open `http://localhost:3000` in a clean browser window (hide bookmarks bar, 100% zoom, dark OS theme).
4. Second terminal ready with `python verify.py` pre-typed (for the verification shot).
5. Open `reports/KAVACH_Incident_Prevention_Report.pdf` in a tab, minimised.
6. Practice the toggle flip once so the recording take is smooth.

## Shot list

| # | Time | Screen | Narration (say this, roughly) |
|---|------|--------|--------------------------------|
| 1 | 0:00–0:25 | Control room, scenario loaded, paused at 02:00 | "January 2025. Eight workers died at a steel plant where every safety system was working — gas detectors, permits, SCADA. The investigation found the warning signals existed, but no intelligence layer connected them in time. This is KAVACH — that missing layer." |
| 2 | 0:25–0:50 | Toggle set to **BASELINE**, press Play at high speed through the night | "This is a minute-by-minute replay of a composite incident, on our deterministic digital twin. In Baseline mode you're seeing exactly what the plant's own single-sensor alarms saw. Watch the board — it stays green. All night." |
| 3 | 0:50–1:10 | Pause at ~06:25. Point at PT-GM-104 sparkline | "But look closer. This pressure sensor has been drifting upward for four hours — always below its alarm limit. No threshold system on earth flags this. " |
| 4 | 1:10–1:25 | Jump chip **06:30**. Still BASELINE — green | "06:30. A crew of five enters the basement connected to that gas main. The gas test passed — at one point only. The isolation was skipped. Baseline view: still green." |
| 5 | 1:25–2:10 | **Flip the toggle to KAVACH.** Zone goes critical; open the evidence panel; hover the four rules | "Same morning. Same data. KAVACH: CRITICAL — at 06:30, not 09:40. And it shows its work: rising gas-main trend feeding an occupied confined space… isolation omitted on the permit… single-point gas test… a shift handover that missed the drift. Four rules, live values, the exact permit — and the regulation: Factories Act Section 36, OISD-105." |
| 6 | 2:10–2:35 | Play through 08:30 and 09:30 escalations; pause at 09:40; point at the baseline alarm marker | "As the morning unfolds, KAVACH escalates: hot work twenty metres from the vent, then a valve closure driving back-pressure. Only at 09:40 does the first conventional alarm fire — fifty minutes before the explosion. KAVACH had been critical for three hours." |
| 7 | 2:35–2:55 | Metrics card close-up | "Measured, not claimed: 3 hours 9 minutes of prediction lead time. 240 minutes of warning versus 51. Zero missed hazards. Zero false alerts." |
| 8 | 2:55–3:20 | Orchestrator action timeline; then flash the auto-generated PDF report | "On the critical alert, KAVACH orchestrates the response: suspend the entry permit, isolate the main, notify, evacuate by plant connectivity, re-test, monitor — every action citing its regulation. And it writes the regulator-ready prevention report itself." |
| 9 | 3:20–3:50 | `/whatif` console: apply gas-main isolation at 06:30 → risk drops CRITICAL → ALERT | "Don't trust us — stress-test it. What if the isolation had been applied? The rule clears, risk de-escalates. This engine reasons about barriers and causes, not correlations. Judges can drive this console live." |
| 10 | 3:50–4:15 | Switch scenario to **normal_day**; show calibration moment ~10:00 | "The harder test is a normal day. A calibration test spikes this sensor to alarm level — the baseline cries wolf. KAVACH reads the work order, understands it's a calibration, and stays quiet. Zero false alerts. Operators will not mute this system." |
| 11 | 4:15–4:35 | Terminal: run `python verify.py`, scroll to **ALL CHECKS PASSED** | "Every number you've seen — lead time, detection minutes, false-positive counts, even the what-if behaviour — is asserted by an automated verification suite. The demo you just watched is deterministic and reproducible, run for run." |
| 12 | 4:35–5:00 | Architecture diagram (docs/architecture.png), then close card / title | "Under the hood: a deterministic digital twin, a compound-risk engine with eight rules, a regulatory intelligence layer, an emergency orchestrator — FastAPI and Next.js, no external dependencies. The data already exists in every plant. KAVACH makes it act in time." |

## Recording tips
- Set playback speed **10–30 min/s** for the night section, **2–5 min/s** around key moments.
- Do shots 1–8 in one take if possible (the timeline is deterministic — retakes are identical).
- Keep the cursor deliberate; hover 1 s before clicking anything you narrate.
- Export ~8–10 Mbps MP4. Upload unlisted to YouTube; put the link in the Unstop form AND the README.
