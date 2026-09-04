from __future__ import annotations

from .models import Diagnosis, EventType, InterventionType as IT, RevenueEvent, RootCause

# error_reason -> (root_cause, recoverable, confidence, suggested interventions)
_REASON_MAP: dict[str, tuple[RootCause, bool, float, list[IT]]] = {
    "insufficient_funds": (RootCause.INSUFFICIENT_FUNDS, True, 0.90, [IT.SMART_RETRY, IT.REMINDER_MESSAGE]),
    "mandate_insufficient_funds": (RootCause.INSUFFICIENT_FUNDS, True, 0.90, [IT.MANDATE_RETRY, IT.REMINDER_MESSAGE]),
    "card_expired": (RootCause.CARD_EXPIRED, True, 0.95, [IT.NEW_PAYMENT_LINK, IT.REMINDER_MESSAGE]),
    "incorrect_cvv": (RootCause.AUTHENTICATION_FAILED, True, 0.85, [IT.NEW_PAYMENT_LINK, IT.REMINDER_MESSAGE]),
    "payment_declined_by_bank": (RootCause.DO_NOT_HONOR, True, 0.60, [IT.RETRY_ALT_METHOD, IT.REMINDER_MESSAGE]),
    "issuer_bank_not_available": (RootCause.ISSUER_DOWN, True, 0.90, [IT.SMART_RETRY]),
    "payment_gateway_timeout": (RootCause.NETWORK_TIMEOUT, True, 0.92, [IT.SMART_RETRY]),
    "npci_unavailable": (RootCause.NETWORK_TIMEOUT, True, 0.92, [IT.SMART_RETRY]),
    "upi_collect_expired": (RootCause.NETWORK_TIMEOUT, True, 0.80, [IT.NEW_PAYMENT_LINK, IT.REMINDER_MESSAGE]),
    "transaction_limit_exceeded": (RootCause.LIMIT_EXCEEDED, True, 0.80, [IT.RETRY_ALT_METHOD, IT.EMI_OFFER, IT.REMINDER_MESSAGE]),
    "mandate_revoked": (RootCause.MANDATE_REVOKED, True, 0.88, [IT.REMINDER_MESSAGE, IT.ESCALATE_HUMAN]),
    "disputed": (RootCause.INVOICE_DISPUTE, False, 0.75, [IT.ESCALATE_HUMAN]),
}

_HUMAN: dict[RootCause, str] = {
    RootCause.INSUFFICIENT_FUNDS: "Customer's account lacked balance at charge time — highly retryable once funds land (e.g. post-payday).",
    RootCause.CARD_EXPIRED: "Saved card has expired — needs the customer to enter a fresh card via a new link.",
    RootCause.AUTHENTICATION_FAILED: "Authentication failed (CVV/OTP) — a clean re-attempt on a fresh link usually clears it.",
    RootCause.DO_NOT_HONOR: "Bank declined without a specific reason ('do not honor') — an alternate method often succeeds.",
    RootCause.ISSUER_DOWN: "Issuing bank was temporarily unreachable — a timed retry after recovery is very likely to succeed.",
    RootCause.NETWORK_TIMEOUT: "Transient network/gateway timeout — not the customer's fault; a short-delay retry usually works.",
    RootCause.LIMIT_EXCEEDED: "Per-transaction limit hit — split via EMI or nudge to an alternate method.",
    RootCause.RISK_BLOCKED: "Flagged by fraud checks — must NOT be auto-retried; routed to a human reviewer.",
    RootCause.MANDATE_REVOKED: "Subscription mandate was revoked — requires the customer to re-authorise; cannot silently retry.",
    RootCause.ABANDONED_HESITATION: "Checkout abandoned mid-flow — a gentle, well-timed nudge with a ready link recovers many of these.",
    RootCause.ABANDONED_PRICE: "High-value cart abandoned — price is the likely blocker; offer EMI within policy bounds.",
    RootCause.INVOICE_FORGOTTEN: "Invoice simply overdue — a polite reminder plus a one-tap pay link is usually enough.",
    RootCause.INVOICE_DISPUTE: "Invoice is disputed — chasing payment is inappropriate; route to a human/AR owner.",
    RootCause.UNKNOWN: "Cause could not be determined from available signals.",
}


def _signals(ev: RevenueEvent) -> list[str]:
    s = [f"type={ev.type.value}", f"method={ev.method or 'n/a'}",
         f"amount=₹{ev.amount_paise // 100:,}", f"attempts={ev.attempt_count}",
         f"age={ev.age_hours:.0f}h", f"ltv=₹{ev.customer.ltv_paise // 100:,}"]
    if ev.error_reason:
        s.append(f"error_reason={ev.error_reason}")
    if ev.error_source:
        s.append(f"error_source={ev.error_source}")
    if ev.risk_flag:
        s.append("risk_flag=true")
    return s


def diagnose(ev: RevenueEvent) -> Diagnosis:
    """Rule-based root-cause diagnosis (always available, no keys needed)."""
    signals = _signals(ev)

    # Fraud flag dominates everything — this is a safety invariant.
    if ev.risk_flag:
        return Diagnosis(
            root_cause=RootCause.RISK_BLOCKED, confidence=0.99, recoverable=False,
            rationale=_HUMAN[RootCause.RISK_BLOCKED], signals=signals,
            suggested=[IT.ESCALATE_HUMAN], source="rules")

    if ev.error_reason and ev.error_reason in _REASON_MAP:
        rc, recoverable, conf, suggested = _REASON_MAP[ev.error_reason]
        return Diagnosis(root_cause=rc, confidence=conf, recoverable=recoverable,
                         rationale=_HUMAN[rc], signals=signals, suggested=list(suggested),
                         source="rules")

    if ev.type == EventType.CHECKOUT_ABANDONMENT:
        if ev.amount_paise >= 10_000 * 100:
            rc, suggested = RootCause.ABANDONED_PRICE, [IT.REMINDER_MESSAGE, IT.EMI_OFFER, IT.NEW_PAYMENT_LINK]
        else:
            rc, suggested = RootCause.ABANDONED_HESITATION, [IT.REMINDER_MESSAGE, IT.NEW_PAYMENT_LINK]
        return Diagnosis(root_cause=rc, confidence=0.62, recoverable=True,
                         rationale=_HUMAN[rc], signals=signals, suggested=suggested, source="rules")

    if ev.type == EventType.INVOICE_OVERDUE:
        rc = RootCause.INVOICE_FORGOTTEN
        # A real B2B receivables ladder: gentle nudge -> firm reminder+link ->
        # capture a promise-to-pay -> final notice -> hand to a human AR owner.
        return Diagnosis(root_cause=rc, confidence=0.80, recoverable=True,
                         rationale=_HUMAN[rc], signals=signals,
                         suggested=[IT.REMINDER_MESSAGE, IT.NEW_PAYMENT_LINK,
                                    IT.PROMISE_TO_PAY, IT.FINAL_NOTICE, IT.ESCALATE_HUMAN],
                         source="rules")

    return Diagnosis(root_cause=RootCause.UNKNOWN, confidence=0.3, recoverable=False,
                     rationale=_HUMAN[RootCause.UNKNOWN], signals=signals,
                     suggested=[IT.ESCALATE_HUMAN], source="rules")
