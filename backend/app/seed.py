"""Synthetic-but-realistic batch of at-risk revenue events."""
from __future__ import annotations

import random

from .models import Customer, EventType, RevenueEvent, new_id, now_ist
from datetime import timedelta

FIRST = ["Aarav", "Vivaan", "Aditya", "Diya", "Ananya", "Ishaan", "Kabir", "Zara",
         "Riya", "Arjun", "Meera", "Rohan", "Sara", "Kiara", "Dev", "Nisha",
         "Farhan", "Tara", "Yash", "Anjali", "Karthik", "Priya", "Rahul", "Sneha"]
LAST = ["Sharma", "Verma", "Iyer", "Nair", "Reddy", "Gupta", "Mehta", "Bose",
        "Khan", "Patel", "Singh", "Rao", "Das", "Kapoor", "Menon", "Joshi"]
COMPANIES = ["Zephyr Retail", "Blume Organics", "Nimbus Labs", "Kettle & Co",
             "Saffron Foods", "Peak Athleisure", "Lumen Interiors", "Verdant Agro"]
BANKS = ["HDFC", "ICICI", "SBI", "Axis", "Kotak", "IndusInd", "Yes Bank"]

# Realistic Razorpay-shaped failure envelopes: (reason, code, source, step, method)
CARD_FAILS = [
    ("insufficient_funds", "BAD_REQUEST_ERROR", "customer", "payment_authorization", "card"),
    ("card_expired", "BAD_REQUEST_ERROR", "customer", "payment_authentication", "card"),
    ("incorrect_cvv", "BAD_REQUEST_ERROR", "customer", "payment_authentication", "card"),
    ("payment_declined_by_bank", "GATEWAY_ERROR", "bank", "payment_authorization", "card"),
    ("issuer_bank_not_available", "GATEWAY_ERROR", "bank", "payment_authorization", "card"),
    ("payment_gateway_timeout", "GATEWAY_ERROR", "gateway", "payment_authorization", "card"),
    ("transaction_limit_exceeded", "BAD_REQUEST_ERROR", "bank", "payment_authorization", "card"),
]
UPI_FAILS = [
    ("insufficient_funds", "BAD_REQUEST_ERROR", "customer", "payment_authorization", "upi"),
    ("upi_collect_expired", "BAD_REQUEST_ERROR", "customer", "payment_authorization", "upi"),
    ("payment_declined_by_bank", "GATEWAY_ERROR", "bank", "payment_authorization", "upi"),
    ("npci_unavailable", "GATEWAY_ERROR", "gateway", "payment_authorization", "upi"),
]
SUB_FAILS = [
    ("mandate_insufficient_funds", "BAD_REQUEST_ERROR", "customer", "payment_authorization", "emandate"),
    ("mandate_revoked", "BAD_REQUEST_ERROR", "customer", "payment_initiation", "emandate"),
    ("issuer_bank_not_available", "GATEWAY_ERROR", "bank", "payment_authorization", "emandate"),
]


def _customer(rng: random.Random, *, company: bool = False, opted_out: bool = False,
              prior_contacts: int = 0) -> Customer:
    if company:
        name = rng.choice(COMPANIES)
        domain = name.lower().replace(" & ", "").replace(" ", "") + ".in"
        email = f"accounts@{domain}"
    else:
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        email = name.lower().replace(" ", ".") + "@example.com"
    return Customer(
        id=new_id("cust"),
        name=name,
        email=email,
        phone="+9198" + "".join(str(rng.randint(0, 9)) for _ in range(8)),
        language_pref=rng.choice(["hinglish", "hinglish", "english"]),
        ltv_paise=rng.randint(5_000, 900_000) * 100,
        opted_out=opted_out,
        prior_contacts=prior_contacts,
    )


def _event(rng: random.Random, etype: EventType, cust: Customer, **over) -> RevenueEvent:
    created = now_ist() - timedelta(hours=rng.uniform(2, 96))
    base = dict(
        id=new_id("evt"),
        type=etype,
        currency="INR",
        created_at=created,
        customer=cust,
        age_hours=round((now_ist() - created).total_seconds() / 3600, 1),
        attempt_count=rng.randint(1, 2),
    )
    base.update(over)
    return RevenueEvent(**base)


def build_batch(seed: int = 7, n: int = 52) -> list[RevenueEvent]:
    rng = random.Random(seed)
    events: list[RevenueEvent] = []

    # ---- Planted edge cases (bounded-behaviour showcase) -------------------- #
    # 1) Opted-out customer — agent must not contact at all.
    reason, code, src, step, method = rng.choice(CARD_FAILS)
    events.append(_event(
        rng, EventType.PAYMENT_FAILURE, _customer(rng, opted_out=True),
        amount_paise=rng.randint(900, 6000) * 100, method=method,
        order_id=new_id("order"), payment_id=new_id("pay"),
        error_reason=reason, error_code=code, error_source=src, error_step=step,
    ))
    # 2) Contact-cap already reached — agent must escalate, not spam.
    events.append(_event(
        rng, EventType.CHECKOUT_ABANDONMENT, _customer(rng, prior_contacts=4),
        amount_paise=rng.randint(1500, 9000) * 100, method="card",
        order_id=new_id("order"),
    ))
    # 3) Large B2B invoice above the auto threshold — human sign-off required.
    events.append(_event(
        rng, EventType.INVOICE_OVERDUE, _customer(rng, company=True),
        amount_paise=rng.randint(280_000, 500_000) * 100,
        invoice_id=new_id("inv"),
    ))
    # 4) Fraud-flagged payment — never auto-retry; escalate.
    reason, code, src, step, method = ("payment_declined_by_bank", "GATEWAY_ERROR", "bank",
                                       "payment_authorization", "card")
    events.append(_event(
        rng, EventType.PAYMENT_FAILURE, _customer(rng),
        amount_paise=rng.randint(20_000, 60_000) * 100, method=method,
        order_id=new_id("order"), payment_id=new_id("pay"),
        error_reason=reason, error_code=code, error_source=src, error_step=step,
        risk_flag=True,
    ))

    # ---- Bulk realistic distribution --------------------------------------- #
    weights = [
        (EventType.PAYMENT_FAILURE, 0.42),
        (EventType.CHECKOUT_ABANDONMENT, 0.24),
        (EventType.SUBSCRIPTION_FAILURE, 0.20),
        (EventType.INVOICE_OVERDUE, 0.14),
    ]
    types = [t for t, _ in weights]
    probs = [w for _, w in weights]

    while len(events) < n:
        etype = rng.choices(types, probs)[0]
        cust = _customer(rng, company=(etype == EventType.INVOICE_OVERDUE and rng.random() < 0.7))

        if etype == EventType.PAYMENT_FAILURE:
            reason, code, src, step, method = rng.choice(
                CARD_FAILS if rng.random() < 0.6 else UPI_FAILS)
            events.append(_event(
                rng, etype, cust,
                amount_paise=rng.randint(500, 15_000) * 100, method=method,
                order_id=new_id("order"), payment_id=new_id("pay"),
                error_reason=reason, error_code=code, error_source=src, error_step=step,
                risk_flag=rng.random() < 0.05,
            ))
        elif etype == EventType.CHECKOUT_ABANDONMENT:
            events.append(_event(
                rng, etype, cust,
                amount_paise=rng.randint(800, 25_000) * 100, method="card",
                order_id=new_id("order"),
            ))
        elif etype == EventType.SUBSCRIPTION_FAILURE:
            reason, code, src, step, method = rng.choice(SUB_FAILS)
            events.append(_event(
                rng, etype, cust,
                amount_paise=rng.choice([199, 499, 799, 999, 1499, 2999]) * 100,
                method=method, subscription_id=new_id("sub"),
                error_reason=reason, error_code=code, error_source=src, error_step=step,
                attempt_count=rng.randint(1, 3),
            ))
        else:  # INVOICE_OVERDUE
            disputed = rng.random() < 0.15
            events.append(_event(
                rng, etype, cust,
                amount_paise=rng.randint(8_000, 55_000) * 100,
                invoice_id=new_id("inv"),
                error_reason="disputed" if disputed else None,
            ))

    rng.shuffle(events)
    return events[:n]
