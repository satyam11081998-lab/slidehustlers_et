# KAVACH — Jury Q&A Preparation
The questions a sharp jury will ask, with the answers. Rehearse the bold lines; they are the sound bites.

---

**Q1. Don't plants already have alarm systems, trip systems, permit software? What's actually new here?**
Yes — and that's the point. Each of those watches ONE thing, deliberately: trip systems must stay simple to be certifiable, alarms are per-tag by design, permit software is a workflow tool that never sees live process data. At Vizag every one of them worked. **"Every existing system watches one signal perfectly. Nothing watches the combination — and the combination is what kills."** KAVACH is the judgment layer above them: it joins sensor *trends* with operational *context* — permits, isolations, gas tests, shift handovers — which no product on the plant's floor does today. And it retrofits: reads from their systems, replaces none, never touches the safety-instrumented layer.

**Q2. Your data is synthetic. How do we know this isn't a toy?**
Three answers. (1) Real SCADA + permit data is behind NDAs for every team in this competition — the playing field is synthetic; the question is fidelity. (2) Our twin has 34 realistically-tagged instruments with physics-consistent behaviour, and the scenario is a composite of *documented* failure modes from public investigations — sub-alarm drift, single-point gas tests, handover gaps, hot-work proximity. Ask any plant engineer: each beat is real. (3) Most importantly, **the engine doesn't know the script.** It sees only what a real plant would emit — tag values, permits, work orders. Swap the twin for OPC-UA connectors and nothing downstream changes. The twin and a real plant share one interface.

**Q3. Why hand-written rules instead of machine learning?**
Because fatal-accident data is (thankfully) too scarce to learn from, and because safety decisions must be *auditable*. Our rules encode the causal logic safety engineers already use — barrier analysis — and every alert shows its reasoning, which an ML classifier cannot honestly do. The falsifiable proof it works: the what-if console. **Restore a barrier and the risk drops; the engine reasons about causes, not correlations.** ML has a place on our roadmap — pattern mining over near-miss corpora to *propose* new rules — humans approve them.

**Q4. Won't this just add more alarms operators will ignore?**
We measured exactly that. On a fully benign day with tempting co-occurrences, the conventional baseline raises a false alarm (a calibration spike); KAVACH raises **zero**, because it reads the calibration work order and suppresses — nine context suppressions that day. Alert bands have hysteresis so scores don't flap. **False-positive discipline is a headline metric in our product, because a muted safety system is a dead safety system.**

**Q5. How is the lead-time number honest? You wrote the scenario yourselves.**
The scenario was written to be *realistic*, not convenient — the baseline system in our replay behaves exactly as the plant's real alarms would (per-tag thresholds, 3-minute persistence). Both engines see identical data. The ground-truth labels and both detection times are computed, exposed via API, and asserted by an automated verification suite anyone can run: `python verify.py`. Change the scenario and the metrics recompute honestly — we invite you to try.

**Q6. What happens on a false CRITICAL — who's liable if KAVACH suspends a permit wrongly?**
Deployment is phased exactly for this: observe (read-only) → advise (alerts with evidence, humans decide) → orchestrate (pre-approved playbooks, human gates above defined blast radius). In advisory mode a wrong alert costs a supervisor five minutes of reading the evidence panel; the plant's existing decision authority is unchanged. Orchestration is opt-in per action, and note the asymmetry: **the cost of one suppressed false alarm is minutes; the cost of one missed compound risk is Vizag.**

**Q7. Where does the LLM/AI actually matter here? Is this "AI" at all?**
The intelligence is the fusion: derived signals (trend slopes, drift detection, corroboration), an 8-rule compound-risk engine over a live operational context graph, deterministic regulatory retrieval, and an orchestrator — that's the AI that saves lives, and it's fully explainable. An LLM narrates alerts into plain language for operators (with a deterministic fallback, so the demo can't fail and the plant can't be held hostage by an API). We used AI-assisted development heavily and openly — the design, domain modelling, verification and every line were produced during this hackathon.

**Q8. Isn't KAVACH the Railways' system name?**
Yes — कवच, armour. **"Railways built KAVACH for trains; we built it for the workers inside the plants."** Different domain, same protective philosophy; we'd rename commercially if needed.

**Q9. How does this scale to another plant, or another industry?**
The engines are plant-agnostic. A plant is data: a layout JSON (zones + connectivity), tagged instruments with limits, and connector mappings. The rules operate on *categories* (confined space, gas network, hot work, isolation), not on our specific coke oven. Refinery, chemical unit, mine — same spine. That's also the business answer: onboarding is configuration, not a data-science project.

**Q10. What would it cost / who pays?**
EHS budgets already pay for compliance software with no predictive value. KAVACH lands there: Factories Act / OISD / DGMS audit pressure creates the purchase order, prevention creates the ROI (one prevented LTI pays for years of licence). Pilot: one battery, 90 days, advisory mode, priced as a compliance-analytics subscription.

**Q11. What's the weakest part of the prototype?**
Honest answer: the CCTV/vision lane of the problem statement — we scoped it to the roadmap and said so, because a mocked demo would be dishonest, and the sensor+permit fusion is where the lives are. Also, the twin models one plant section; multi-unit scale needs a streaming backbone (Kafka/Timescale) — an engineering exercise, not a research risk, and the deterministic engine core carries over unchanged.

**Q12. What did YOU learn / can you defend any line of this code?**
(For Satyam — prep points:) walk through R1's logic in `compound.py`; explain why the drift detector uses a 60-min window but "rising" uses 45; explain hysteresis bands; explain why `crc32` seeds instead of `hash()`; run verify.py live. The repo is deliberately readable — every module's docstring explains *why* it exists.

---
*Keep answers under 45 seconds each. When in doubt, drive to the what-if console — interaction beats argument.*
