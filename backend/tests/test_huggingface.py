"""
Tests for HuggingFaceMessageGenerator (prompt formatting, API mocking, and fallback).
"""
from __future__ import annotations

import httpx
import pytest

from app.services.llm.huggingface import HuggingFaceMessageGenerator
from app.services.llm.interface import MessageContext


class TestHuggingFaceMessageGenerator:
    def test_fallback_when_no_api_key(self):
        gen = HuggingFaceMessageGenerator(api_key="")
        ctx = MessageContext(
            customer_name="Rishi",
            amount=3499.0,
            currency="INR",
            failure_reason="insufficient_funds",
            payment_link="https://rzp.io/i/test",
        )

        msg = gen.whatsapp_message(ctx)
        assert "Rishi" in msg
        assert "3,499.00" in msg
        assert "https://rzp.io/i/test" in msg

        email = gen.email_body(ctx)
        assert "Rishi" in email
        assert "3,499.00" in email

    def test_generated_text_when_api_key_present(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert "Authorization" in request.headers
            return httpx.Response(
                200,
                json=[{"generated_text": "Hi Rishi! Your payment of INR 3,499.00 failed. Please use: https://rzp.io/i/test"}],
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        gen = HuggingFaceMessageGenerator(
            api_key="hf_test_mock_key",
            http_client=client,
        )

        ctx = MessageContext(
            customer_name="Rishi",
            amount=3499.0,
            currency="INR",
            failure_reason="insufficient_funds",
            payment_link="https://rzp.io/i/test",
        )

        msg = gen.whatsapp_message(ctx)
        assert "Hi Rishi!" in msg
        assert "3,499.00" in msg

    def test_resilient_fallback_on_hf_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "Model overloaded"})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        gen = HuggingFaceMessageGenerator(
            api_key="hf_test_key",
            http_client=client,
        )

        ctx = MessageContext(
            customer_name="Rishi",
            amount=1000.0,
            currency="INR",
            failure_reason=None,
            payment_link=None,
        )

        # Should not raise; falls back gracefully
        msg = gen.whatsapp_message(ctx)
        assert "Rishi" in msg
        assert "1,000.00" in msg
