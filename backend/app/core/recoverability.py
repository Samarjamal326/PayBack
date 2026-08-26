"""
Deterministic Recoverability Classifier.
Categorizes failed payment situations into deterministic recoverability classes.
Does not use LLM to ensure reproducible and auditable classification.
"""
from __future__ import annotations

from app.core.probability import RecoveryContext
from app.models.domain import RecoverabilityCategory


class RecoverabilityClassifier:
    """
    Classifies a case into RecoverabilityCategory using deterministic business rules.
    """

    TEMPORARY_FAILURE_REASONS = {
        "network_error",
        "gateway_timeout",
        "bank_server_error",
        "system_busy",
        "insufficient_funds_temporary",
        "otp_timeout",
        "temporary_decline",
        "card_declined_temporary",
        "card_declined",
        "temporary_bank_error",
        "bank_error",
        "timeout",
        "timed_out",
        "test_payment_failure",
    }

    PERMANENT_FAILURE_REASONS = {
        "card_lost_stolen",
        "fraud_suspected",
        "account_closed",
        "invalid_account",
        "expired_card_permanently",
        "expired_instrument",
        "customer_cancelled",
        "do_not_honor_permanently",
    }

    def classify(self, ctx: RecoveryContext) -> tuple[RecoverabilityCategory, str]:
        """
        Returns (RecoverabilityCategory, reason).
        """
        # 1. Immediate Non-Recoverable checks
        if ctx.opted_out:
            return (
                RecoverabilityCategory.NON_RECOVERABLE,
                "Customer has explicitly opted out of communications and recovery.",
            )

        reason = (ctx.failure_reason_raw or "").lower().strip()

        if reason in self.PERMANENT_FAILURE_REASONS:
            return (
                RecoverabilityCategory.NON_RECOVERABLE,
                f"Failure reason '{reason}' represents a permanent non-recoverable error.",
            )

        # 2. Highly Recoverable: temporary failure with strong history
        is_temporary = reason in self.TEMPORARY_FAILURE_REASONS or not reason
        high_history = (
            ctx.previous_transactions >= 2
            and ctx.historical_success_rate >= 0.70
        )

        if is_temporary and high_history:
            return (
                RecoverabilityCategory.HIGHLY_RECOVERABLE,
                "Temporary failure with high historical payment success rate.",
            )

        # 3. Likely Recoverable
        if is_temporary and (ctx.historical_success_rate >= 0.40 or ctx.previous_transactions <= 1):
            return (
                RecoverabilityCategory.LIKELY_RECOVERABLE,
                "Temporary failure with acceptable payment history or new customer intent.",
            )

        # 4. Low Recovery Probability
        low_history = (
            ctx.previous_transactions >= 3
            and ctx.historical_success_rate < 0.30
        )
        repeated_failures = ctx.retry_count >= 2 or ctx.previous_failures >= 3

        if low_history or repeated_failures:
            return (
                RecoverabilityCategory.LOW_RECOVERY_PROBABILITY,
                "Low historical payment success rate or repeated consecutive failure attempts.",
            )

        # 5. Uncertain
        return (
            RecoverabilityCategory.UNCERTAIN,
            "Ambiguous failure signals or conflicting historical payment behavior.",
        )
