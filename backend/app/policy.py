from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .config import IST
from .models import (Channel, Diagnosis, GateDecision, Guardrails, Intervention,
                     InterventionType as IT, PolicyResult, RevenueEvent, RootCause)

_RETRY_TYPES = {IT.SMART_RETRY, IT.MANDATE_RETRY, IT.RETRY_ALT_METHOD}
# Actions that pull money WITHOUT the customer re-confirming — these are the ones
# the auto-charge ceiling gates. Outreach (links/reminders) is not auto-charge.
_AUTO_CHARGE = {IT.SMART_RETRY, IT.MANDATE_RETRY}


@dataclass
class RunState:
    """Mutable per-run bookkeeping the policy engine reads and the orchestrator writes."""
    contacts_by_customer: dict[str, int] = field(default_factory=dict)
    retries_by_event: dict[str, int] = field(default_factory=dict)
    last_contact_at: dict[str, datetime] = field(default_factory=dict)
    total_cost_paise: int = 0

    def contacts(self, cust_id: str, prior: int) -> int:
        return prior + self.contacts_by_customer.get(cust_id, 0)


def _in_quiet_hours(dt: datetime, g: Guardrails) -> bool:
    h = dt.astimezone(IST).hour
    return h >= g.quiet_start_hour or h < g.quiet_end_hour


def _next_allowed_send(dt: datetime, g: Guardrails) -> datetime:
    dt = dt.astimezone(IST)
    if not _in_quiet_hours(dt, g):
        return dt
    # push to the next quiet_end_hour boundary
    target = dt.replace(hour=g.quiet_end_hour, minute=0, second=0, microsecond=0)
    if dt.hour >= g.quiet_start_hour:
        target = target + timedelta(days=1)
    return target


def evaluate(ev: RevenueEvent, dg: Diagnosis, iv: Intervention,
             g: Guardrails, state: RunState) -> PolicyResult:
    reasons: list[str] = []
    fired: list[str] = []
    is_contact = iv.channel != Channel.NONE
    is_retry = iv.type in _RETRY_TYPES

    if iv.type == IT.ESCALATE_HUMAN:
        return PolicyResult(decision=GateDecision.ESCALATE,
                            reasons=["Routed to a human reviewer."], fired_rules=["escalate_action"])

    if dg.root_cause == RootCause.RISK_BLOCKED and g.escalate_risk_blocked:
        return PolicyResult(decision=GateDecision.ESCALATE,
                            reasons=["Fraud-flagged — auto-recovery disabled; human review required."],
                            fired_rules=["escalate_risk_blocked"])

    if ev.amount_paise > g.human_review_amount_paise:
        return PolicyResult(
            decision=GateDecision.ESCALATE,
            reasons=[f"Amount ₹{ev.amount_paise // 100:,} exceeds human-review ceiling "
                     f"₹{g.human_review_amount_paise // 100:,} — assigned to a human."],
            fired_rules=["human_review_amount"])

    if g.respect_opt_out and ev.customer.opted_out and is_contact:
        return PolicyResult(decision=GateDecision.BLOCK,
                            reasons=["Customer opted out of communication — outreach suppressed."],
                            fired_rules=["respect_opt_out"])


    if iv.type in _AUTO_CHARGE and ev.amount_paise > g.max_auto_amount_paise:
        return PolicyResult(
            decision=GateDecision.ESCALATE,
            reasons=[f"Auto-charge of ₹{ev.amount_paise // 100:,} exceeds auto ceiling "
                     f"₹{g.max_auto_amount_paise // 100:,} — human approval required."],
            fired_rules=["max_auto_amount"])

    if is_retry and state.retries_by_event.get(ev.id, 0) >= g.max_retries:
        return PolicyResult(decision=GateDecision.BLOCK,
                            reasons=[f"Retry cap ({g.max_retries}) reached for this event."],
                            fired_rules=["max_retries"])

    if is_contact and state.contacts(ev.customer.id, ev.customer.prior_contacts) >= g.max_contacts_per_customer:
        return PolicyResult(decision=GateDecision.BLOCK,
                            reasons=[f"Contact cap ({g.max_contacts_per_customer}) reached for this customer."],
                            fired_rules=["max_contacts_per_customer"])

    reschedule = None
    if is_contact:
        base = iv.scheduled_for or datetime.now(IST)
        # min gap since last contact
        last = state.last_contact_at.get(ev.customer.id)
        if last is not None:
            earliest = last + timedelta(hours=g.min_gap_hours)
            if base < earliest:
                base = earliest
                fired.append("min_gap_hours")
                reasons.append(f"Held to respect {g.min_gap_hours}h gap between contacts.")
        # quiet hours
        if _in_quiet_hours(base, g):
            base = _next_allowed_send(base, g)
            fired.append("quiet_hours")
            reasons.append("Deferred out of quiet hours (21:00–08:00 IST).")
        if fired:
            return PolicyResult(decision=GateDecision.DEFER, reasons=reasons,
                                fired_rules=fired, reschedule_to=base)

    return PolicyResult(decision=GateDecision.ALLOW,
                        reasons=["Within all guardrails."], fired_rules=[])
