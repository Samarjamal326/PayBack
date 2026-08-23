from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.domain import RecoveryOutcome


@dataclass(frozen=True)
class ActionResult:
    outcome: RecoveryOutcome
    detail: str
    external_ref: str | None = None  # e.g., Razorpay payment link ID


class PaymentActionProvider(ABC):
    """Razorpay integration slot. Stub in Phase 1."""

    @abstractmethod
    def retry_payment(self, transaction_id: str, amount: float) -> ActionResult:
        ...

    @abstractmethod
    def create_payment_link(self, transaction_id: str, amount: float, customer_email: str) -> ActionResult:
        ...


class MessagingProvider(ABC):
    """WhatsApp / email integration slot. Stub in Phase 1."""

    @abstractmethod
    def send_whatsapp(self, phone: str, message: str) -> ActionResult:
        ...

    @abstractmethod
    def send_email(self, email: str, subject: str, body: str) -> ActionResult:
        ...


class EscalationProvider(ABC):
    """Human-in-the-loop escalation slot."""

    @abstractmethod
    def escalate(self, recovery_case_id: str, reason: str) -> ActionResult:
        ...
