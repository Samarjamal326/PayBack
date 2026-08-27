"""
Live Integration Tests (Supabase & Razorpay Test Mode).
These tests run only when valid external test credentials are set in the environment.
Otherwise, they skip gracefully, keeping CI and local unit tests 100% deterministic and zero-cost.
"""
from __future__ import annotations

import os
import pytest

from app.config import settings
from app.models.domain import Customer, PaymentMethod, RecoveryStatus, Transaction, TransactionStatus
from app.repositories.factory import create_supabase_repositories
from app.services.actions.razorpay import RazorpayPaymentProvider


@pytest.mark.skipif(
    not (settings.supabase_url and (settings.supabase_service_role_key or settings.supabase_anon_key)),
    reason="Real Supabase credentials not set in environment.",
)
class TestLiveSupabase:
    def test_live_supabase_customer_roundtrip(self):
        key = settings.supabase_service_role_key or settings.supabase_anon_key
        repos = create_supabase_repositories(settings.supabase_url, key)

        c = Customer(
            name="Live Test Customer",
            email="live_test@example.com",
            phone="+919876543210",
            external_id="ext_live_001",
        )
        saved = repos.customers.save(c)
        assert saved.id == c.id

        fetched = repos.customers.get(c.id)
        assert fetched is not None
        assert fetched.name == "Live Test Customer"


@pytest.mark.skipif(
    not (settings.is_razorpay_configured() and settings.razorpay_key_id.startswith("rzp_test_")),
    reason="Real Razorpay Test Mode credentials not set in environment.",
)
class TestLiveRazorpayTestMode:
    def test_live_razorpay_create_test_payment_link(self):
        settings.validate_razorpay_test_mode()
        provider = RazorpayPaymentProvider(
            key_id=settings.razorpay_key_id,
            key_secret=settings.razorpay_key_secret,
        )

        res = provider.create_payment_link(
            transaction_id="tx_live_test_001",
            amount=2499.0,
            customer_email="test_buyer@example.com",
            customer_name="Test Buyer",
            customer_phone="+919876543210",
        )

        # Razorpay Test Mode payment_link quota may be exhausted (HTTP 429 / RATE_LIMIT_EXCEEDED).
        # This is an external platform limitation, NOT an application failure.
        # Skip the assertions cleanly rather than failing the suite.
        detail = res.detail or ""
        if "RATE_LIMIT_EXCEEDED" in detail or "rate_limit" in detail.lower() or "429" in detail:
            pytest.skip(
                f"Razorpay Test Mode payment_link quota exhausted (RATE_LIMIT_EXCEEDED): {detail[:300]}"
            )

        assert res.external_ref is not None
        assert "http" in res.external_ref
