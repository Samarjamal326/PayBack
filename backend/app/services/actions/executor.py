from __future__ import annotations

from app.models.domain import (
    ActionRecord,
    RecoveryAction,
    RecoveryCase,
    RecoveryOutcome,
    Transaction,
    Customer,
)
from app.services.actions.interfaces import (
    ActionResult,
    EscalationProvider,
    MessagingProvider,
    PaymentActionProvider,
)
from app.services.llm.interface import MessageContext, MessageGenerator


class ActionExecutor:
    """
    Orchestrates execution of a selected RecoveryAction.

    Keeps LangGraph nodes thin — nodes call this; this calls providers.
    """

    def __init__(
        self,
        payment: PaymentActionProvider,
        messaging: MessagingProvider,
        escalation: EscalationProvider,
        message_generator: MessageGenerator,
    ) -> None:
        self._payment = payment
        self._messaging = messaging
        self._escalation = escalation
        self._generator = message_generator

    def execute(
        self,
        action: RecoveryAction,
        case: RecoveryCase,
        transaction: Transaction,
        customer: Customer,
    ) -> ActionRecord:
        result = self._dispatch(action, case, transaction, customer)
        return ActionRecord(
            recovery_case_id=case.id,
            action=action,
            outcome=result.outcome,
            detail=result.detail,
            external_ref=result.external_ref,
        )

    def _dispatch(
        self,
        action: RecoveryAction,
        case: RecoveryCase,
        transaction: Transaction,
        customer: Customer,
    ) -> ActionResult:
        ctx = MessageContext(
            customer_name=customer.name,
            amount=transaction.amount,
            currency=transaction.currency.value,
            failure_reason=transaction.failure_reason,
            payment_link=None,
        )

        if action == RecoveryAction.RETRY_PAYMENT:
            return self._payment.retry_payment(transaction.id, transaction.amount)

        if action == RecoveryAction.CREATE_PAYMENT_LINK:
            result = self._payment.create_payment_link(
                transaction_id=transaction.id,
                amount=transaction.amount,
                customer_email=customer.email or "",
                customer_phone=customer.phone,
                customer_name=customer.name,
            )
            ctx = MessageContext(
                customer_name=customer.name,
                amount=transaction.amount,
                currency=transaction.currency.value,
                failure_reason=transaction.failure_reason,
                payment_link=result.external_ref,
            )
            return result

        if action == RecoveryAction.SEND_WHATSAPP:
            msg = self._generator.whatsapp_message(ctx)
            return self._messaging.send_whatsapp(customer.phone or "", msg)

        if action == RecoveryAction.SEND_EMAIL:
            body = self._generator.email_body(ctx)
            return self._messaging.send_email(customer.email or "", "Action required — complete your payment", body)

        if action == RecoveryAction.ESCALATE:
            return self._escalation.escalate(case.id, case.escalate_reason.value if case.escalate_reason else "unknown")

        # STOP
        return ActionResult(outcome=RecoveryOutcome.STOPPED, detail="Recovery stopped by decision engine.")
