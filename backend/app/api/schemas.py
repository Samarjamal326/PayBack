from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.domain import (
    ActionRecord,
    Currency,
    EscalateReason,
    PaymentMethod,
    RecoveryAction,
    RecoveryDecision,
    RecoveryOutcome,
    RecoveryStatus,
    StopReason,
    TransactionStatus,
)


class PaymentEventRequest(BaseModel):
    """Payload for POST /api/v1/events/payment"""
    customer_external_id: str
    customer_name: str
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    transaction_amount: float
    transaction_currency: Currency = Currency.INR
    payment_method: PaymentMethod = PaymentMethod.UNKNOWN
    transaction_status: TransactionStatus
    failure_reason: Optional[str] = None


class StartRecoveryRequest(BaseModel):
    """Payload for POST /api/v1/recovery"""
    case_id: str
    maximum_retries: int = 3
    maximum_messages: int = 3
    recovery_window_hours: int = 72
    high_value_threshold: float = 10_000.0
    human_approval_required: bool = False


class RecoveryCaseResponse(BaseModel):
    id: str
    transaction_id: str
    customer_id: str
    amount_at_risk: float
    reason: str
    status: RecoveryStatus
    recovery_probability: float
    decision: Optional[RecoveryDecision]
    selected_action: Optional[RecoveryAction]
    stop_reason: Optional[StopReason]
    escalate_reason: Optional[EscalateReason]
    retry_count: int
    message_count: int
    created_at: datetime
    updated_at: datetime


class ActionRecordResponse(BaseModel):
    id: str
    recovery_case_id: str
    action: RecoveryAction
    outcome: Optional[RecoveryOutcome]
    detail: Optional[str]
    executed_at: datetime
