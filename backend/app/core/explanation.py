"""
Deterministic Explainability Engine.
Builds transparent, human-readable explanations from structured decision facts.
Does not use LLM for decision reasoning to guarantee auditability.
"""
from __future__ import annotations

from app.core.probability import RecoveryContext
from app.models.domain import (
    ActionCandidate,
    Customer,
    Policy,
    RecoverabilityCategory,
    RecoveryAction,
)


class ExplanationEngine:
    """
    Generates human-readable explanations for merchant dashboards and audit logs.
    """

    def build_explanation(
        self,
        ctx: RecoveryContext,
        customer: Customer,
        policy: Policy,
        category: RecoverabilityCategory,
        probability: float,
        selected: ActionCandidate,
        candidates: list[ActionCandidate],
    ) -> tuple[str, list[str]]:
        """
        Returns (summary_reason, bullet_point_details).
        """
        details: list[str] = []

        # 1. Customer history signal
        if ctx.opted_out:
            details.append("Customer has explicitly opted out of recovery communications.")
        elif ctx.previous_transactions > 0:
            details.append(
                f"Customer has {int(ctx.previous_transactions)} prior transactions "
                f"({ctx.historical_success_rate:.0%} success rate)."
            )
        else:
            details.append("Customer has no prior payment history (new customer).")

        # 2. Failure context
        reason = ctx.failure_reason_raw or "unspecified reason"
        details.append(f"Payment failure classified as {category.value.upper()} (Reason: '{reason}').")

        # 3. Guardrails / Limits
        if ctx.amount >= policy.high_value_threshold:
            details.append(
                f"Transaction amount of INR {ctx.amount:,.2f} meets high-value threshold "
                f"(INR {policy.high_value_threshold:,.2f})."
            )
        if ctx.retry_count > 0 or ctx.messages_sent > 0:
            details.append(
                f"Previous attempts: {int(ctx.retry_count)} retries, "
                f"{int(ctx.messages_sent)} messages sent."
            )
        else:
            details.append("No recovery limits or guardrails exceeded.")

        # 4. Probability & EV rationale
        details.append(
            f"Estimated baseline recovery probability: {probability:.2%} "
            f"(Action: {selected.action.value}, Expected Value: INR {selected.expected_value:,.2f})."
        )

        # 5. Comparative candidate ranking
        eligible_others = [
            c for c in candidates if c.eligible and c.action != selected.action and c.action != RecoveryAction.STOP
        ]
        if eligible_others:
            comp_strs = [f"{c.action.value} (EV: INR {c.expected_value:,.2f})" for c in eligible_others[:2]]
            details.append(f"Compared against alternatives: {', '.join(comp_strs)}.")

        # Summary line
        if selected.action == RecoveryAction.STOP:
            summary = f"Stopped recovery: {details[0]}"
        elif selected.action == RecoveryAction.ESCALATE:
            summary = f"Escalated for human review: High-value transaction of INR {ctx.amount:,.2f}."
        else:
            summary = (
                f"Selected {selected.action.value.upper()} (EV: INR {selected.expected_value:,.2f}, "
                f"Prob: {selected.probability:.1%}) for {category.value.upper()} recovery opportunity."
            )

        return summary, details
