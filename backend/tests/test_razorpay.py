"""
Tests for Razorpay Test Mode Payment Provider.
Validates exact amount, paise conversion, payment link creation, and error handling.
"""
from __future__ import annotations

import httpx
import json
import pytest

from app.models.domain import RecoveryOutcome
from app.services.actions.razorpay import RazorpayPaymentProvider


class TestRazorpayTestModeProvider:
    def test_create_payment_link_payload_and_url(self):
        recorded_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            recorded_requests.append(request)
            data = json.loads(request.read())
            
            # Handle order creation request
            if "/orders" in str(request.url):
                # Verify exact amount in paise: 2499.00 INR -> 249900 paise
                assert data["amount"] == 249900
                assert data["currency"] == "INR"
                assert data["notes"]["transaction_id"] == "tx_123"
                
                return httpx.Response(
                    200,
                    json={
                        "id": "order_test_123",
                        "amount": 249900,
                        "currency": "INR",
                        "receipt": "payback_tx_123",
                    },
                )
            
            # Handle payment link creation request
            elif "/payment_links" in str(request.url):
                # Verify payment link payload
                assert data["amount"] == 249900
                assert data["currency"] == "INR"
                assert data["customer"]["name"] == "Kavita"
                assert data["customer"]["email"] == "kavita@example.com"
                assert data["customer"]["contact"] == "+919876543210"
                assert data["notes"]["transaction_id"] == "tx_123"
                
                return httpx.Response(
                    200,
                    json={
                        "id": "plink_test_999",
                        "short_url": "https://rzp.io/i/test_link_999",
                        "status": "created",
                        "amount": 249900,
                    },
                )
            
            return httpx.Response(404, json={"error": "Not found"})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = RazorpayPaymentProvider(
            key_id="rzp_test_mytestkey",
            key_secret="mysecret",
            http_client=client,
        )

        result = provider.create_payment_link(
            transaction_id="tx_123",
            amount=2499.0,
            customer_email="kavita@example.com",
            customer_name="Kavita",
            customer_phone="+919876543210",
        )

        assert result.outcome == RecoveryOutcome.FAILED  # Pending webhook payment
        assert result.external_ref == "https://rzp.io/i/test_link_999"
        assert "plink_test_999" in result.detail
        assert len(recorded_requests) == 2  # Order creation + payment link creation

    def test_create_payment_link_handles_api_error_gracefully(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": {"description": "Invalid customer phone"}})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = RazorpayPaymentProvider(
            key_id="rzp_test_mytestkey",
            key_secret="mysecret",
            http_client=client,
        )

        result = provider.create_payment_link(
            transaction_id="tx_123",
            amount=500.0,
            customer_email="test@example.com",
        )

        assert result.outcome == RecoveryOutcome.FAILED
        assert "400" in result.detail

    def test_retry_payment_simulated(self):
        provider = RazorpayPaymentProvider(
            key_id="rzp_test_key",
            key_secret="secret",
        )
        res = provider.retry_payment("tx_abc", 1000.0)
        assert res.outcome == RecoveryOutcome.FAILED
        assert "simulated" in res.detail
