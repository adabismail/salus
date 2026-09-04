from __future__ import annotations

import random

from .models import InterventionType as IT, RootCause

# (root_cause, intervention) -> base recovery probability on the first attempt
_EFFECT: dict[tuple[RootCause, IT], float] = {
    (RootCause.INSUFFICIENT_FUNDS, IT.SMART_RETRY): 0.42,
    (RootCause.INSUFFICIENT_FUNDS, IT.MANDATE_RETRY): 0.40,
    (RootCause.INSUFFICIENT_FUNDS, IT.REMINDER_MESSAGE): 0.18,
    (RootCause.CARD_EXPIRED, IT.NEW_PAYMENT_LINK): 0.55,
    (RootCause.CARD_EXPIRED, IT.REMINDER_MESSAGE): 0.33,
    (RootCause.AUTHENTICATION_FAILED, IT.NEW_PAYMENT_LINK): 0.60,
    (RootCause.AUTHENTICATION_FAILED, IT.REMINDER_MESSAGE): 0.30,
    (RootCause.DO_NOT_HONOR, IT.RETRY_ALT_METHOD): 0.35,
    (RootCause.DO_NOT_HONOR, IT.REMINDER_MESSAGE): 0.15,
    (RootCause.ISSUER_DOWN, IT.SMART_RETRY): 0.78,
    (RootCause.NETWORK_TIMEOUT, IT.SMART_RETRY): 0.82,
    (RootCause.NETWORK_TIMEOUT, IT.NEW_PAYMENT_LINK): 0.50,
    (RootCause.NETWORK_TIMEOUT, IT.REMINDER_MESSAGE): 0.40,
    (RootCause.LIMIT_EXCEEDED, IT.RETRY_ALT_METHOD): 0.40,
    (RootCause.LIMIT_EXCEEDED, IT.EMI_OFFER): 0.45,
    (RootCause.LIMIT_EXCEEDED, IT.REMINDER_MESSAGE): 0.20,
    (RootCause.ABANDONED_HESITATION, IT.REMINDER_MESSAGE): 0.32,
    (RootCause.ABANDONED_HESITATION, IT.NEW_PAYMENT_LINK): 0.28,
    (RootCause.ABANDONED_PRICE, IT.REMINDER_MESSAGE): 0.22,
    (RootCause.ABANDONED_PRICE, IT.EMI_OFFER): 0.40,
    (RootCause.ABANDONED_PRICE, IT.NEW_PAYMENT_LINK): 0.25,
    (RootCause.INVOICE_FORGOTTEN, IT.REMINDER_MESSAGE): 0.50,
    (RootCause.INVOICE_FORGOTTEN, IT.NEW_PAYMENT_LINK): 0.45,
    (RootCause.INVOICE_FORGOTTEN, IT.FINAL_NOTICE): 0.38,
    (RootCause.MANDATE_REVOKED, IT.REMINDER_MESSAGE): 0.40,
}


def promise_probability(root_cause: RootCause, attempt_idx: int) -> float:
    """Chance a customer commits to a promise-to-pay when asked (B2B receivables)."""
    base = 0.55 if root_cause == RootCause.INVOICE_FORGOTTEN else 0.30
    return base * (0.9 ** attempt_idx)


# Global realism damping — keeps the batch's recovery rate in a defensible band
# rather than an implausibly rosy one. Tune in one place.
_REALISM = 0.82


def recovery_probability(root_cause: RootCause, itype: IT, attempt_idx: int) -> float:
    """attempt_idx is 0 for the first action on an event, then 1, 2 ..."""
    base = _EFFECT.get((root_cause, itype), 0.08)
    return base * _REALISM * (0.85 ** attempt_idx)


def settle_hours(itype: IT, rng: random.Random) -> float:
    if itype in (IT.SMART_RETRY, IT.MANDATE_RETRY, IT.RETRY_ALT_METHOD):
        return round(rng.uniform(0.05, 0.5), 2)   # a retry settles fast
    return round(rng.uniform(0.5, 8.0), 2)         # a human pays after a nudge


def roll(rng: random.Random, probability: float) -> bool:
    return rng.random() < probability
