"""Domain models for Salus. Money is stored in paise (Razorpay convention)."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .config import IST


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now_ist() -> datetime:
    return datetime.now(IST)


class EventType(str, Enum):
    PAYMENT_FAILURE = "payment_failure"
    CHECKOUT_ABANDONMENT = "checkout_abandonment"
    SUBSCRIPTION_FAILURE = "subscription_failure"
    INVOICE_OVERDUE = "invoice_overdue"


class EventStatus(str, Enum):
    AT_RISK = "at_risk"
    IN_RECOVERY = "in_recovery"
    RECOVERED = "recovered"
    LOST = "lost"
    ESCALATED = "escalated"          # handed to a human, on purpose
    PROMISE_TO_PAY = "promise_to_pay"  # customer committed to pay by a date
    STOPPED = "stopped"              # a stopping rule halted further action


class RootCause(str, Enum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    CARD_EXPIRED = "card_expired"
    AUTHENTICATION_FAILED = "authentication_failed"
    DO_NOT_HONOR = "do_not_honor"
    ISSUER_DOWN = "issuer_down"
    NETWORK_TIMEOUT = "network_timeout"
    LIMIT_EXCEEDED = "limit_exceeded"
    RISK_BLOCKED = "risk_blocked"
    MANDATE_REVOKED = "mandate_revoked"
    ABANDONED_HESITATION = "abandoned_hesitation"
    ABANDONED_PRICE = "abandoned_price"
    INVOICE_FORGOTTEN = "invoice_forgotten"
    INVOICE_DISPUTE = "invoice_dispute"
    UNKNOWN = "unknown"


class InterventionType(str, Enum):
    SMART_RETRY = "smart_retry"
    NEW_PAYMENT_LINK = "new_payment_link"
    REMINDER_MESSAGE = "reminder_message"
    RETRY_ALT_METHOD = "retry_alt_method"
    EMI_OFFER = "emi_offer"
    MANDATE_RETRY = "mandate_retry"
    FINAL_NOTICE = "final_notice"          # last, firm dunning step before escalation
    PROMISE_TO_PAY = "promise_to_pay"      # capture a commitment-to-pay from the customer
    ESCALATE_HUMAN = "escalate_human"
    STOP = "stop"


class Channel(str, Enum):
    WHATSAPP = "whatsapp"
    SMS = "sms"
    EMAIL = "email"
    NONE = "none"


class GateDecision(str, Enum):
    ALLOW = "allow"
    DEFER = "defer"      # allowed, but rescheduled
    BLOCK = "block"      # not allowed 
    ESCALATE = "escalate"  # must go to a human


class Customer(BaseModel):
    id: str
    name: str
    email: str
    phone: str
    language_pref: str = "hinglish"    # hinglish | english
    ltv_paise: int = 0                 # lifetime value, feeds prioritisation
    opted_out: bool = False            # respected absolutely
    prior_contacts: int = 0            # contacts already made before this run


class RevenueEvent(BaseModel):
    id: str
    type: EventType
    amount_paise: int
    currency: str = "INR"
    created_at: datetime
    customer: Customer

    # Razorpay references (test-mode-shaped)
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    subscription_id: Optional[str] = None
    invoice_id: Optional[str] = None

    # Failure envelope, mirroring Razorpay's payment error object
    method: Optional[str] = None       
    error_code: Optional[str] = None   
    error_source: Optional[str] = None  
    error_step: Optional[str] = None 
    error_reason: Optional[str] = None  

    attempt_count: int = 1
    age_hours: float = 0.0            
    risk_flag: bool = False           


class Diagnosis(BaseModel):
    root_cause: RootCause
    confidence: float                  
    recoverable: bool
    rationale: str                    
    signals: list[str] = Field(default_factory=list)
    suggested: list[InterventionType] = Field(default_factory=list)
    source: str = "rules"              


class PolicyResult(BaseModel):
    decision: GateDecision
    reasons: list[str] = Field(default_factory=list)
    fired_rules: list[str] = Field(default_factory=list)
    reschedule_to: Optional[datetime] = None


class Intervention(BaseModel):
    id: str
    event_id: str
    type: InterventionType
    channel: Channel = Channel.NONE
    scheduled_for: Optional[datetime] = None
    cost_paise: int = 0                
    message: Optional[str] = None      
    razorpay_ref: Optional[str] = None  
    gate: Optional[PolicyResult] = None
    executed: bool = False
    succeeded: Optional[bool] = None    
    step: int = 0                       
    firmness: str = "gentle"            


class AuditEntry(BaseModel):
    id: str = Field(default_factory=lambda: new_id("aud"))
    ts: datetime = Field(default_factory=now_ist)
    event_id: str
    phase: str                         
    actor: str                        
    summary: str
    detail: dict[str, Any] = Field(default_factory=dict)
    cost_paise: int = 0


class Outcome(BaseModel):
    recovered: bool = False
    recovered_amount_paise: int = 0
    recovered_at: Optional[datetime] = None
    winning_intervention: Optional[InterventionType] = None
    attempts: int = 0
    note: str = ""
    # Promise-to-pay branch (B2B receivables)
    promised: bool = False
    promise_amount_paise: int = 0
    promise_due: Optional[datetime] = None


class EventRecord(BaseModel):
    """Everything Salus knows and did about one at-risk event."""
    event: RevenueEvent
    status: EventStatus = EventStatus.AT_RISK
    diagnosis: Optional[Diagnosis] = None
    interventions: list[Intervention] = Field(default_factory=list)
    outcome: Outcome = Field(default_factory=Outcome)
    audit: list[AuditEntry] = Field(default_factory=list)
    total_cost_paise: int = 0


class Guardrails(BaseModel):
    max_retries: int = 3
    max_contacts_per_customer: int = 4
    min_gap_hours: int = 20
    quiet_start_hour: int = 21         
    quiet_end_hour: int = 8         
    max_auto_amount_paise: int = 50_00_000       # ₹50,000 auto-charge ceiling
    human_review_amount_paise: int = 2_00_00_000  # ₹2,00,000 — any action above goes to a human       
    max_discount_pct: int = 10          
    respect_opt_out: bool = True
    escalate_risk_blocked: bool = True  


def default_guardrails() -> Guardrails:
    return Guardrails()



class Metrics(BaseModel):
    at_risk_count: int = 0
    at_risk_paise: int = 0
    recovered_count: int = 0
    recovered_paise: int = 0
    lost_count: int = 0
    lost_paise: int = 0
    escalated_count: int = 0
    escalated_paise: int = 0
    promise_count: int = 0              
    promise_paise: int = 0
    addressable_count: int = 0
    addressable_paise: int = 0
    cost_paise: int = 0
    recovery_rate: float = 0.0          # recovered_paise / addressable_paise (headline)
    gross_recovery_rate: float = 0.0    # recovered_paise / at_risk_paise (includes escalated)
    net_recovered_paise: int = 0        # recovered - cost
    roi: float = 0.0                    # recovered / cost
    avg_time_to_recover_hours: float = 0.0
    actions_taken: int = 0
    actions_blocked: int = 0
    actions_deferred: int = 0
    by_root_cause: dict[str, dict[str, int]] = Field(default_factory=dict)
    by_intervention: dict[str, dict[str, int]] = Field(default_factory=dict)


class RunSummary(BaseModel):
    run_id: str
    seed: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    guardrails: Guardrails
    metrics: Metrics = Field(default_factory=Metrics)
    mode: str = "simulate"
