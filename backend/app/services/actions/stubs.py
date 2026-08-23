from __future__ import annotations

from app.models.domain import RecoveryOutcome
from app.services.actions.interfaces import (
    ActionResult,
    EscalationProvider,
    MessagingProvider,
    PaymentActionProvider,
)


class StubPaymentProvider(PaymentActionProvider):
    """No-op Razorpay stub. Replace with real implementation in Phase 2."""

    def retry_payment(self, transaction_id: str, amount: float) -> ActionResult:
        return ActionResult(
            outcome=RecoveryOutcome.FAILED,
            detail=f"[stub] retry_payment called for tx={transaction_id}",
        )

    def create_payment_link(self, transaction_id: str, amount: float, customer_email: str) -> ActionResult:
        return ActionResult(
            outcome=RecoveryOutcome.FAILED,
            detail=f"[stub] create_payment_link called for tx={transaction_id}",
            external_ref="https://rzp.io/stub/link",
        )


class StubMessagingProvider(MessagingProvider):
    """No-op messaging stub. Replace with WhatsApp/email providers in Phase 2."""

    def send_whatsapp(self, phone: str, message: str) -> ActionResult:
        return ActionResult(
            outcome=RecoveryOutcome.FAILED,
            detail=f"[stub] send_whatsapp to {phone}",
        )

    def send_email(self, email: str, subject: str, body: str) -> ActionResult:
        return ActionResult(
            outcome=RecoveryOutcome.FAILED,
            detail=f"[stub] send_email to {email}",
        )


class StubEscalationProvider(EscalationProvider):
    """No-op escalation stub."""

    def escalate(self, recovery_case_id: str, reason: str) -> ActionResult:
        return ActionResult(
            outcome=RecoveryOutcome.ESCALATED,
            detail=f"[stub] escalated case={recovery_case_id}: {reason}",
        )
