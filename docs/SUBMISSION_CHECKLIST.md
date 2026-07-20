# KAVACH — Submission Checklist (deadline ~20 July 2026)

Work through this top to bottom. Everything in **[YOU]** is a Satyam action; everything else is already done in the repo.

## A. Git & GitHub — do this first
- [x] Repo prepared: `.gitignore` excludes `.env`, `node_modules`, `.venv`, `__pycache__`, `.next`, internal notes (`CONTEXT.md`), and `docs/qa/`.
- [ ] **[YOU]** Double-click `push_to_github.bat` in the `kavach` folder (or run its commands in a terminal). It initialises git, commits everything, and pushes to `https://github.com/satyam11081998-lab/slidehustlers_et` (branch `main`). A browser window may open for GitHub sign-in — approve it.
- [ ] **[YOU]** On GitHub: Settings → confirm the repo is **Public** (rule: all links must be public).
- [ ] **[YOU]** Check on github.com that `README.md` renders with the architecture image, and that `backend/`, `frontend/`, `data/`, `docs/`, `reports/` are all present. Confirm **no `.env`** file appears anywhere.

## B. Verify the prototype one last time
- [ ] **[YOU]** `cd backend && python verify.py` → must end **ALL CHECKS PASSED**.
- [ ] **[YOU]** `cd frontend && npm run build` → must succeed (then `npm run start` and click through `/`, `/whatif`, `/console`).

## C. Host the live demo (recommended, ~30 min)
- [ ] **[YOU]** Follow `docs/DEPLOYMENT.md` (Render backend → Vercel frontend). Paste the Vercel URL into the README "Live demo" line and re-push (`git add -A && git commit -m "Add live demo URL" && git push`).

## D. Record the demo video (~1–2 hours incl. retakes)
- [ ] **[YOU]** Follow `docs/DEMO_VIDEO_SCRIPT.md` shot by shot (target ≤ 5:00).
- [ ] **[YOU]** Upload to YouTube as **Unlisted** (or Public). Test the link in an incognito window.
- [ ] **[YOU]** Add the video link to the README and re-push.

## E. Submit on Unstop
- [ ] **[YOU]** Working prototype link: the Vercel URL (plus GitHub repo).
- [ ] **[YOU]** GitHub link: `https://github.com/satyam11081998-lab/slidehustlers_et`
- [ ] **[YOU]** Pitch deck: upload `docs/kavach_pitch_deck.pptx` (a PDF twin is at `docs/kavach_pitch_deck.pdf` if the form prefers PDF).
- [ ] **[YOU]** Demo video: the YouTube link.
- [ ] **[YOU]** Architecture diagram (if asked separately): `docs/architecture.png`.
- [ ] **[YOU]** Submit well before the deadline — Unstop does not accept late submissions.

## F. Finale prep (after shortlist)
- [ ] Rehearse with `docs/JURY_QA_PREP.md` — answers under 45 s.
- [ ] Warm the Render backend before going on stage (`/api/health`).
- [ ] End the pitch at the what-if console and hand the jury the controls.

## Compliance notes (already handled, know them for Q&A)
- All code, data, documents and assets were created during the hackathon; the plant data is synthetic and labelled as such on every surface (rule: original work).
- Open-source tools only (FastAPI, Next.js, pptx tooling); no licensed datasets.
- No secrets in the repo: OpenAI key lives only in `.env` (gitignored); deterministic fallback means the system runs fully without it.
