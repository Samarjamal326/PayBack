from __future__ import annotations

from collections.abc import MutableMapping
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from app.agent.graph import build_recovery_graph
from app.agent.state import RecoveryState
from app.config import settings
from app.core.state_machine import assert_transition
from app.models.domain import (
    ActionRecord,
    AuditEventType,
    AuditRecord,
    Customer,
    Policy,
    RecoveryAction,
    RecoveryCase,
    RecoveryDecision,
    RecoveryOutcome,
    RecoveryStatus,
    Transaction,
    TransactionStatus,
)
from app.repositories.factory import RepositoryBundle, get_repository_bundle
from app.services.actions.executor import ActionExecutor
from app.services.actions.razorpay import RazorpayPaymentProvider
from app.services.actions.stubs import (
    StubEscalationProvider,
    StubMessagingProvider,
    StubPaymentProvider,
)
from app.services.llm.huggingface import HuggingFaceMessageGenerator
from app.services.llm.mock import MockMessageGenerator


class _RepoDictProxy(MutableMapping):
    """
    Backwards compatibility proxy for repository dictionary-like access.
    """

    def __init__(self, repo: Any, key_field: str = "id") -> None:
        self._repo = repo
        self._key_field = key_field

    def __getitem__(self, key: str) -> Any:
        val = self._repo.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __setitem__(self, key: str, value: Any) -> None:
        self._repo.save(value)

    def __delitem__(self, key: str) -> None:
        raise NotImplementedError("Deletion not supported")

    def __iter__(self) -> Iterator[str]:
        return iter([])

    def __len__(self) -> int:
        return 0


class _ActionHistoryProxy(MutableMapping):
    def __init__(self, repo: Any) -> None:
        self._repo = repo

    def __getitem__(self, key: str) -> list[ActionRecord]:
        return self._repo.list_by_case(key)

    def __setitem__(self, key: str, value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                self._repo.save(item)
        else:
            self._repo.save(value)

    def __delitem__(self, key: str) -> None:
        raise NotImplementedError("Deletion not supported")

    def __iter__(self) -> Iterator[str]:
        return iter([])

    def __len__(self) -> int:
        return 0


from app.services.llm.factory import get_message_generator


def _default_executor(repos: Optional[RepositoryBundle] = None) -> ActionExecutor:
    # Use Razorpay Test Mode provider if test keys are configured, otherwise safe stub
    payment_provider = (
        RazorpayPaymentProvider(
            key_id=settings.razorpay_key_id,
            key_secret=settings.razorpay_key_secret,
        )
        if settings.is_razorpay_configured() and settings.razorpay_key_id.startswith("rzp_test_")
        else StubPaymentProvider()
    )

    llm_generator = get_message_generator(settings)
    delivery_repo = repos.message_deliveries if repos else None

    return ActionExecutor(
        payment=payment_provider,
        messaging=StubMessagingProvider(),
        escalation=StubEscalationProvider(),
        message_generator=llm_generator,
        delivery_repo=delivery_repo,
    )




class RecoveryService:
    """
    Application-level recovery service.

    Bridges the FastAPI layer, repositories, decision engine, and LangGraph agent.
    Zero-cost by design: works seamlessly with in-memory or Supabase free tier.
    """

    def __init__(
        self,
        executor: Optional[ActionExecutor] = None,
        repos: Optional[RepositoryBundle] = None,
    ) -> None:
        self._repos = repos or get_repository_bundle()
        self._executor = executor or _default_executor(self._repos)
        self._graph = build_recovery_graph(self._executor).compile()


        # Backwards-compatible proxy mappings
        self._cases = _RepoDictProxy(self._repos.cases)
        self._transactions = _RepoDictProxy(self._repos.transactions)
        self._customers = _RepoDictProxy(self._repos.customers)
        self._history = _ActionHistoryProxy(self._repos.actions)

    def ingest_payment_event(self, transaction: Transaction, customer: Customer) -> RecoveryCase:
        """
        Entry point for incoming payment events.
        Persists customer, transaction, and creates a RecoveryCase if applicable.
        """
        self._customers_repo.save(customer)
        self._transactions_repo.save(transaction)

        if transaction.status == TransactionStatus.SUCCESS:
            raise ValueError("Successful transactions do not require recovery.")

        existing = self._cases_repo.get_by_transaction_id(transaction.id)
        if existing:
            return existing

        case = RecoveryCase(
            transaction_id=transaction.id,
            customer_id=customer.id,
            amount_at_risk=transaction.amount,
            reason=transaction.failure_reason or "payment_not_completed",
            status=RecoveryStatus.DETECTED,
        )
        self._cases_repo.save(case)

        # Audit trail: initial payment failure & case detection
        self.record_audit_event(
            case_id=case.id,
            event_type=AuditEventType.PAYMENT_FAILED,
            detail=f"Payment failed for tx '{transaction.id}' amount {transaction.currency.value} {transaction.amount:,.2f}. Reason: {case.reason}",
        )
        self.record_audit_event(
            case_id=case.id,
            event_type=AuditEventType.RECOVERY_CASE_CREATED,
            detail=f"Recovery case '{case.id}' created with status DETECTED.",
        )

        return case

    def run_recovery(self, case_id: str, policy: Optional[Policy] = None) -> RecoveryCase:
        """Runs the full LangGraph recovery workflow for a case."""
        case = self.get_case(case_id)
        transaction = self._transactions_repo.get(case.transaction_id)
        if not transaction:
            raise KeyError(f"Transaction '{case.transaction_id}' not found.")

        customer = self._customers_repo.get(case.customer_id)
        if not customer:
            raise KeyError(f"Customer '{case.customer_id}' not found.")

        active_policy = policy or self._policies_repo.get_default()

        # Audit: eligibility check started
        self.record_audit_event(
            case_id=case.id,
            event_type=AuditEventType.ELIGIBILITY_CHECKED,
            detail=f"Checking eligibility: opt_out={customer.opted_out}, retry_count={case.retry_count}",
        )

        initial_state: RecoveryState = {
            "transaction": transaction,
            "customer": customer,
            "case": case,
            "policy": active_policy,
            "action_history": [],
            "error": None,
        }

        final_state = self._graph.invoke(initial_state)
        updated_case: RecoveryCase = final_state["case"]

        # Persist updated case
        self._cases_repo.save(updated_case)

        # Persist newly recorded actions
        for action_rec in final_state.get("action_history", []):
            self._actions_repo.save(action_rec)
            self.record_audit_event(
                case_id=case.id,
                event_type=AuditEventType.ACTION_SELECTED,
                detail=f"Action '{action_rec.action.value}' executed with detail: {action_rec.detail}",
            )
            if action_rec.action == RecoveryAction.CREATE_PAYMENT_LINK:
                self.record_audit_event(
                    case_id=case.id,
                    event_type=AuditEventType.PAYMENT_LINK_CREATED,
                    detail=f"Test Payment Link created: {action_rec.external_ref or 'N/A'}",
                )

        # Audit decision / terminal state
        if updated_case.decision:
            self.record_audit_event(
                case_id=case.id,
                event_type=AuditEventType.DECISION_MADE,
                detail=f"Decision '{updated_case.decision.value}' made. Action: '{updated_case.selected_action.value if updated_case.selected_action else 'None'}'. Probability: {updated_case.recovery_probability:.0%}",
            )

        if updated_case.status == RecoveryStatus.STOPPED:
            self.record_audit_event(
                case_id=case.id,
                event_type=AuditEventType.RECOVERY_STOPPED,
                detail=f"Recovery stopped. Reason: {updated_case.stop_reason.value if updated_case.stop_reason else 'unspecified'}",
            )
        elif updated_case.status == RecoveryStatus.ESCALATED:
            self.record_audit_event(
                case_id=case.id,
                event_type=AuditEventType.RECOVERY_ESCALATED,
                detail=f"Recovery escalated to human review. Reason: {updated_case.escalate_reason.value if updated_case.escalate_reason else 'unspecified'}",
            )

        return updated_case

    def mark_case_recovered(
        self,
        case_id: str,
        amount_recovered: float,
        detail: str = "Payment successfully recovered",
    ) -> RecoveryCase:
        """
        Marks a case as RECOVERED upon receiving webhook payment confirmation.
        """
        case = self.get_case(case_id)

        # If still in action_executed or monitoring or decision, assert transition to RECOVERED
        if case.status != RecoveryStatus.RECOVERED:
            if case.status != RecoveryStatus.MONITORING:
                # Transition through monitoring if needed
                case = case.model_copy(
                    update={
                        "status": RecoveryStatus.MONITORING,
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
            assert_transition(case.status, RecoveryStatus.RECOVERED)

        recovered_case = case.model_copy(
            update={
                "status": RecoveryStatus.RECOVERED,
                "outcome": RecoveryOutcome.RECOVERED,
                "amount_recovered": amount_recovered,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._cases_repo.save(recovered_case)

        # Audit events
        self.record_audit_event(
            case_id=case_id,
            event_type=AuditEventType.PAYMENT_SUCCEEDED,
            detail=f"Payment confirmed for INR {amount_recovered:,.2f}. {detail}",
        )
        self.record_audit_event(
            case_id=case_id,
            event_type=AuditEventType.RECOVERY_COMPLETED,
            detail=f"Recovery case '{case_id}' fully completed with outcome RECOVERED.",
        )

        return recovered_case

    def record_audit_event(
        self,
        case_id: str,
        event_type: AuditEventType,
        detail: str,
    ) -> AuditRecord:
        record = AuditRecord(
            recovery_case_id=case_id,
            event_type=event_type,
            detail=detail,
        )
        return self._audits_repo.save(record)

    def get_case(self, case_id: str) -> RecoveryCase:
        case = self._cases_repo.get(case_id)
        if not case:
            raise KeyError(f"Recovery case '{case_id}' not found.")
        return case

    def get_case_by_transaction_id(self, transaction_id: str) -> Optional[RecoveryCase]:
        return self._cases_repo.get_by_transaction_id(transaction_id)

    def get_action_history(self, case_id: str) -> list[ActionRecord]:
        self.get_case(case_id)  # verify case exists
        return self._actions_repo.list_by_case(case_id)

    def get_audit_history(self, case_id: str) -> list[AuditRecord]:
        self.get_case(case_id)  # verify case exists
        return self._audits_repo.list_by_case(case_id)

    # Repository properties for internal access
    @property
    def _customers_repo(self):
        return self._repos.customers

    @property
    def _transactions_repo(self):
        return self._repos.transactions

    @property
    def _cases_repo(self):
        return self._repos.cases

    @property
    def _actions_repo(self):
        return self._repos.actions

    @property
    def _audits_repo(self):
        return self._repos.audits

    @property
    def _policies_repo(self):
        return self._repos.policies
