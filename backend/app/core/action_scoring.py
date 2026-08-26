"""
Action Candidate Evaluation and Expected Value Scoring.
Calculates EV = (Probability * Amount_At_Risk) - Action_Cost.
Enforces policy guardrails on candidate eligibility.
"""
from __future__ import annotations

from app.core.probability import RecoveryContext
from app.models.domain import (
    ActionCandidate,
    Policy,
    RecoverabilityCategory,
    RecoveryAction,
)


class ActionScorer:
    """
    Evaluates candidate recovery actions, computes expected value (EV),
    and filters by policy guardrails.
    """

    # Action-specific conversion multipliers relative to case baseline probability
    ACTION_CONVERSION_WEIGHTS = {
        RecoveryAction.RETRY_PAYMENT: 0.90,
        RecoveryAction.CREATE_PAYMENT_LINK: 0.85,
        RecoveryAction.SEND_WHATSAPP: 0.90,
        RecoveryAction.SEND_EMAIL: 0.70,
        RecoveryAction.ESCALATE: 0.80,
        RecoveryAction.STOP: 0.00,
    }


    def generate_and_score_candidates(
        self,
        ctx: RecoveryContext,
        policy: Policy,
        category: RecoverabilityCategory,
        base_probability: float,
    ) -> list[ActionCandidate]:
        """
        Generates all possible recovery action candidates, tests policy eligibility,
        and computes Expected Value.
        """
        candidates: list[ActionCandidate] = []
        amount = ctx.amount

        # 1. STOP candidate
        candidates.append(
            ActionCandidate(
                action=RecoveryAction.STOP,
                probability=0.0,
                expected_value=0.0,
                cost=0.0,
                eligible=True,
            )
        )

        # 2. ESCALATE candidate
        esc_cost = policy.action_costs.get(RecoveryAction.ESCALATE.value, 15.0)
        esc_prob = round(base_probability * self.ACTION_CONVERSION_WEIGHTS[RecoveryAction.ESCALATE], 4)
        esc_ev = round((esc_prob * amount) - esc_cost, 2)
        candidates.append(
            ActionCandidate(
                action=RecoveryAction.ESCALATE,
                probability=esc_prob,
                expected_value=esc_ev,
                cost=esc_cost,
                eligible=True,
            )
        )

        if category == RecoverabilityCategory.NON_RECOVERABLE:
            # For non-recoverable cases, only STOP is eligible
            for c in candidates:
                if c.action != RecoveryAction.STOP:
                    c.eligible = False
                    c.ineligible_reason = "Case is non-recoverable."
            return candidates

        # 3. RETRY_PAYMENT candidate
        retry_cost = policy.action_costs.get(RecoveryAction.RETRY_PAYMENT.value, 2.0)
        retry_prob = round(base_probability * self.ACTION_CONVERSION_WEIGHTS[RecoveryAction.RETRY_PAYMENT], 4)
        retry_ev = round((retry_prob * amount) - retry_cost, 2)
        retry_eligible = True
        retry_reason = None

        if ctx.retry_count >= policy.maximum_retries:
            retry_eligible = False
            retry_reason = f"Exceeded maximum retries ({policy.maximum_retries})."
        elif ctx.payment_method_raw in ("upi",):
            retry_eligible = False
            retry_reason = "Direct merchant retry not supported on UPI collect/intent without customer auth."

        candidates.append(
            ActionCandidate(
                action=RecoveryAction.RETRY_PAYMENT,
                probability=retry_prob,
                expected_value=retry_ev,
                cost=retry_cost,
                eligible=retry_eligible,
                ineligible_reason=retry_reason,
            )
        )

        # 4. CREATE_PAYMENT_LINK candidate
        link_cost = policy.action_costs.get(RecoveryAction.CREATE_PAYMENT_LINK.value, 5.0)
        # Higher conversion on failed transactions than abandoned checkouts
        is_abandoned = (
            ctx.transaction_status == "abandoned"
            or ctx.failure_reason_raw == "abandoned"
            or "abandon" in (ctx.failure_reason_raw or "").lower()
        )
        link_weight = 0.80 if is_abandoned else 0.95
        link_prob = round(base_probability * link_weight, 4)

        link_ev = round((link_prob * amount) - link_cost, 2)
        link_eligible = True
        link_reason = None

        if ctx.messages_sent >= policy.maximum_messages:
            link_eligible = False
            link_reason = f"Exceeded maximum communication limit ({policy.maximum_messages})."

        candidates.append(
            ActionCandidate(
                action=RecoveryAction.CREATE_PAYMENT_LINK,
                probability=link_prob,
                expected_value=link_ev,
                cost=link_cost,
                eligible=link_eligible,
                ineligible_reason=link_reason,
            )
        )


        # 5. SEND_WHATSAPP candidate
        wa_cost = policy.action_costs.get(RecoveryAction.SEND_WHATSAPP.value, 1.0)
        wa_prob = round(base_probability * self.ACTION_CONVERSION_WEIGHTS[RecoveryAction.SEND_WHATSAPP], 4)
        wa_ev = round((wa_prob * amount) - wa_cost, 2)
        wa_eligible = True
        wa_reason = None

        if ctx.messages_sent >= policy.maximum_messages:
            wa_eligible = False
            wa_reason = f"Exceeded maximum communication limit ({policy.maximum_messages})."

        candidates.append(
            ActionCandidate(
                action=RecoveryAction.SEND_WHATSAPP,
                probability=wa_prob,
                expected_value=wa_ev,
                cost=wa_cost,
                eligible=wa_eligible,
                ineligible_reason=wa_reason,
            )
        )

        # 6. SEND_EMAIL candidate
        email_cost = policy.action_costs.get(RecoveryAction.SEND_EMAIL.value, 0.2)
        email_prob = round(base_probability * self.ACTION_CONVERSION_WEIGHTS[RecoveryAction.SEND_EMAIL], 4)
        email_ev = round((email_prob * amount) - email_cost, 2)
        email_eligible = True
        email_reason = None

        if ctx.messages_sent >= policy.maximum_messages:
            email_eligible = False
            email_reason = f"Exceeded maximum communication limit ({policy.maximum_messages})."

        candidates.append(
            ActionCandidate(
                action=RecoveryAction.SEND_EMAIL,
                probability=email_prob,
                expected_value=email_ev,
                cost=email_cost,
                eligible=email_eligible,
                ineligible_reason=email_reason,
            )
        )

        return candidates
