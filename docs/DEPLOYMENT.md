# KAVACH — Deployment

The hosted demo is **two services**: the Next.js control room on Vercel, and the FastAPI engine on Render. Vercel cannot host WebSocket *servers*, so the engine lives on Render — the browser is still a WebSocket *client*, which Vercel serves perfectly.

**It also works with only Vercel.** The control room ships with precomputed frames in `frontend/public/demo/`, so if the API is unreachable — not deployed yet, free instance cold-starting, or network blocked — it plays the identical scenario offline instead of showing an empty screen. Deploy the frontend first and you already have a working link; add the backend to turn on live streaming.

---

## 0. Fastest path (two steps)

1. **Backend, one click:** https://render.com/deploy?repo=https://github.com/satyam11081998-lab/slidehustlers_et — Render reads [`render.yaml`](../render.yaml) and configures itself. Wait for "Live", copy the service URL.
2. **Frontend, one script:** double-click [`deploy.bat`](../deploy.bat) in the repo root. It installs the Vercel CLI, opens a browser for you to sign in, asks for the Render URL from step 1, sets the environment variable and deploys to production.

Everything below is the manual equivalent if you would rather click through the dashboards.

---

## 1. Backend → Render (5 min, gives you live WebSockets)

1. Go to **https://dashboard.render.com/select-repo?type=web** and pick `slidehustlers_et`.
2. Render detects [`render.yaml`](../render.yaml) and fills everything in. If it asks, confirm:
   - **Root Directory:** `backend`
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance:** Free
3. Deploy, then check `https://<your-service>.onrender.com/api/health` returns `{"ok":true,...}`.

> Free instances sleep after ~15 minutes idle and take ~60 s to wake. **Open `/api/health` once before a jury session or a recording.** If it is still asleep when a judge opens the link, the control room falls back to offline frames automatically — it will not break.

## 2. Frontend → Vercel (3 min)

1. Go to **https://vercel.com/new** and import `slidehustlers_et`.
2. Set **Root Directory** to `frontend`. Framework (Next.js) is auto-detected; leave the build settings alone.
3. Add an Environment Variable (Production):
   - `NEXT_PUBLIC_API_BASE` = `https://<your-service>.onrender.com` — **no trailing slash**
   - *(Skip this and the app runs purely on the offline frames — still a working demo.)*
4. Deploy. You get `https://<project>.vercel.app`.

If you deployed the frontend before the backend existed, add the variable afterwards and hit **Redeploy** — the app will switch from offline frames to the live stream.

## 3. Check it (60 seconds)

- `/` — the control room loads; the connection dot is green when the live socket is up.
- Press **Play** — the clock runs; **Baseline ⇄ KAVACH** toggle flips the same morning.
- Jump to **06:30** — Battery 4 Basement goes critical with four rules and full evidence.
- `/whatif` — apply the isolation; risk falls CRITICAL → ALERT *(needs the backend; it computes live)*.
- `/console` — raw twin view.
- `https://<render-url>/api/metrics?scenario=vizag_replay` — `lead_time_min: 189`.

## 4. Regenerating the offline frames

They are committed, so you only need this if you change the engine or a scenario:

```bash
cd backend && python export_static.py     # writes frontend/public/demo/*.json
```

## 5. Notes

- **CORS** is open (`allow_origins=["*"]`) — deliberate for a public read-only demo with no auth surface and no writes. To tighten after the hackathon, set it to your Vercel origin in `backend/app/main.py`.
- **No secrets are required.** `KAVACH_DETERMINISTIC=1` keeps the LLM narration on its template fallback, so the hosted demo needs no API key and cannot fail on a rate limit.
- **Local run** is unchanged and remains the fullest experience:
  ```bash
  cd backend && uvicorn app.main:app --port 8000
  cd frontend && npm run build && npm run start
  ```
