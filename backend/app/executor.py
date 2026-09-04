from __future__ import annotations

import base64
import uuid

import httpx

from .config import settings
from .models import Intervention, InterventionType as IT, RevenueEvent

_LINK_TYPES = {IT.NEW_PAYMENT_LINK, IT.RETRY_ALT_METHOD, IT.EMI_OFFER, IT.REMINDER_MESSAGE, IT.MANDATE_RETRY}


def _sim_link() -> tuple[str, str]:
    token = uuid.uuid4().hex[:10]
    return f"plink_{token}", f"https://rzp.io/i/{token}"


def _live_link(ev: RevenueEvent) -> tuple[str, str]:
    auth = base64.b64encode(
        f"{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}".encode()).decode()
    payload = {
        "amount": ev.amount_paise,
        "currency": ev.currency,
        "accept_partial": False,
        "description": f"Salus recovery for {ev.type.value}",
        "customer": {"name": ev.customer.name, "email": ev.customer.email, "contact": ev.customer.phone},
        "notify": {"sms": False, "email": False},  # Salus owns the messaging
        "reminder_enable": False,
        "notes": {"salus_event_id": ev.id},
    }
    with httpx.Client(timeout=15) as client:
        r = client.post("https://api.razorpay.com/v1/payment_links",
                        headers={"Authorization": f"Basic {auth}"}, json=payload)
        r.raise_for_status()
        data = r.json()
    return data["id"], data["short_url"]


def execute(ev: RevenueEvent, iv: Intervention) -> None:
    """Perform the side-effect and stamp the intervention with its Razorpay ref."""
    if iv.type in _LINK_TYPES and iv.message and "{link}" in iv.message:
        if settings.razorpay_live:
            ref, url = _live_link(ev)
        else:
            ref, url = _sim_link()
        iv.razorpay_ref = ref
        iv.message = iv.message.replace("{link}", url)
    elif iv.type in (IT.SMART_RETRY, IT.MANDATE_RETRY):
        iv.razorpay_ref = f"retry_{uuid.uuid4().hex[:10]}"
    iv.executed = True
