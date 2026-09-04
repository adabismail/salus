"""Optional LLM assist"""
from __future__ import annotations

from .config import settings
from .models import Diagnosis, RevenueEvent

_SYSTEM = (
    "You write short, warm, trustworthy payment-recovery messages for Indian customers. "
    "Match the requested language (Hinglish = Roman-script Hindi+English, or English). "
    "One or two sentences. Never pushy, never threatening. Keep the {link} placeholder "
    "exactly as given. No emojis unless the original had them."
)


def available() -> bool:
    if not settings.llm_enabled:
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:
        return False


def refine_message(ev: RevenueEvent, dg: Diagnosis, base_message: str) -> str:
    """Return an improved message, or the original on any problem."""
    if not available():
        return base_message
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        prompt = (
            f"Language: {ev.customer.language_pref}\n"
            f"Customer first name: {ev.customer.name.split()[0]}\n"
            f"Amount: ₹{ev.amount_paise // 100:,}\n"
            f"Root cause: {dg.root_cause.value}\n"
            f"Draft to improve (keep {{link}} placeholder):\n{base_message}"
        )
        resp = client.messages.create(
            model=settings.LLM_MODEL, max_tokens=200, system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        return text if "{link}" in text else base_message
    except Exception:
        return base_message
