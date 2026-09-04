from __future__ import annotations

import hashlib
import hmac
import time

import httpx

from .config import settings
from .models import RevenueEvent

_BASE = "https://api.razorpay.com/v1"


def _auth() -> tuple[str, str]:
    return (settings.RAZORPAY_KEY_ID or "", settings.RAZORPAY_KEY_SECRET or "")


def verify() -> dict:
    """Confirm the keys work by making a real (read-only) API call."""
    with httpx.Client(timeout=20) as c:
        r = c.get(f"{_BASE}/payment_links", params={"count": 1}, auth=_auth())
    ok = r.status_code == 200
    return {
        "ok": ok,
        "status_code": r.status_code,
        "key_id": settings.masked_key_id,
        "test_mode": (settings.RAZORPAY_KEY_ID or "").startswith("rzp_test_"),
        "detail": None if ok else r.text[:300],
    }


def create_payment_link(ev: RevenueEvent) -> dict:
    """Create a REAL test-mode payment link for one at-risk event."""
    payload = {
        "amount": ev.amount_paise,
        "currency": ev.currency,
        "accept_partial": False,
        "description": f"Salus recovery · {ev.type.value}",
        "customer": {
            "name": ev.customer.name,
            "email": ev.customer.email,
            "contact": ev.customer.phone,
        },
        "notify": {"sms": False, "email": False},  # Salus never sends via Razorpay
        "reminder_enable": False,
        "notes": {"salus_event_id": ev.id, "root": (ev.error_reason or ev.type.value)},
    }
    # Razorpay rate-limits bursts (429). Back off and retry rather than failing
    # the whole batch on the first throttled call.
    delays = (1.2, 2.5, 4.0)
    last_error = "unknown error"
    for attempt in range(len(delays) + 1):
        with httpx.Client(timeout=20) as c:
            r = c.post(f"{_BASE}/payment_links", json=payload, auth=_auth())
        if r.status_code == 429:
            last_error = "Razorpay rate limit (429)"
            if attempt < len(delays):
                time.sleep(delays[attempt])
                continue
            break
        if r.status_code >= 400:
            raise RuntimeError(f"Razorpay {r.status_code}: {r.text[:200]}")
        return r.json()
    raise RuntimeError(f"{last_error} — too many links created too quickly; wait a few seconds and retry.")


def fetch_payment_link(link_id: str) -> dict:
    with httpx.Client(timeout=20) as c:
        r = c.get(f"{_BASE}/payment_links/{link_id}", auth=_auth())
        r.raise_for_status()
        return r.json()


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """Verify a Razorpay webhook's HMAC-SHA256 signature."""
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def list_payment_links(count: int = 100) -> list[dict]:
    """Every payment link on the account. Read-only, so it isn't throttled the
    way link creation is — this is how we recover state after a restart."""
    with httpx.Client(timeout=25) as c:
        r = c.get(f"{_BASE}/payment_links", params={"count": count}, auth=_auth())
        r.raise_for_status()
        data = r.json()
    return data.get("payment_links") or data.get("items") or []
