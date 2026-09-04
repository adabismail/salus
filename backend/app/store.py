from __future__ import annotations

from typing import Any, Iterator, Optional

from . import metrics as metrics_mod
from .config import settings
from .models import (EventRecord, Guardrails, RevenueEvent, RunSummary,
                     default_guardrails, new_id, now_ist)
from .orchestrator import Orchestrator
from .seed import build_batch


class Store:
    def __init__(self) -> None:
        self.guardrails: Guardrails = default_guardrails()
        self.seed: int = settings.SEED
        self.events: list[RevenueEvent] = []
        self.records: list[EventRecord] = []
        self.summary: Optional[RunSummary] = None
        # event_id -> real Razorpay link info (live mode)
        self.live_links: dict[str, dict] = {}
        self.reset()

    def reset(self, seed: Optional[int] = None) -> None:
        if seed is not None:
            self.seed = seed
        self.events = build_batch(self.seed, settings.BATCH_SIZE)
        self.records = [EventRecord(event=e) for e in self.events]
        self.summary = None

    def record_by_id(self, event_id: str) -> Optional[EventRecord]:
        return next((r for r in self.records if r.event.id == event_id), None)

    def set_guardrails(self, g: Guardrails) -> None:
        self.guardrails = g

    def run_stream(self) -> Iterator[dict[str, Any]]:
        """Run the agent over a fresh copy of the batch, yielding live progress."""
        self.records = [EventRecord(event=e) for e in self.events]
        orch = Orchestrator(self.records, self.guardrails, self.seed)
        summary = RunSummary(run_id=new_id("run"), seed=self.seed,
                             started_at=orch.started_at, guardrails=self.guardrails,
                             mode=settings.MODE)
        self.summary = summary
        for progress in orch.run():
            yield progress
        summary.finished_at = now_ist()
        summary.metrics = metrics_mod.compute(self.records, orch.started_at)

    def current_metrics(self):
        started = self.summary.started_at if self.summary else now_ist()
        return metrics_mod.compute(self.records, started)


store = Store()
