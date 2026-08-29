from __future__ import annotations

from typing import Optional

from app.models.domain import (
    ActionRecord,
    DeliveryProvider,
    MessageChannel,
    MessageDeliveryRecord,
    MessageStatus,
    RecoveryAction,
    RecoveryCase,
    RecoveryOutcome,
    Transaction,
    Customer,
)
from app.repositories.interfaces import MessageDeliveryRepository
from app.services.actions.interfaces import (
    ActionResult,
    EscalationProvider,
    MessagingProvider,
    PaymentActionProvider,
)
from app.services.llm.interface import MessageContext, MessageGenerator
from app.services.messaging.interfaces import DeliveryProviderAdapter


class ActionExecutor:
    """
    Orchestrates execution of a selected RecoveryAction.

    Keeps LangGraph nodes thin — nodes call this; this calls providers.
    Phase 4 addition: optionally records persistent MessageDeliveryRecord on message dispatch.
    """

    def __init__(
        self,
        payment: PaymentActionProvider,
        messaging: MessagingProvider,
        escalation: EscalationProvider,
        message_generator: MessageGenerator,
        delivery_provider: Optional[DeliveryProviderAdapter] = None,
        delivery_repo: Optional[MessageDeliveryRepository] = None,
    ) -> None:
        self._payment = payment
        self._messaging = messaging
        self._escalation = escalation
        self._generator = message_generator
        self._delivery_provider = delivery_provider
        self._delivery_repo = delivery_repo

    def execute(
        self,
        action: RecoveryAction,
        case: RecoveryCase,
        transaction: Transaction,
        customer: Customer,
    ) -> ActionRecord:
        result = self._dispatch(action, case, transaction, customer)
        return ActionRecord(
            merchant_id=case.merchant_id,
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
            result = self._messaging.send_whatsapp(customer.phone or "", msg)

            # Persist message delivery record if repository available
            if self._delivery_repo:
                rec = MessageDeliveryRecord(
                    merchant_id=case.merchant_id,
                    recovery_case_id=case.id,
                    customer_id=customer.id,
                    channel=MessageChannel.WHATSAPP,
                    provider=DeliveryProvider.MOCK,
                    provider_message_id=result.external_ref or f"wa_{case.id[:8]}",
                    status=MessageStatus.DELIVERED if result.outcome == RecoveryOutcome.RECOVERED or "stub" in result.detail else MessageStatus.SENT,
                    content_preview=msg[:120],
                )
                self._delivery_repo.save(rec)

            return result

        if action == RecoveryAction.SEND_EMAIL:
            # First create a payment link to include in the email
            payment_link_result = self._payment.create_payment_link(
                transaction_id=transaction.id,
                amount=transaction.amount,
                customer_email=customer.email or "",
                customer_phone=customer.phone,
                customer_name=customer.name,
            )
            
            # Update context with payment link
            ctx = MessageContext(
                customer_name=customer.name,
                amount=transaction.amount,
                currency=transaction.currency.value,
                failure_reason=transaction.failure_reason,
                payment_link=payment_link_result.external_ref,
            )
            
            body = self._generator.email_body(ctx)
            subject = "Action required — complete your payment"
            
            # Use the new delivery provider if available, otherwise fallback to old messaging
            if self._delivery_provider:
                delivery_result = self._delivery_provider.send_email(
                    recipient_email=customer.email or "",
                    subject=subject,
                    body_html=body,
                    merchant_name=case.merchant_id,
                )
                result = ActionResult(
                    outcome=RecoveryOutcome.RECOVERED if delivery_result.success else RecoveryOutcome.FAILED,
                    detail=delivery_result.failure_reason or "Email sent successfully",
                    external_ref=payment_link_result.external_ref,  # Store payment link URL
                )
                
                # Persist message delivery record if repository available
                if self._delivery_repo:
                    rec = MessageDeliveryRecord(
                        merchant_id=case.merchant_id,
                        recovery_case_id=case.id,
                        customer_id=customer.id,
                        channel=MessageChannel.EMAIL,
                        provider=delivery_result.provider,
                        provider_message_id=delivery_result.provider_message_id or f"email_{case.id[:8]}",
                        status=delivery_result.status,
                        content_preview=f"Subject: {subject} | Link: {payment_link_result.external_ref}",
                    )
                    self._delivery_repo.save(rec)
            else:
                # Fallback to old messaging interface
                result = self._messaging.send_email(customer.email or "", subject, body)

                # Persist message delivery record if repository available
                if self._delivery_repo:
                    rec = MessageDeliveryRecord(
                        merchant_id=case.merchant_id,
                        recovery_case_id=case.id,
                        customer_id=customer.id,
                        channel=MessageChannel.EMAIL,
                        provider=DeliveryProvider.MOCK,
                        provider_message_id=result.external_ref or f"email_{case.id[:8]}",
                        status=MessageStatus.DELIVERED if result.outcome == RecoveryOutcome.RECOVERED or "stub" in result.detail else MessageStatus.SENT,
                        content_preview=f"Subject: {subject} | Link: {payment_link_result.external_ref}",
                    )
                    self._delivery_repo.save(rec)

            return result

        if action == RecoveryAction.ESCALATE:
            return self._escalation.escalate(case.id, case.escalate_reason.value if case.escalate_reason else "unknown")

        # STOP
        return ActionResult(outcome=RecoveryOutcome.STOPPED, detail="Recovery stopped by decision engine.")

