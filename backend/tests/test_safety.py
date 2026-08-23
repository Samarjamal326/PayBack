"""
Safety and zero-cost policy enforcement tests.
Validates that live credentials and live payment operations are strictly blocked.
"""
from __future__ import annotations

import pytest

from app.config import Settings
from app.services.actions.razorpay import LiveKeyForbiddenError, RazorpayPaymentProvider


class TestZeroCostSafety:
    def test_live_key_rejected_by_config(self):
        cfg = Settings(razorpay_key_id="rzp_live_abcdef123456", razorpay_key_secret="secret123")
        with pytest.raises(ValueError) as exc:
            cfg.validate_razorpay_test_mode()
        assert "LIVE" in str(exc.value)

    def test_invalid_key_prefix_rejected_by_config(self):
        cfg = Settings(razorpay_key_id="invalid_prefix_key", razorpay_key_secret="secret123")
        with pytest.raises(ValueError) as exc:
            cfg.validate_razorpay_test_mode()
        assert "rzp_test_" in str(exc.value)

    def test_test_key_accepted_by_config(self):
        cfg = Settings(razorpay_key_id="rzp_test_validtestkey123", razorpay_key_secret="secret123")
        assert cfg.validate_razorpay_test_mode() is True
        assert cfg.razorpay_mode == "TEST"

    def test_unconfigured_key_mode(self):
        cfg = Settings(razorpay_key_id="", razorpay_key_secret="")
        assert cfg.validate_razorpay_test_mode() is False
        assert cfg.razorpay_mode == "UNCONFIGURED"

    def test_provider_refuses_live_key_instantiation(self):
        with pytest.raises(LiveKeyForbiddenError) as exc:
            RazorpayPaymentProvider(
                key_id="rzp_live_liveproductionkey123",
                key_secret="livesecret",
            )
        assert "LIVE Razorpay key detected" in str(exc.value)

    def test_provider_refuses_invalid_key_on_create_link(self):
        with pytest.raises(LiveKeyForbiddenError):
            RazorpayPaymentProvider(
                key_id="rzp_live_test",
                key_secret="secret",
            )
