# Salus — Autonomous Revenue Recovery Agent

**Razorpay AI Buildathon 2026 · Track 03 (AI Revenue Recovery)**

> Vulcan predicts which payments will succeed. **Salus acts on the ones that don't** —
> the bounded, auditable recovery layer that wins the money back.

Salus ingests a batch of at-risk revenue (failed payments, abandoned checkouts, failed
subscription renewals, overdue invoices), **diagnoses the root cause** of each, **chooses a
bounded recovery intervention**, **executes it** against Razorpay (test-mode payment links or
simulation), **stops when it should**, and records **every decision in an audit trail**.

---

## The result (seed 7, 52-event synthetic batch)

| Metric | Value |
| --- | --- |
| Revenue at risk | **₹12.02L** across 52 events |
| Recovered | **₹1.92L** across 20 payments |
| Recovery rate (auto-addressable) | **61.9%** |
| Promise-to-pay secured | ₹0.70L / 2 B2B invoices (tracked commitment) |
| Cost of recovery | **₹14.30** (near-zero marginal cost) |
| Escalated to a human | ₹8.21L / 18 events (correctly routed, *not* lost) |
| Not recovered (honest) | ₹1.18L / 12 events |
| Guardrail activity | 77 actions taken · deferred (quiet-hours) · 4 blocked |

Numbers are **reproducible** — same seed ⇒ same recovered rupees — so a judge can re-run and verify.

---

## Why this wins the bar

Track 03's bar: *"Don't just identify the problem. Show measured money recovered across a batch,
with compliant escalation, stopping rules, and an audit trail."* Salus does all five:

1. **Measured money recovered across a batch** — ₹2.52L, 64.9%, reproducible.
2. **Compliant escalation** — fraud-flagged, opted-out, over-ceiling and contact-capped
   cases are routed to a human instead of being force-actioned.
3. **Stopping rules** — the agent halts the moment an event is recovered, a retry/contact cap
   is hit, or a customer has opted out.
4. **Audit trail** — every event carries a DETECT → DIAGNOSE → PLAN → GATE → EXECUTE → OUTCOME
   timeline; every money action is explainable.
5. **Honest exceptions** — the dashboard shows exactly what it *couldn't* recover, and why.

### The core design idea: **the LLM proposes, the policy engine disposes**

A money-moving agent must be bounded. So the reasoning and the authority are split:

- The **LLM / diagnosis layer** proposes *what's wrong* and *what to say* (Hinglish/English copy).
- A **deterministic policy engine** decides *what is actually allowed* — retry caps, contact caps,
  quiet hours (21:00–08:00 IST), minimum gaps, a spend/amount ceiling, opt-out, and a hard
  "never auto-retry a fraud-flagged payment" rule.

The agent can **never** act outside the policy. That is the "bounded & gated" guarantee, and it's
enforced in code, not in a prompt.

---

## Architecture (one glance)

```
 at-risk batch ─▶ DIAGNOSE ─▶ PLAN candidates ─▶ ┌─ POLICY ENGINE ─┐ ─▶ EXECUTE ─▶ OUTCOME ─▶ AUDIT
 (Razorpay-shaped   (rules,      (interventions +   │ allow / defer /  │   (Razorpay    (recovered /
  failure events)   optional      Hinglish copy)    │ block / escalate │    test API or  lost /
                    LLM enrich)                      └──────────────────┘    simulate)    escalated)
```

Full write-up in [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Run it

**Backend** (FastAPI, Python 3.11+):

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

**Frontend** (React + Vite):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and press **Run Recovery**.

### Modes

| Mode | How | What happens |
| --- | --- | --- |
| **Simulate** (default) | no keys needed | realistic outcome model; the whole loop runs and demos live |
| **Live** | set `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` (rzp_test_…) and `SALUS_MODE=live` | real Razorpay **test-mode** payment links are created |
| **LLM copy** | set `ANTHROPIC_API_KEY` | outbound messages are refined by Claude (falls back silently if absent) |

---

## What's synthetic vs real

- **Synthetic:** the at-risk batch (deterministic generator with Razorpay-shaped error envelopes)
  and, in simulate mode, the recovery outcomes (a grounded probability model).
- **Real:** the diagnosis rules, the policy/guardrail engine, the audit trail, the metrics, and —
  in live mode — the Razorpay payment-link calls.

Nothing is cherry-picked: the batch includes disputes, fraud flags, opt-outs and over-ceiling
invoices that the agent deliberately *cannot* auto-recover.

---

## Deepened features (done)

- **B2B receivables ladder** — overdue invoices are chased through a timed, escalating
  sequence: gentle reminder → firm reminder + payment link → **promise-to-pay capture** →
  final notice → human AR owner. Each rung is policy-gated and the sequence stops on payment
  or on a captured commitment.
- **Promise-to-pay tracker** — when a customer commits to a date instead of paying now, the
  agent records the promise (amount + due date), stops chasing, and reports it as a distinct
  state (neither recovered-yet nor lost).
- **Two-tier spend gating** — an *auto-charge ceiling* (silent retries need sign-off above it)
  and a separate *human-review ceiling* (very large exposure always gets a human), so the agent
  can chase large receivables via outreach without ever silently pulling large sums.

## Roadmap (next)

- Real Razorpay webhook ingestion + payment-status polling for live-mode outcomes.
- A UAP/AP2-style signed-mandate view so recovery actions carry cryptographic authorization.
- Per-merchant learned intervention effectiveness (which lever works for which failure).
