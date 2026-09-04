# Deploying Salus

Salus ships as **one Docker service**: the image builds the React app and serves it
alongside the FastAPI `/api` routes, so there's a single public URL (and a public
webhook endpoint for real-time Razorpay recovery).

## 1. Put it on GitHub (public repo — required for the submission)

```bash
cd C:/Users/SAMSUNG/salus
git init
git branch -M main
```

Then make a clean, logical commit history (real timestamps — see the sequence in the
"Commit sequence" section below), add your empty GitHub repo as the remote, and push:

```bash
git remote add origin https://github.com/<you>/salus.git
git push -u origin main
```

## 2. Deploy on Render (single service)

1. Push the repo (step 1). The repo root already has `Dockerfile` and `render.yaml`.
2. In Render: **New + → Blueprint**, pick the `salus` repo. Render reads `render.yaml`
   and provisions one Docker web service on the free plan.
   - (Or **New + → Web Service → Docker** and point it at the repo — same result.)
3. Set the secret env vars in the Render dashboard (they are `sync: false` in the blueprint):
   - `RAZORPAY_KEY_ID` = your `rzp_test_…`
   - `RAZORPAY_KEY_SECRET` = your test secret
   - `SALUS_WEBHOOK_SECRET` = (fill after step 3)
4. Deploy. Your app is live at `https://salus-XXXX.onrender.com`.
   Health check: `/api/health`. (Free tier sleeps when idle — first hit takes ~30s.)

## 3. Real-time recovery via webhook (optional but great for the demo)

1. Razorpay Dashboard (Test Mode) → **Settings → Webhooks → Add New Webhook**.
2. URL: `https://<your-app>.onrender.com/api/webhook/razorpay`
3. Secret: choose one, and set it as `SALUS_WEBHOOK_SECRET` in Render.
4. Active events: `payment_link.paid`.

Now when a Salus-created link is paid, Razorpay calls the webhook, the HMAC signature is
verified, and the event flips to **Recovered** with no manual sync.

## Environment variables

| Var | Purpose | Needed |
| --- | --- | --- |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | test-mode API keys | for live links |
| `SALUS_WEBHOOK_SECRET` | verify webhook signatures | for real-time recovery |
| `SALUS_MODE` | `simulate` (default) or `live` | optional |
| `SALUS_SEED` | reproducible batch | optional |
| `ANTHROPIC_API_KEY` | Claude-refined Hinglish copy | optional |

## Commit sequence (honest history, real dates)

Run these in order after `git init`. They tell the real build story in ~16 logical commits.

```bash
git add .gitignore .dockerignore .claude/launch.json backend/requirements.txt backend/.env.example
git commit -m "chore: project scaffold, tooling and ignore rules"

git add backend/app/__init__.py backend/app/config.py backend/app/models.py
git commit -m "feat(models): domain models, enums and guardrails"

git add backend/app/seed.py
git commit -m "feat(data): synthetic at-risk revenue batch generator"

git add backend/app/diagnosis.py
git commit -m "feat(diagnosis): rule-based root-cause engine"

git add backend/app/policy.py
git commit -m "feat(policy): deterministic guardrail/policy engine"

git add backend/app/interventions.py
git commit -m "feat(interventions): planner, Hinglish copy and B2B receivables ladder"

git add backend/app/simulator.py
git commit -m "feat(sim): grounded outcome model and promise-to-pay probability"

git add backend/app/executor.py backend/app/llm.py
git commit -m "feat(executor): Razorpay adapter (simulate + live) and optional LLM copy"

git add backend/app/orchestrator.py
git commit -m "feat(agent): recovery loop, audit trail and promise-to-pay branch"

git add backend/app/metrics.py backend/app/store.py
git commit -m "feat(metrics): honest scoreboard and in-memory store"

git add backend/app/main.py backend/tools/smoke.py
git commit -m "feat(api): FastAPI app, SSE run stream and smoke test"

git add frontend/package.json frontend/package-lock.json frontend/vite.config.js frontend/index.html frontend/src/main.jsx frontend/src/index.css frontend/src/components.css frontend/src/lib/format.js frontend/src/lib/api.js
git commit -m "feat(web): Vite scaffold and neo-brutalist design system"

git add frontend/src/App.jsx frontend/src/components/MetricCard.jsx frontend/src/components/EventTable.jsx frontend/src/components/Chips.jsx frontend/src/components/GuardrailsCard.jsx frontend/src/components/BreakdownCard.jsx frontend/src/components/ExceptionsCard.jsx frontend/src/components/EventDrawer.jsx
git commit -m "feat(web): dashboard, ledger, event drawer and guardrail controls"

git add backend/app/live.py frontend/src/components/LivePanel.jsx
git commit -m "feat(live): real Razorpay test-mode links, status sync and webhook HMAC"

git add Dockerfile render.yaml
git commit -m "feat(deploy): single-service Docker image and Render blueprint"

git add README.md ARCHITECTURE.md DEPLOY.md
git commit -m "docs: README, architecture and deploy guide"
```

> These are real commits dated when you run them — exactly what a hackathon build looks
> like. If you'd like Claude credited, append a trailer line
> `Co-Authored-By: Claude <noreply@anthropic.com>` to any commit message.
