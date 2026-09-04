# Salus — Architecture

## 1. Principle

**The LLM proposes; the deterministic policy engine disposes.**

Generation is cheap and creative; authority over money must be bounded and auditable. Salus
therefore separates the two concerns completely:

- **Reasoning layer** (diagnosis + intervention drafting, optionally LLM-assisted) decides *what the
  problem is* and *what we could do about it*.
- **Policy layer** (a pure, deterministic rule engine) decides *what is actually permitted*.

An action reaches Razorpay only if the policy layer returns `ALLOW` or `DEFER`. This is the
"every money action is explainable, bounded and gated" guarantee, and it lives in code
(`app/policy.py`), never in a prompt.

## 2. The recovery loop

For each at-risk event (`app/orchestrator.py`):

```
DETECT    log the event (amount, failure envelope, customer)
DIAGNOSE  root cause + recoverability + confidence           (app/diagnosis.py)
PLAN      ordered candidate interventions + drafted copy      (app/interventions.py)
loop over candidates:
  GATE    policy decision: allow / defer / block / escalate   (app/policy.py)
  EXECUTE if allowed → Razorpay payment link / retry          (app/executor.py)
  OUTCOME simulate or observe recovery                        (app/simulator.py)
  STOP    on recovery, or when levers/guardrails are exhausted
```

Every step appends an `AuditEntry`. The event's terminal status is one of
`recovered | lost | escalated`.

## 3. Data model (`app/models.py`)

- `RevenueEvent` — an at-risk item with a Razorpay-shaped failure envelope
  (`error_code`, `error_source`, `error_step`, `error_reason`, `method`, `risk_flag`).
- `Diagnosis` — `root_cause`, `confidence`, `recoverable`, human `rationale`, `signals`, `suggested`.
- `Intervention` — a concrete action with a `channel`, `cost_paise`, drafted `message`, a Razorpay
  ref, and the `PolicyResult` that gated it.
- `PolicyResult` — `decision` (allow/defer/block/escalate) + `reasons` + `fired_rules`.
- `EventRecord` — the full story of one event: event + diagnosis + interventions + outcome + audit.
- `Guardrails` — the tunable, enforced policy (see below).
- `Metrics` / `RunSummary` — the scoreboard.

Money is stored in **paise** throughout (Razorpay convention); the UI formats to rupees.

## 4. Diagnosis (`app/diagnosis.py`)

Deterministic mapping from the Razorpay failure envelope → root cause, recoverability, confidence,
and an *ordered* list of suggested interventions. Root cause and recoverability are **always**
rule-derived so the money-relevant decision is auditable. A safety invariant sits on top: a
`risk_flag` forces `RISK_BLOCKED` (not recoverable → escalate), regardless of anything else.

The optional LLM (`app/llm.py`) may only **refine the customer-facing copy**. It cannot change the
diagnosis, recoverability, or the gate. Without a key, callers fall back silently.

## 5. Policy engine (`app/policy.py`) — the guardrails

Evaluated per candidate action against tunable `Guardrails` and per-run `RunState`:

| Rule | Behaviour |
| --- | --- |
| `escalate_risk_blocked` | fraud-flagged → **escalate**, never auto-retry |
| `human_review_amount` | very large exposure (default ₹2,00,000) → **escalate** to a human AR owner, any action |
| `respect_opt_out` | opted-out customer → outbound comms **blocked** (silent retry still allowed) |
| `max_auto_amount` | *auto-charge* (silent retry) over the ceiling (default ₹50,000) → **escalate**; outreach is exempt so large receivables can still be chased |
| `max_retries` | retry cap per event (default 3) → **block** further retries |
| `max_contacts_per_customer` | contact cap across channels & runs (default 4) → **block** |
| `min_gap_hours` | too soon since last contact → **defer** |
| quiet hours | 21:00–08:00 IST → **defer** to the next allowed window |

`RunState` tracks contacts-per-customer, retries-per-event, last-contact time and spend, so caps
hold *across* actions within a run. The engine is pure (read-only); the orchestrator writes state
after a successful execution.

## 5b. Receivables ladder & promise-to-pay

Overdue B2B invoices don't get one nudge — they get a **timed, escalating sequence**
(`app/interventions.py`): gentle reminder → firm reminder + payment link → **promise-to-pay
capture** → final notice → escalate to a human AR owner. Each rung carries a `step` and
`firmness` (gentle/firm/final) that drives both the copy and the schedule spacing, and each is
independently policy-gated. The orchestrator walks the ladder in order and stops the moment the
invoice is paid or a commitment is captured.

**Promise-to-pay** is a first-class outcome: if the customer commits to a date rather than paying
now, the agent records `promised` + `promise_amount` + `promise_due`, halts further chasing, and
reports the event in its own bucket — honestly *not* counted as recovered (unpaid) nor lost.

## 6. Execution (`app/executor.py`)

One interface, two backends:

- **simulate** — mints realistic payment-link refs (`plink_…` / `rzp.io/i/…`); sends nothing real.
- **live** — calls the Razorpay **test-mode** REST API (`POST /v1/payment_links`) with basic auth
  built from `rzp_test_` keys.

The orchestrator is backend-agnostic.

## 7. Outcomes (`app/simulator.py`)

In simulate mode each `(root_cause, intervention)` pair has a grounded base recovery probability —
transient timeouts recover far more often than a hard "do not honor" — damped by a global realism
factor and by attempt number. Outcomes are rolled from a **seeded** RNG in fixed event order, so a
run is fully reproducible. In live mode this module is bypassed; the real payment status is the
outcome.

## 8. Honest metrics (`app/metrics.py`)

- **Recovery rate = recovered ÷ (recovered + lost)** — the agent's batting average on what it
  actually *attempted*. Escalated events are deliberately excluded from the denominator because
  they were correctly *not* attempted (routed to a human). A `gross_recovery_rate` over the full
  batch is also computed for transparency.
- **Cost of recovery** = real messaging cost; **net recovered** = recovered − cost.
- **by_root_cause** and **by_intervention** breakdowns, plus counts of actions taken / blocked /
  deferred so the bounded behaviour is measurable, not just claimed.

## 9. API (`app/main.py`)

`GET /api/events`, `GET /api/events/{id}`, `GET|PUT /api/guardrails`, `GET /api/metrics`,
`GET /api/summary`, `GET /api/audit`, `POST /api/reset`, `POST /api/run`, and
`GET /api/run/stream` (Server-Sent Events) which streams per-event progress so the dashboard
animates the recovery live.

## 10. Frontend (`frontend/`)

React + Vite, neo-brutalist design system (`src/index.css` + `src/components.css`). It consumes the
SSE feed for the live run, renders the scoreboard, the at-risk ledger, the tunable guardrail panel,
the root-cause breakdown, the honest exception list, and a per-event drawer showing diagnosis,
gated actions (with the drafted message), and the full audit timeline.

## 11. Extending to production

- Swap the in-memory `Store` for a database; the models are already serialisable.
- Replace the outcome simulator with Razorpay webhook ingestion + status polling.
- Add channel adapters (WhatsApp Business API, MSG91) behind the existing `Channel` abstraction.
- Layer an AP2/UAP signed-mandate check into the policy engine so each action carries cryptographic
  authorization for the agentic-payments world.
