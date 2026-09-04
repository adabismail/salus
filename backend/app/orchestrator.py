from __future__ import annotations

import random
from datetime import timedelta
from typing import Any, Iterator

from . import llm
from .diagnosis import diagnose
from .executor import execute
from .interventions import plan
from .models import (AuditEntry, Channel, EventRecord, EventStatus, GateDecision,
                     Guardrails, InterventionType as IT, Outcome, now_ist)
from .policy import RunState, evaluate
from .simulator import promise_probability, recovery_probability, roll, settle_hours

_RETRY_TYPES = {IT.SMART_RETRY, IT.MANDATE_RETRY, IT.RETRY_ALT_METHOD}


class Orchestrator:
    def __init__(self, records: list[EventRecord], guardrails: Guardrails, seed: int):
        self.records = records
        self.guardrails = guardrails
        self.state = RunState()
        self.rng = random.Random(seed * 2654435761 % (2**32))
        self.started_at = now_ist()

    def _log(self, rec: EventRecord, phase: str, actor: str, summary: str,
             detail: dict[str, Any] | None = None, cost: int = 0) -> None:
        rec.audit.append(AuditEntry(event_id=rec.event.id, phase=phase, actor=actor,
                                    summary=summary, detail=detail or {}, cost_paise=cost))

    def run(self) -> Iterator[dict[str, Any]]:
        recovered_paise = 0
        recovered_count = 0
        for i, rec in enumerate(self.records, start=1):
            self._process(rec)
            if rec.status == EventStatus.RECOVERED:
                recovered_paise += rec.outcome.recovered_amount_paise
                recovered_count += 1
            yield {
                "type": "event",
                "processed": i,
                "total": len(self.records),
                "event_id": rec.event.id,
                "status": rec.status.value,
                "amount_paise": rec.event.amount_paise,
                "root_cause": rec.diagnosis.root_cause.value if rec.diagnosis else None,
                "recovered_paise_so_far": recovered_paise,
                "recovered_count_so_far": recovered_count,
            }
        yield {"type": "done", "processed": len(self.records)}

    def _process(self, rec: EventRecord) -> None:
        ev = rec.event
        rec.status = EventStatus.IN_RECOVERY
        self._log(rec, "detect", "agent",
                  f"Detected {ev.type.value} of ₹{ev.amount_paise // 100:,} for {ev.customer.name}.",
                  {"error_reason": ev.error_reason, "method": ev.method})

        dg = diagnose(ev)
        rec.diagnosis = dg
        self._log(rec, "diagnose", "agent",
                  f"Root cause: {dg.root_cause.value} ({int(dg.confidence * 100)}% conf).",
                  {"rationale": dg.rationale, "recoverable": dg.recoverable,
                   "suggested": [s.value for s in dg.suggested]})

        candidates = plan(rec)
        self._log(rec, "plan", "agent",
                  f"Planned {len(candidates)} candidate action(s).",
                  {"actions": [c.type.value for c in candidates]})

        attempt_idx = 0
        acted = False
        for iv in candidates:
            gate = evaluate(ev, dg, iv, self.guardrails, self.state)
            iv.gate = gate
            rec.interventions.append(iv)
            self._log(rec, "gate", "policy",
                      f"{iv.type.value}: {gate.decision.value.upper()} — {'; '.join(gate.reasons)}",
                      {"fired_rules": gate.fired_rules})

            if gate.decision == GateDecision.ESCALATE:
                rec.status = EventStatus.ESCALATED
                self._log(rec, "stop", "human",
                          "Escalated to a human reviewer; agent will not act further.")
                return
            if gate.decision == GateDecision.BLOCK:
                continue

            if gate.decision == GateDecision.DEFER and gate.reschedule_to:
                iv.scheduled_for = gate.reschedule_to

            if iv.message and "{link}" in (iv.message or ""):
                iv.message = llm.refine_message(ev, dg, iv.message)

            execute(ev, iv)
            acted = True

            if iv.channel != Channel.NONE:
                cid = ev.customer.id
                self.state.contacts_by_customer[cid] = self.state.contacts_by_customer.get(cid, 0) + 1
                self.state.last_contact_at[cid] = iv.scheduled_for or now_ist()
            if iv.type in _RETRY_TYPES:
                self.state.retries_by_event[ev.id] = self.state.retries_by_event.get(ev.id, 0) + 1
            self.state.total_cost_paise += iv.cost_paise
            rec.total_cost_paise += iv.cost_paise

            self._log(rec, "execute", "razorpay",
                      f"Executed {iv.type.value}"
                      + (f" via {iv.channel.value}" if iv.channel != Channel.NONE else "")
                      + (f" (cost ₹{iv.cost_paise / 100:.2f})" if iv.cost_paise else ""),
                      {"razorpay_ref": iv.razorpay_ref, "message": iv.message,
                       "scheduled_for": iv.scheduled_for.isoformat() if iv.scheduled_for else None},
                      cost=iv.cost_paise)

            if iv.type == IT.PROMISE_TO_PAY:
                pp = promise_probability(dg.root_cause, attempt_idx)
                got = roll(self.rng, pp)
                iv.succeeded = got
                attempt_idx += 1
                if got:
                    due = (iv.scheduled_for or now_ist()) + timedelta(days=7)
                    rec.outcome = Outcome(
                        promised=True, promise_amount_paise=ev.amount_paise, promise_due=due,
                        winning_intervention=iv.type, attempts=attempt_idx,
                        note=f"Customer committed to pay by {due.date()} (p={pp:.2f}).")
                    rec.status = EventStatus.PROMISE_TO_PAY
                    self._log(rec, "outcome", "razorpay",
                              f"Promise-to-pay secured for ₹{ev.amount_paise // 100:,}, due {due.date()}.",
                              {"probability": round(pp, 3)})
                    self._log(rec, "stop", "agent",
                              "Stopping rule: commitment captured — tracked, not chased further.")
                    return
                self._log(rec, "outcome", "razorpay",
                          f"No commitment given (p={pp:.2f}); moving to final notice.")
                continue

            p = recovery_probability(dg.root_cause, iv.type, attempt_idx)
            success = roll(self.rng, p)
            iv.succeeded = success
            attempt_idx += 1

            if success:
                settle = settle_hours(iv.type, self.rng)
                recovered_at = (iv.scheduled_for or now_ist()) + timedelta(hours=settle)
                rec.outcome = Outcome(
                    recovered=True, recovered_amount_paise=ev.amount_paise,
                    recovered_at=recovered_at, winning_intervention=iv.type,
                    attempts=attempt_idx,
                    note=f"Recovered via {iv.type.value} (p={p:.2f}).")
                rec.status = EventStatus.RECOVERED
                self._log(rec, "outcome", "razorpay",
                          f"Recovered ₹{ev.amount_paise // 100:,} via {iv.type.value}.",
                          {"probability": round(p, 3)})
                self._log(rec, "stop", "agent",
                          "Stopping rule: amount recovered — no further action taken.")
                return
            self._log(rec, "outcome", "razorpay",
                      f"{iv.type.value} did not recover (p={p:.2f}); trying next lever.",
                      {"probability": round(p, 3)})

        if not acted:
            rec.status = EventStatus.ESCALATED
            self._log(rec, "stop", "human",
                      "Every available action was blocked by policy — escalated to a human "
                      "instead of breaching a guardrail.")
        else:
            rec.status = EventStatus.LOST
            rec.outcome.attempts = attempt_idx
            self._log(rec, "outcome", "agent",
                      "Recovery levers exhausted within guardrails; marked as not recovered.")
