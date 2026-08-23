from __future__ import annotations

from typing import Optional

from app.models.domain import (
    ActionRecord,
    AuditRecord,
    Customer,
    Policy,
    RecoveryCase,
    Transaction,
)
from app.repositories.interfaces import (
    ActionRecordRepository,
    AuditRecordRepository,
    CustomerRepository,
    PolicyRepository,
    RecoveryCaseRepository,
    TransactionRepository,
)


class InMemoryCustomerRepository(CustomerRepository):
    def __init__(self) -> None:
        self._store: dict[str, Customer] = {}
        self._by_external_id: dict[str, str] = {}

    def save(self, customer: Customer) -> Customer:
        self._store[customer.id] = customer.model_copy()
        if customer.external_id:
            self._by_external_id[customer.external_id] = customer.id
        return customer

    def get(self, customer_id: str) -> Optional[Customer]:
        item = self._store.get(customer_id)
        return item.model_copy() if item else None

    def get_by_external_id(self, external_id: str) -> Optional[Customer]:
        cid = self._by_external_id.get(external_id)
        if not cid:
            return None
        return self.get(cid)


class InMemoryTransactionRepository(TransactionRepository):
    def __init__(self) -> None:
        self._store: dict[str, Transaction] = {}

    def save(self, transaction: Transaction) -> Transaction:
        self._store[transaction.id] = transaction.model_copy()
        return transaction

    def get(self, transaction_id: str) -> Optional[Transaction]:
        item = self._store.get(transaction_id)
        return item.model_copy() if item else None


class InMemoryRecoveryCaseRepository(RecoveryCaseRepository):
    def __init__(self) -> None:
        self._store: dict[str, RecoveryCase] = {}
        self._by_tx_id: dict[str, str] = {}

    def save(self, case: RecoveryCase) -> RecoveryCase:
        self._store[case.id] = case.model_copy()
        self._by_tx_id[case.transaction_id] = case.id
        return case

    def get(self, case_id: str) -> Optional[RecoveryCase]:
        item = self._store.get(case_id)
        return item.model_copy() if item else None

    def get_by_transaction_id(self, transaction_id: str) -> Optional[RecoveryCase]:
        cid = self._by_tx_id.get(transaction_id)
        if not cid:
            return None
        return self.get(cid)


class InMemoryActionRecordRepository(ActionRecordRepository):
    def __init__(self) -> None:
        self._store: dict[str, list[ActionRecord]] = {}

    def save(self, record: ActionRecord) -> ActionRecord:
        records = self._store.setdefault(record.recovery_case_id, [])
        records.append(record.model_copy())
        return record

    def list_by_case(self, case_id: str) -> list[ActionRecord]:
        return [r.model_copy() for r in self._store.get(case_id, [])]


class InMemoryAuditRecordRepository(AuditRecordRepository):
    def __init__(self) -> None:
        self._store: dict[str, list[AuditRecord]] = {}

    def save(self, record: AuditRecord) -> AuditRecord:
        records = self._store.setdefault(record.recovery_case_id, [])
        records.append(record.model_copy())
        return record

    def list_by_case(self, case_id: str) -> list[AuditRecord]:
        return [r.model_copy() for r in self._store.get(case_id, [])]


class InMemoryPolicyRepository(PolicyRepository):
    def __init__(self) -> None:
        self._policy: Policy = Policy()

    def save(self, policy: Policy) -> Policy:
        self._policy = policy.model_copy()
        return policy

    def get_default(self) -> Policy:
        return self._policy.model_copy()
