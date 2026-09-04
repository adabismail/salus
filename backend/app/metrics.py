"""Aggregate an honest scoreboard from processed event records."""
from __future__ import annotations

from datetime import datetime

from .models import EventRecord, EventStatus, GateDecision, Metrics


def compute(records: list[EventRecord], started_at: datetime) -> Metrics:
    m = Metrics()
    ttr: list[float] = []

    for rec in records:
        ev = rec.event
        m.at_risk_count += 1
        m.at_risk_paise += ev.amount_paise
        m.cost_paise += rec.total_cost_paise

        rc = rec.diagnosis.root_cause.value if rec.diagnosis else "unknown"
        bucket = m.by_root_cause.setdefault(
            rc, {"at_risk": 0, "recovered": 0, "escalated": 0, "recovered_paise": 0})
        bucket["at_risk"] += 1

        if rec.status == EventStatus.RECOVERED:
            m.recovered_count += 1
            m.recovered_paise += rec.outcome.recovered_amount_paise
            bucket["recovered"] += 1
            bucket["recovered_paise"] += rec.outcome.recovered_amount_paise
            if rec.outcome.recovered_at:
                ttr.append((rec.outcome.recovered_at - started_at).total_seconds() / 3600)
        elif rec.status == EventStatus.ESCALATED:
            m.escalated_count += 1
            m.escalated_paise += ev.amount_paise
            bucket["escalated"] += 1
        elif rec.status == EventStatus.PROMISE_TO_PAY:
            m.promise_count += 1
            m.promise_paise += rec.outcome.promise_amount_paise or ev.amount_paise
        else:  # LOST / STOPPED
            m.lost_count += 1
            m.lost_paise += ev.amount_paise

        for iv in rec.interventions:
            if iv.executed:
                m.actions_taken += 1
                ib = m.by_intervention.setdefault(iv.type.value, {"taken": 0, "succeeded": 0})
                ib["taken"] += 1
                if iv.succeeded:
                    ib["succeeded"] += 1
            if iv.gate and iv.gate.decision == GateDecision.BLOCK:
                m.actions_blocked += 1
            if iv.gate and iv.gate.decision == GateDecision.DEFER:
                m.actions_deferred += 1

    m.addressable_count = m.recovered_count + m.lost_count
    m.addressable_paise = m.recovered_paise + m.lost_paise
    m.recovery_rate = round(m.recovered_paise / m.addressable_paise, 4) if m.addressable_paise else 0.0
    m.gross_recovery_rate = round(m.recovered_paise / m.at_risk_paise, 4) if m.at_risk_paise else 0.0
    m.net_recovered_paise = m.recovered_paise - m.cost_paise
    m.roi = round(m.recovered_paise / m.cost_paise, 1) if m.cost_paise else 0.0
    m.avg_time_to_recover_hours = round(sum(ttr) / len(ttr), 1) if ttr else 0.0
    return m
