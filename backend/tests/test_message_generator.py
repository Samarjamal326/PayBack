"""
Tests for the message generation interface and mock implementation.
No real HuggingFace API call — uses MockMessageGenerator.
"""
from __future__ import annotations

from app.services.llm.interface import MessageContext, MessageGenerator
from app.services.llm.mock import MockMessageGenerator


def _ctx(**kwargs) -> MessageContext:
    defaults = dict(
        customer_name="Aditya Kumar",
        amount=1_999.0,
        currency="INR",
        failure_reason="card_declined",
        payment_link="https://rzp.io/l/test123",
    )
    defaults.update(kwargs)
    return MessageContext(**defaults)


class TestMockMessageGenerator:
    def setup_method(self):
        self.gen: MessageGenerator = MockMessageGenerator()

    def test_whatsapp_message_contains_customer_name(self):
        msg = self.gen.whatsapp_message(_ctx())
        assert "Aditya Kumar" in msg

    def test_whatsapp_message_contains_amount(self):
        msg = self.gen.whatsapp_message(_ctx())
        assert "1,999.00" in msg

    def test_whatsapp_message_includes_payment_link(self):
        msg = self.gen.whatsapp_message(_ctx())
        assert "https://rzp.io/l/test123" in msg

    def test_whatsapp_message_without_link(self):
        msg = self.gen.whatsapp_message(_ctx(payment_link=None))
        assert "http" not in msg

    def test_email_body_contains_amount(self):
        body = self.gen.email_body(_ctx())
        assert "1,999.00" in body

    def test_email_body_contains_link(self):
        body = self.gen.email_body(_ctx())
        assert "https://rzp.io/l/test123" in body

    def test_interface_is_satisfied(self):
        # Ensures MockMessageGenerator implements the abstract interface correctly
        assert isinstance(self.gen, MessageGenerator)
