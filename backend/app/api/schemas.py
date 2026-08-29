from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.domain import (
    AuditEventType,
    Currency,
    EscalateReason,
    MessageChannel,
    MessageStatus,
    NotificationType,
    PaymentMethod,
    RecoveryAction,
    RecoveryDecision,
    RecoveryOutcome,
    RecoveryStatus,
    StopReason,
    TransactionStatus,
)


# ---------------------------------------------------------------------------
# Health & Status
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    app_env: str
    razorpay_mode: str


class ReadinessResponse(BaseModel):
    status: str
    app_env: str
    database: str
    razorpay: str
    llm: str
    messaging: str
    dependencies: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Auth & Merchant Profiles
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    password: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    merchant_id: str
    name: str
    email: str


class MerchantProfileResponse(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    timezone: str
    created_at: datetime


class UpdateMerchantProfileRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    timezone: Optional[str] = None


class NotificationSettingsResponse(BaseModel):
    merchant_id: str
    notify_recovery_completed: bool
    notify_recovery_escalated: bool
    notify_action_failed: bool
    notify_payment_recovered: bool


class UpdateNotificationSettingsRequest(BaseModel):
    notify_recovery_completed: Optional[bool] = None
    notify_recovery_escalated: Optional[bool] = None
    notify_action_failed: Optional[bool] = None
    notify_payment_recovered: Optional[bool] = None


# ---------------------------------------------------------------------------
# Events & Webhook
# ---------------------------------------------------------------------------

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


class CreatePaymentRequest(BaseModel):
    """Payload for POST /api/v1/payments - Create Razorpay payment link"""
    customer_id: str
    amount: float
    currency: Currency = Currency.INR
    description: Optional[str] = "Payment"


class CreatePaymentWithCustomerRequest(BaseModel):
    """Payload for POST /api/v1/payments/create-with-customer - Create customer and payment link"""
    customer_name: str
    customer_email: str
    customer_phone: str
    amount: float
    currency: Currency = Currency.INR
    payment_method: PaymentMethod = PaymentMethod.CARD


class CreatePaymentResponse(BaseModel):
    """Response for payment creation"""
    transaction_id: str
    razorpay_order_id: Optional[str] = None
    payment_link_url: Optional[str] = None
    amount: float
    currency: str
    status: str
    customer_name: str
    created_at: datetime


class StartRecoveryRequest(BaseModel):
    """Payload for POST /api/v1/recovery"""
    case_id: str
    maximum_retries: int = 3
    maximum_messages: int = 3
    recovery_window_hours: int = 72
    high_value_threshold: float = 10_000.0
    human_approval_required: bool = False


class WebhookResponse(BaseModel):
    status: str
    message: str
    event: Optional[str] = None
    case_id: Optional[str] = None
    is_duplicate: bool = False


# ---------------------------------------------------------------------------
# Recovery Cases & Actions
# ---------------------------------------------------------------------------

class RecoveryCaseResponse(BaseModel):
    id: str
    merchant_id: Optional[str] = None
    transaction_id: str
    customer_id: str
    amount_at_risk: float
    reason: str
    status: RecoveryStatus
    recoverability: Optional[str] = None
    recovery_probability: float
    expected_value: float = 0.0
    decision_reason: Optional[str] = None
    decision: Optional[RecoveryDecision] = None
    selected_action: Optional[RecoveryAction] = None
    stop_reason: Optional[StopReason] = None
    escalate_reason: Optional[EscalateReason] = None
    outcome: Optional[RecoveryOutcome] = None
    amount_recovered: float = 0.0
    retry_count: int
    message_count: int
    created_at: datetime
    updated_at: datetime


class ActionRecordResponse(BaseModel):
    id: str
    merchant_id: Optional[str] = None
    recovery_case_id: str
    action: RecoveryAction
    outcome: Optional[RecoveryOutcome] = None
    detail: Optional[str] = None
    external_ref: Optional[str] = None
    executed_at: datetime


class AuditRecordResponse(BaseModel):
    id: str
    merchant_id: Optional[str] = None
    recovery_case_id: str
    event_type: AuditEventType
    detail: str
    created_at: datetime


class MessageDeliveryResponse(BaseModel):
    id: str
    merchant_id: Optional[str] = None
    recovery_case_id: str
    customer_id: str
    channel: MessageChannel
    provider: str
    provider_message_id: Optional[str] = None
    status: MessageStatus
    content_preview: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

class CustomerResponse(BaseModel):
    id: str
    merchant_id: Optional[str] = None
    external_id: Optional[str] = None
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    opted_out: bool
    created_at: datetime


class CustomerMetrics(BaseModel):
    total_payments: int = 0
    successful_payments: int = 0
    failed_payments: int = 0
    total_paid_amount: float = 0.0
    failed_amount: float = 0.0
    recovery_cases_count: int = 0
    successful_recoveries_count: int = 0
    recovered_revenue: float = 0.0
    recovery_rate: float = 0.0
    historical_success_rate: float = 0.0
    customer_tenure_days: int = 0


class CustomerDetailResponse(BaseModel):
    customer: CustomerResponse
    metrics: CustomerMetrics
    recent_transactions: list[TransactionResponse] = Field(default_factory=list)
    recent_recoveries: list[RecoveryCaseResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

class TransactionResponse(BaseModel):
    id: str
    merchant_id: Optional[str] = None
    customer_id: str
    amount: float
    currency: Currency
    payment_method: PaymentMethod
    status: TransactionStatus
    failure_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Dashboard & Analytics
# ---------------------------------------------------------------------------

class DashboardSummaryResponse(BaseModel):
    total_revenue_at_risk: float
    total_recovered_revenue: float
    overall_recovery_rate: float
    active_recovery_cases: int
    total_recovery_cases: int
    successful_recoveries: int
    escalated_cases: int
    stopped_cases: int
    average_recovery_time_hours: float


class TrendDataPoint(BaseModel):
    date: str
    at_risk_amount: float
    recovered_amount: float
    recovered_count: int
    failed_count: int


class DashboardTrendsResponse(BaseModel):
    period: str
    trends: list[TrendDataPoint] = Field(default_factory=list)


class ActionBreakdownItem(BaseModel):
    action: str
    count: int
    recovered_amount: float
    success_rate: float


class DashboardBreakdownResponse(BaseModel):
    by_action: list[ActionBreakdownItem] = Field(default_factory=list)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_payment_method: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

class PolicyResponse(BaseModel):
    id: str
    merchant_id: Optional[str] = None
    name: str
    is_active: bool
    maximum_retries: int
    maximum_messages: int
    recovery_window_hours: int
    high_value_threshold: float
    human_approval_required: bool
    action_costs: dict[str, float]
    created_at: datetime
    updated_at: datetime


class CreatePolicyRequest(BaseModel):
    name: str = "New Policy"
    is_active: bool = True
    maximum_retries: int = 3
    maximum_messages: int = 3
    recovery_window_hours: int = 72
    high_value_threshold: float = 10_000.0
    human_approval_required: bool = False
    action_costs: Optional[dict[str, float]] = None


class UpdatePolicyRequest(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    maximum_retries: Optional[int] = None
    maximum_messages: Optional[int] = None
    recovery_window_hours: Optional[int] = None
    high_value_threshold: Optional[float] = None
    human_approval_required: Optional[bool] = None
    action_costs: Optional[dict[str, float]] = None


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class NotificationResponse(BaseModel):
    id: str
    merchant_id: str
    notification_type: NotificationType
    title: str
    message: str
    recovery_case_id: Optional[str] = None
    read: bool
    created_at: datetime


class UnreadCountResponse(BaseModel):
    unread_count: int


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class APIErrorResponse(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None
    details: Optional[Any] = None

