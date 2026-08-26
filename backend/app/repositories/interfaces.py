from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from app.models.domain import (
    ActionRecord,
    AuditRecord,
    Customer,
    Policy,
    RecoveryCase,
    Transaction,
)


class CustomerRepository(ABC):
    @abstractmethod
    def save(self, customer: Customer) -> Customer:
        ...

    @abstractmethod
    def get(self, customer_id: str) -> Optional[Customer]:
        ...

    @abstractmethod
    def get_by_external_id(self, external_id: str) -> Optional[Customer]:
        ...


class TransactionRepository(ABC):
    @abstractmethod
    def save(self, transaction: Transaction) -> Transaction:
        ...

    @abstractmethod
    def get(self, transaction_id: str) -> Optional[Transaction]:
        ...

    @abstractmethod
    def count_by_customer_before(
        self, customer_id: str, before_dt: datetime
    ) -> int:
        """
        Count all transactions for `customer_id` with created_at < before_dt.
        Used to compute `previous_transactions` for ML feature engineering.
        Does NOT include the current transaction (caller passes its created_at).
        """
        ...

    @abstractmethod
    def count_successful_by_customer_before(
        self, customer_id: str, before_dt: datetime
    ) -> int:
        """
        Count transactions with status='success' for `customer_id`
        with created_at < before_dt.
        Used to compute `historical_success_rate`.
        """
        ...

    @abstractmethod
    def count_failed_by_customer_before(
        self, customer_id: str, before_dt: datetime
    ) -> int:
        """
        Count transactions with status='failed' for `customer_id`
        with created_at < before_dt.
        Used to compute `previous_failures`.
        """
        ...



class RecoveryCaseRepository(ABC):
    @abstractmethod
    def save(self, case: RecoveryCase) -> RecoveryCase:
        ...

    @abstractmethod
    def get(self, case_id: str) -> Optional[RecoveryCase]:
        ...

    @abstractmethod
    def get_by_transaction_id(self, transaction_id: str) -> Optional[RecoveryCase]:
        ...

    @abstractmethod
    def count_recovered_by_customer_before(
        self, customer_id: str, before_dt: datetime
    ) -> int:
        """
        Count recovery cases for `customer_id` whose outcome is RECOVERED
        and whose created_at < before_dt.
        Used to compute `previous_recoveries`.
        """
        ...



class ActionRecordRepository(ABC):
    @abstractmethod
    def save(self, record: ActionRecord) -> ActionRecord:
        ...

    @abstractmethod
    def list_by_case(self, case_id: str) -> list[ActionRecord]:
        ...


class AuditRecordRepository(ABC):
    @abstractmethod
    def save(self, record: AuditRecord) -> AuditRecord:
        ...

    @abstractmethod
    def list_by_case(self, case_id: str) -> list[AuditRecord]:
        ...


class PolicyRepository(ABC):
    @abstractmethod
    def save(self, policy: Policy) -> Policy:
        ...

    @abstractmethod
    def get_default(self) -> Policy:
        ...
