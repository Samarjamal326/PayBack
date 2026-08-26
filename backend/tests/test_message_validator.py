"""
Focused unit tests for the deterministic MessageValidator.
All tests are 100% offline — zero LLM dependencies, zero network requests.
"""
from app.services.llm.interface import MessageContext
from app.services.llm.validator import MessageValidator


def _sample_context(**kwargs) -> MessageContext:
    defaults = dict(
        customer_name="Priya Sharma",
        amount=2999.0,
        currency="INR",
        failure_reason="gateway_timeout",
        payment_link="https://rzp.io/i/plink_test123",
        merchant_tone="friendly",
    )
    defaults.update(kwargs)
    return MessageContext(**defaults)


class TestMessageValidator:
    # 1. Valid WhatsApp message remains unchanged (with whitespace normalized)
    def test_valid_whatsapp_message_passes(self):
        ctx = _sample_context()
        raw = (
            "Hi Priya Sharma, your payment of INR 2,999.00 could not be processed. "
            "Please complete it here: https://rzp.io/i/plink_test123\n\n"
            "Reply STOP to opt out."
        )
        validated = MessageValidator.validate_whatsapp(raw, ctx)
        assert validated == raw

    # 2. "recent order" or similar unsupported claim causes fallback
    def test_unsupported_recent_order_claim_triggers_fallback(self):
        ctx = _sample_context()
        raw = (
            "Hello Priya, We noticed there was a delay processing your recent order. "
            "Please check the payment link: https://rzp.io/i/plink_test123. "
            "Reply STOP to opt out."
        )
        validated = MessageValidator.validate_whatsapp(raw, ctx)
        # Unsupported claim must be rejected and replaced with safe fallback
        assert "recent order" not in validated.lower()
        assert "Priya Sharma" in validated
        assert "https://rzp.io/i/plink_test123" in validated
        assert "Reply STOP to opt out." in validated

    # 3. [Customer Support Email] placeholder is rejected/sanitized
    def test_customer_support_placeholder_triggers_fallback(self):
        ctx = _sample_context()
        raw = (
            "<p>Dear Priya Sharma,</p>"
            "<p>Please contact support at [Customer Support Email] or click "
            "<a href='https://rzp.io/i/plink_test123'>here</a>.</p>"
        )
        validated = MessageValidator.validate_email(raw, ctx)
        assert "[Customer Support Email]" not in validated
        assert "[Support Email]" not in validated
        assert "Priya Sharma" in validated
        assert "https://rzp.io/i/plink_test123" in validated

    # 4. Exact payment link is preserved & altered link triggers fallback
    def test_altered_payment_link_triggers_fallback(self):
        ctx = _sample_context()
        raw = (
            "Hi Priya Sharma, please pay at https://evil-phishing.com/pay. "
            "Reply STOP to opt out."
        )
        validated = MessageValidator.validate_whatsapp(raw, ctx)
        assert "https://evil-phishing.com/pay" not in validated
        assert "https://rzp.io/i/plink_test123" in validated

    # 5. Exact payment link is required if context provides one
    def test_missing_payment_link_triggers_fallback(self):
        ctx = _sample_context()
        raw = "Hi Priya Sharma, your payment failed. Reply STOP to opt out."
        validated = MessageValidator.validate_whatsapp(raw, ctx)
        assert "https://rzp.io/i/plink_test123" in validated

    # 6. Exact currency and amount are in fallback
    def test_fallback_contains_exact_amount_and_currency(self):
        ctx = _sample_context(amount=14500.50, currency="INR")
        validated = MessageValidator.validate_whatsapp("", ctx)
        assert "INR" in validated
        assert "14,500.50" in validated

    # 7. LLM cannot introduce a discount
    def test_discount_claim_triggers_fallback(self):
        ctx = _sample_context()
        raw = (
            "Hi Priya Sharma, we added a 10% discount to your payment link: "
            "https://rzp.io/i/plink_test123. Reply STOP to opt out."
        )
        validated = MessageValidator.validate_whatsapp(raw, ctx)
        assert "discount" not in validated.lower()
        assert "https://rzp.io/i/plink_test123" in validated

    # 8. WhatsApp always contains "Reply STOP to opt out."
    def test_whatsapp_appends_opt_out_if_missing(self):
        ctx = _sample_context()
        raw = (
            "Hi Priya Sharma, please complete your payment at "
            "https://rzp.io/i/plink_test123."
        )
        validated = MessageValidator.validate_whatsapp(raw, ctx)
        assert "Reply STOP to opt out." in validated
        assert "https://rzp.io/i/plink_test123" in validated

    # 9. Invalid/None/Empty output triggers deterministic fallback
    def test_empty_or_none_output_triggers_fallback(self):
        ctx = _sample_context()
        assert MessageValidator.validate_whatsapp(None, ctx) == MessageValidator.get_fallback_whatsapp(ctx)
        assert MessageValidator.validate_whatsapp("", ctx) == MessageValidator.get_fallback_whatsapp(ctx)
        assert MessageValidator.validate_email(None, ctx) == MessageValidator.get_fallback_email(ctx)

    # 10. Valid email HTML passes
    def test_valid_email_html_passes(self):
        ctx = _sample_context()
        raw_html = (
            "<p>Dear Priya Sharma,</p>"
            "<p>Your payment of INR 2,999.00 could not be processed.</p>"
            "<p><a href='https://rzp.io/i/plink_test123'>Complete Payment</a></p>"
        )
        validated = MessageValidator.validate_email(raw_html, ctx)
        assert "<p>Dear Priya Sharma,</p>" in validated
        assert "https://rzp.io/i/plink_test123" in validated

    # 11. Invalid email placeholder triggers sanitization/fallback
    def test_invalid_email_with_todo_or_tbd_triggers_fallback(self):
        ctx = _sample_context()
        raw_html = (
            "<p>Dear Priya Sharma, your order status is TODO. "
            "Link: https://rzp.io/i/plink_test123</p>"
        )
        validated = MessageValidator.validate_email(raw_html, ctx)
        assert "TODO" not in validated
        assert "<p>Dear Priya Sharma,</p>" in validated

    # 12. Validator works independently of Ollama
    def test_validator_pure_unit_functionality(self):
        ctx = _sample_context(payment_link=None)
        raw = "Hi Priya Sharma, your payment failed. Reply STOP to opt out."
        validated = MessageValidator.validate_whatsapp(raw, ctx)
        assert "Priya Sharma" in validated
        assert "Reply STOP to opt out." in validated
        # No link was given, so no link should be introduced
        assert "http" not in validated
