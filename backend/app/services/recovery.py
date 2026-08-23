from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.agent.graph import build_recovery_graph
from app.agent.state import RecoveryState
from app.models.domain import (
    ActionRecord,
    Customer,
    Policy,
    RecoveryCase,
    RecoveryStatus,
    Transaction,
    TransactionStatus,
)
from app.services.actions.executor import ActionExecutor
from app.services.actions.stubs import (
    StubEscalationProvider,
    StubMessagingProvider,
    StubPaymentProvider,
)
from app.services.llm.mock import MockMessageGenerator


def _default_executor() -> ActionExecutor:
    return ActionExecutor(
        payment=StubPaymentProvider(),
        messaging=StubMessagingProvider(),
        escalation=StubEscalationProvider(),
        message_generator=MockMessageGenerator(),
    )


class RecoveryService:
    """
    Application-level service.

    Bridges the FastAPI layer and the LangGraph agent.
    Owns in-memory state for Phase 1 (Supabase replaces this in Phase 2).
    """

    def __init__(self, executor: Optional[ActionExecutor] = None) -> None:
        self._executor = executor or _default_executor()
        self._graph = build_recovery_graph(self._executor).compile()

        # Phase 1 in-memory stores — replaced by repository pattern in Phase 2
        self._cases: dict[str, RecoveryCase] = {}
        self._transactions: dict[str, Transaction] = {}
        self._customers: dict[str, Customer] = {}
        self._history: dict[str, list[ActionRecord]] = {}

    def ingest_payment_event(self, transaction: Transaction, customer: Customer) -> RecoveryCase:
        """
        Entry point for incoming payment events.
        Creates a RecoveryCase if the transaction warrants investigation.
        """
        self._transactions[transaction.id] = transaction
        self._customers[customer.id] = customer

        if transaction.status == TransactionStatus.SUCCESS:
            raise ValueError("Successful transactions do not require recovery.")

        case = RecoveryCase(
            transaction_id=transaction.id,
            customer_id=customer.id,
            amount_at_risk=transaction.amount,
            reason=transaction.failure_reason or "payment_not_completed",
            status=RecoveryStatus.DETECTED,
        )
        self._cases[case.id] = case
        self._history[case.id] = []
        return case

    def run_recovery(self, case_id: str, policy: Optional[Policy] = None) -> RecoveryCase:
        """Runs the full LangGraph recovery workflow for a case."""
        case = self._cases[case_id]
        transaction = self._transactions[case.transaction_id]
        customer = self._customers[case.customer_id]

        initial_state: RecoveryState = {
            "transaction": transaction,
            "customer": customer,
            "case": case,
            "policy": policy or Policy(),
            "action_history": [],
            "error": None,
        }

        final_state = self._graph.invoke(initial_state)

        self._cases[case_id] = final_state["case"]
        self._history[case_id].extend(final_state.get("action_history", []))
        return self._cases[case_id]

    def get_case(self, case_id: str) -> RecoveryCase:
        if case_id not in self._cases:
            raise KeyError(f"Recovery case {case_id!r} not found.")
        return self._cases[case_id]

    def get_action_history(self, case_id: str) -> list[ActionRecord]:
        if case_id not in self._history:
            raise KeyError(f"Recovery case {case_id!r} not found.")
        return self._history[case_id]
