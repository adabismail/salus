"""Runtime settings, loaded from environment (with safe defaults for demo mode)."""
from __future__ import annotations

import os
from datetime import timezone, timedelta

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass

IST = timezone(timedelta(hours=5, minutes=30))


class Settings:
    MODE: str = os.getenv("SALUS_MODE", "simulate").lower()

    SEED: int = int(os.getenv("SALUS_SEED", "7"))
    BATCH_SIZE: int = int(os.getenv("SALUS_BATCH_SIZE", "52"))

    RAZORPAY_KEY_ID: str | None = os.getenv("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET: str | None = os.getenv("RAZORPAY_KEY_SECRET")
    RAZORPAY_WEBHOOK_SECRET: str | None = os.getenv("SALUS_WEBHOOK_SECRET")

    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    LLM_MODEL: str = os.getenv("SALUS_LLM_MODEL", "claude-sonnet-5")

    @property
    def razorpay_configured(self) -> bool:
        """Keys present — live endpoints work regardless of MODE."""
        return bool(self.RAZORPAY_KEY_ID and self.RAZORPAY_KEY_SECRET)

    @property
    def razorpay_live(self) -> bool:
        return self.MODE == "live" and self.razorpay_configured

    @property
    def llm_enabled(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY)

    @property
    def masked_key_id(self) -> str | None:
        """A safe-to-display form of the Key ID — never expose the full value."""
        k = self.RAZORPAY_KEY_ID
        if not k:
            return None
        return f"{k[:9]}••••{k[-2:]}" if len(k) > 12 else "••••"


settings = Settings()
