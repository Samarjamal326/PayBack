"""
Comprehensive tests for webhook signature verification.
These tests focus specifically on the signature verification logic.
"""
from __future__ import annotations

import hashlib
import hmac
import pytest

from app.services.razorpay.webhook import verify_webhook_signature


class TestSignatureVerificationLogic:
    """Test the signature verification function independently."""

    def test_valid_signature_with_exact_match(self):
        """Test signature verification with a valid, exactly matching signature."""
        secret = "test_webhook_secret_123"
        body = b'{"event": "payment_link.paid", "id": "evt_123"}'
        
        # Generate a valid signature
        valid_signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        
        # Verify it should be accepted
        assert verify_webhook_signature(body, valid_signature, secret) is True

    def test_invalid_signature_wrong_secret(self):
        """Test that signature verification fails with wrong secret."""
        secret = "correct_secret"
        wrong_secret = "wrong_secret"
        body = b'{"event": "payment_link.paid"}'
        
        # Generate signature with wrong secret
        wrong_signature = hmac.new(wrong_secret.encode(), body, hashlib.sha256).hexdigest()
        
        # Should fail when verified with correct secret
        assert verify_webhook_signature(body, wrong_signature, secret) is False

    def test_invalid_signature_tampered_body(self):
        """Test that signature verification fails if body is tampered."""
        secret = "test_secret"
        original_body = b'{"event": "payment_link.paid"}'
        tampered_body = b'{"event": "payment.failed"}'
        
        # Generate signature for original body
        signature = hmac.new(secret.encode(), original_body, hashlib.sha256).hexdigest()
        
        # Should fail when verified with tampered body
        assert verify_webhook_signature(tampered_body, signature, secret) is False

    def test_empty_signature_rejected(self):
        """Test that empty signature is rejected."""
        secret = "test_secret"
        body = b'{"event": "payment_link.paid"}'
        
        assert verify_webhook_signature(body, "", secret) is False
        assert verify_webhook_signature(body, None, secret) is False

    def test_empty_secret_rejected(self):
        """Test that empty secret is rejected."""
        body = b'{"event": "payment_link.paid"}'
        signature = hmac.new("secret".encode(), body, hashlib.sha256).hexdigest()
        
        assert verify_webhook_signature(body, signature, "") is False
        assert verify_webhook_signature(body, signature, None) is False

    def test_unicode_handling_in_signature(self):
        """Test that signature verification handles unicode characters correctly."""
        secret = "test_secret_🔒"
        body = '{"event": "payment_link.paid", "customer": "José"}'.encode("utf-8")
        
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(body, signature, secret) is True

    def test_large_payload_signature(self):
        """Test signature verification with large payload."""
        secret = "test_secret"
        # Simulate a large webhook payload
        large_body = b'{"event": "payment_link.paid", "data": "' + b'x' * 10000 + b'"}'
        
        signature = hmac.new(secret.encode(), large_body, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(large_body, signature, secret) is True

    def test_signature_case_sensitivity(self):
        """Test that signature verification is case-sensitive."""
        secret = "test_secret"
        body = b'{"event": "payment_link.paid"}'
        
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        uppercase_signature = signature.upper()
        
        # Should fail with uppercase signature
        assert verify_webhook_signature(body, uppercase_signature, secret) is False

    def test_signature_timing_attack_protection(self):
        """Test that signature verification uses constant-time comparison."""
        secret = "test_secret"
        body = b'{"event": "payment_link.paid"}'
        
        valid_signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        invalid_signature = "a" * len(valid_signature)
        
        # Both should return False/True without timing differences
        # (This is more of a documentation test - the actual timing protection
        # is implemented via hmac.compare_digest in the function)
        assert verify_webhook_signature(body, valid_signature, secret) is True
        assert verify_webhook_signature(body, invalid_signature, secret) is False

    def test_different_hash_algorithms_not_supported(self):
        """Test that only SHA256 is supported (via the implementation)."""
        secret = "test_secret"
        body = b'{"event": "payment_link.paid"}'
        
        # The function only uses SHA256, so we can't test other algorithms
        # This test documents the current implementation
        sha256_signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(body, sha256_signature, secret) is True


class TestSignatureEdgeCases:
    """Test edge cases in signature verification."""

    def test_signature_with_special_characters(self):
        """Test signature with special characters in payload."""
        secret = "test_secret"
        body = b'{"event": "payment_link.paid", "note": "Special: !@#$%^&*()"}'
        
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(body, signature, secret) is True

    def test_signature_with_newlines(self):
        """Test signature with newlines in payload."""
        secret = "test_secret"
        body = b'{"event": "payment_link.paid",\n"id": "123"}'
        
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(body, signature, secret) is True

    def test_signature_format_variations(self):
        """Test different signature format variations."""
        secret = "test_secret"
        body = b'{"event": "payment_link.paid"}'
        
        # Standard hex signature
        hex_signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(body, hex_signature, secret) is True
        
        # Signature with prefix (should fail)
        prefixed_signature = f"sha256={hex_signature}"
        assert verify_webhook_signature(body, prefixed_signature, secret) is False


class TestRealWorldScenarios:
    """Test real-world webhook signature scenarios."""

    def test_razorpay_webhook_format(self):
        """Test with realistic Razorpay webhook format."""
        secret = "rzp_test_secret"
        body = b'''
        {
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": "plink_123",
                        "amount": 100000,
                        "notes": {"transaction_id": "tx_123"}
                    }
                },
                "payment": {
                    "entity": {
                        "id": "pay_456",
                        "amount": 100000,
                        "status": "captured"
                    }
                }
            }
        }
        '''.strip()
        
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(body, signature, secret) is True

    def test_multiple_events_same_signature(self):
        """Test that different events produce different signatures."""
        secret = "test_secret"
        
        event1_body = b'{"event": "payment_link.paid"}'
        event2_body = b'{"event": "payment.failed"}'
        
        sig1 = hmac.new(secret.encode(), event1_body, hashlib.sha256).hexdigest()
        sig2 = hmac.new(secret.encode(), event2_body, hashlib.sha256).hexdigest()
        
        # Signatures should be different
        assert sig1 != sig2
        
        # Each should verify correctly with its own body
        assert verify_webhook_signature(event1_body, sig1, secret) is True
        assert verify_webhook_signature(event2_body, sig2, secret) is True
        
        # Cross-verification should fail
        assert verify_webhook_signature(event1_body, sig2, secret) is False
        assert verify_webhook_signature(event2_body, sig1, secret) is False