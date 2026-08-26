"""
Deterministic Synthetic Dataset Generator for PayBack evaluation and benchmarking.
Generates realistic payment failure events, customer payment histories, opt-outs, and checkout abandonment.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List

from app.core.probability import RecoveryContext, recovery_context_from_domain
from app.models.domain import (
    Customer,
    PaymentMethod,
    Policy,
    RecoveryCase,
    RecoveryStatus,
    Transaction,
    TransactionStatus,
)


@dataclass
class SyntheticCase:
    context: RecoveryContext
    transaction: Transaction
    customer: Customer
    policy: Policy
    ground_truth_will_pay_if_prompted: bool
    scenario_type: str


class SyntheticDataGenerator:
    """
    Generates deterministic evaluation datasets.
    """

    FIRST_NAMES = ["Rahul", "Priya", "Amit", "Sneha", "Vikram", "Ananya", "Rohan", "Pooja", "Arjun", "Neha"]
    LAST_NAMES = ["Sharma", "Verma", "Patel", "Mehta", "Singh", "Gupta", "Kumar", "Iyer", "Rao", "Joshi"]

    FAILURE_REASONS_TEMPORARY = [
        "network_error",
        "gateway_timeout",
        "bank_server_error",
        "system_busy",
        "otp_timeout",
        "card_declined_temporary",
    ]

    FAILURE_REASONS_PERMANENT = [
        "card_lost_stolen",
        "fraud_suspected",
        "account_closed",
        "customer_cancelled",
    ]

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_dataset(self, size: int = 100) -> List[SyntheticCase]:
        """
        Generates a batch of synthetic recovery cases.
        """
        cases: List[SyntheticCase] = []
        for i in range(size):
            case = self._generate_single_case(i)
            cases.append(case)
        return cases

    def _generate_single_case(self, index: int) -> SyntheticCase:
        name = f"{self.rng.choice(self.FIRST_NAMES)} {self.rng.choice(self.LAST_NAMES)}"
        email = f"user_{index}_{self.seed}@example.com"
        phone = f"+9198{self.rng.randint(10000000, 99999999)}"

        roll = self.rng.random()

        opted_out = False
        status = TransactionStatus.FAILED
        failure_reason = self.rng.choice(self.FAILURE_REASONS_TEMPORARY)
        pm = self.rng.choice([PaymentMethod.UPI, PaymentMethod.CARD, PaymentMethod.NET_BANKING])
        amount = round(self.rng.uniform(299.0, 4999.0), 2)
        total_tx = self.rng.randint(1, 15)
        success_rate = round(self.rng.uniform(0.6, 0.95), 2)
        ground_truth_will_pay = False
        scenario_type = "standard_temporary"

        if roll < 0.10:
            opted_out = True
            scenario_type = "opted_out"
            ground_truth_will_pay = False
        elif roll < 0.25:
            failure_reason = self.rng.choice(self.FAILURE_REASONS_PERMANENT)
            scenario_type = "permanent_failure"
            ground_truth_will_pay = False
        elif roll < 0.45:
            scenario_type = "highly_recoverable_returning"
            total_tx = self.rng.randint(5, 20)
            success_rate = round(self.rng.uniform(0.80, 0.98), 2)
            ground_truth_will_pay = True
        elif roll < 0.70:
            scenario_type = "likely_recoverable"
            total_tx = self.rng.randint(1, 6)
            success_rate = round(self.rng.uniform(0.40, 0.75), 2)
            ground_truth_will_pay = self.rng.random() < 0.65
        elif roll < 0.85:
            scenario_type = "abandoned_checkout"
            status = TransactionStatus.ABANDONED
            failure_reason = None
            ground_truth_will_pay = self.rng.random() < 0.50
        else:
            scenario_type = "high_value_transaction"
            amount = round(self.rng.uniform(12000.0, 35000.0), 2)
            ground_truth_will_pay = self.rng.random() < 0.70

        customer = Customer(
            id=f"cust_syn_{index}",
            name=name,
            email=email,
            phone=phone,
            opted_out=opted_out,
        )

        tx = Transaction(
            id=f"tx_syn_{index}",
            customer_id=customer.id,
            amount=amount,
            currency="INR",
            payment_method=pm,
            status=status,
            failure_reason=failure_reason,
        )

        policy = Policy()

        succ_tx = int(total_tx * success_rate)
        fail_tx = total_tx - succ_tx

        ctx = RecoveryContext(
            amount=amount,
            payment_method_raw=pm.value,
            failure_reason_raw=failure_reason or "",
            transaction_status=status.value,
            retry_count=0,
            messages_sent=0,
            opted_out=opted_out,
            customer_tenure_days=float(self.rng.randint(10, 365)),
            previous_transactions=float(total_tx),
            historical_success_rate=success_rate,
            previous_failures=float(fail_tx),
            previous_recoveries=float(max(0, succ_tx - 1)),
            days_since_failure=round(self.rng.uniform(0.1, 2.0), 2),
            checkout_intent_score=0.5,
        )

        return SyntheticCase(
            context=ctx,
            transaction=tx,
            customer=customer,
            policy=policy,
            ground_truth_will_pay_if_prompted=ground_truth_will_pay,
            scenario_type=scenario_type,
        )
