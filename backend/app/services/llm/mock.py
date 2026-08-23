from __future__ import annotations

from app.services.llm.interface import MessageContext, MessageGenerator


class MockMessageGenerator(MessageGenerator):
    """
    Template-based generator used in tests and Phase 1.
    No network calls. No API key required.
    """

    def whatsapp_message(self, ctx: MessageContext) -> str:
        link_part = f"\n\nComplete your payment here: {ctx.payment_link}" if ctx.payment_link else ""
        return (
            f"Hi {ctx.customer_name}, your payment of "
            f"{ctx.currency} {ctx.amount:,.2f} could not be processed."
            f"{link_part}\n\nReply STOP to opt out."
        )

    def email_body(self, ctx: MessageContext) -> str:
        link_part = f"\n\n<a href='{ctx.payment_link}'>Complete Payment</a>" if ctx.payment_link else ""
        return (
            f"<p>Dear {ctx.customer_name},</p>"
            f"<p>We were unable to process your payment of {ctx.currency} {ctx.amount:,.2f}.</p>"
            f"{link_part}"
            f"<p>If you have any questions, please contact support.</p>"
        )
