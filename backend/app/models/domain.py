from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Currency(str, Enum):
    INR = "INR"
    USD = "USD"
    EUR = "EUR"


class PaymentMethod(str, Enum):
    UPI = "upi"
    CARD = "card"
    NET_BANKING = "net_banking"
    WALLET = "wallet"
    EMI = "emi"
    UNKNOWN = "unknown"


class TransactionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    ABANDONED = "abandoned"
    REFUNDED = "refunded"


class RecoveryStatus(str, Enum):
    DETECTED = "detected"
    ANALYZING = "analyzing"
    ELIGIBILITY_CHECK = "eligibility_check"
    DECISION = "decision"
    ACTION_PENDING = "action_pending"
    ACTION_EXECUTED = "action_executed"
    MONITORING = "monitoring"
    RECOVERED = "recovered"
    ESCALATED = "escalated"
    STOPPED = "stopped"


class RecoveryDecision(str, Enum):
    RECOVER = "recover"
    ESCALATE = "escalate"
    STOP = "stop"


class RecoveryAction(str, Enum):
    RETRY_PAYMENT = "retry_payment"
    CREATE_PAYMENT_LINK = "create_payment_link"
    SEND_WHATSAPP = "send_whatsapp"
    SEND_EMAIL = "send_email"
    ESCALATE = "escalate"
    STOP = "stop"


class RecoveryOutcome(str, Enum):
    RECOVERED = "recovered"
    FAILED = "failed"
    EXPIRED = "expired"
    ESCALATED = "escalated"
    STOPPED = "stopped"


class RecoverabilityCategory(str, Enum):
    HIGHLY_RECOVERABLE = "highly_recoverable"
    LIKELY_RECOVERABLE = "likely_recoverable"
    UNCERTAIN = "uncertain"
    LOW_RECOVERY_PROBABILITY = "low_recovery_probability"
    NON_RECOVERABLE = "non_recoverable"


class StopReason(str, Enum):
    OPT_OUT = "customer_opted_out"
    WINDOW_EXPIRED = "recovery_window_expired"
    MAX_RETRIES = "maximum_retries_reached"
    MAX_MESSAGES = "maximum_messages_reached"
    NOT_RECOVERABLE = "determined_not_recoverable"
    NO_INTENT = "no_purchase_intent"


class EscalateReason(str, Enum):
    HIGH_VALUE = "high_value_transaction"
    POLICY_REQUIRES_APPROVAL = "policy_requires_human_approval"
    REPEATED_FAILURES = "repeated_recovery_failures"
    AMBIGUOUS = "ambiguous_situation"


class AuditEventType(str, Enum):
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_ABANDONED = "PAYMENT_ABANDONED"
    RECOVERY_CASE_CREATED = "RECOVERY_CASE_CREATED"
    ELIGIBILITY_CHECKED = "ELIGIBILITY_CHECKED"
    RECOVERABILITY_CLASSIFIED = "RECOVERABILITY_CLASSIFIED"
    RECOVERY_SCORED = "RECOVERY_SCORED"
    DECISION_MADE = "DECISION_MADE"
    ACTION_SELECTED = "ACTION_SELECTED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    PAYMENT_LINK_CREATED = "PAYMENT_LINK_CREATED"
    PAYMENT_SUCCEEDED = "PAYMENT_SUCCEEDED"
    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"
    RECOVERY_STOPPED = "RECOVERY_STOPPED"
    RECOVERY_ESCALATED = "RECOVERY_ESCALATED"


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class Customer(BaseModel):
    id: str = Field(default_factory=_uuid)
    external_id: Optional[str] = None
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    opted_out: bool = False
    created_at: datetime = Field(default_factory=_now)


class Transaction(BaseModel):
    id: str = Field(default_factory=_uuid)
    customer_id: str
    amount: float
    currency: Currency = Currency.INR
    payment_method: PaymentMethod = PaymentMethod.UNKNOWN
    status: TransactionStatus
    failure_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Policy(BaseModel):
    maximum_retries: int = 3
    maximum_messages: int = 3
    recovery_window_hours: int = 72
    high_value_threshold: float = 10_000.0
    human_approval_required: bool = False
    action_costs: dict[str, float] = Field(default_factory=lambda: {
        RecoveryAction.RETRY_PAYMENT.value: 2.0,
        RecoveryAction.CREATE_PAYMENT_LINK.value: 5.0,
        RecoveryAction.SEND_WHATSAPP.value: 1.0,
        RecoveryAction.SEND_EMAIL.value: 0.2,
        RecoveryAction.ESCALATE.value: 15.0,
        RecoveryAction.STOP.value: 0.0,
    })


class ActionCandidate(BaseModel):
    action: RecoveryAction
    probability: float
    expected_value: float
    cost: float
    eligible: bool = True
    ineligible_reason: Optional[str] = None


class DecisionRecord(BaseModel):
    recoverability: RecoverabilityCategory
    recovery_probability: float
    selected_action: RecoveryAction
    expected_value: float
    reason: str
    decision: RecoveryDecision = RecoveryDecision.RECOVER
    stop_reason: Optional[StopReason] = None
    escalate_reason: Optional[EscalateReason] = None
    candidates: list[ActionCandidate] = Field(default_factory=list)
    explanation_details: list[str] = Field(default_factory=list)
    signals: dict[str, Any] = Field(default_factory=dict)


class RecoveryCase(BaseModel):
    id: str = Field(default_factory=_uuid)
    transaction_id: str
    customer_id: str
    amount_at_risk: float
    reason: str
    status: RecoveryStatus = RecoveryStatus.DETECTED
    recoverability: Optional[RecoverabilityCategory] = None
    recovery_probability: float = 0.0  # 0.0–1.0 estimate; NOT a monetary amount
    expected_value: float = 0.0
    decision_reason: Optional[str] = None
    selected_action: Optional[RecoveryAction] = None
    decision: Optional[RecoveryDecision] = None
    stop_reason: Optional[StopReason] = None
    escalate_reason: Optional[EscalateReason] = None
    outcome: Optional[RecoveryOutcome] = None
    amount_recovered: float = 0.0
    retry_count: int = 0
    message_count: int = 0
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)



class ActionRecord(BaseModel):
    id: str = Field(default_factory=_uuid)
    recovery_case_id: str
    action: RecoveryAction
    outcome: Optional[RecoveryOutcome] = None
    detail: Optional[str] = None
    external_ref: Optional[str] = None
    executed_at: datetime = Field(default_factory=_now)


class AuditRecord(BaseModel):
    id: str = Field(default_factory=_uuid)
    recovery_case_id: str
    event_type: AuditEventType
    detail: str
    created_at: datetime = Field(default_factory=_now)
