from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from app.models.domain import (
    ActionRecord,
    AuditRecord,
    Customer,
    Merchant,
    MerchantSettings,
    MessageDeliveryRecord,
    Notification,
    Policy,
    ProcessedWebhookEvent,
    RecoveryCase,
    Transaction,
)


class MerchantRepository(ABC):
    @abstractmethod
    def save(self, merchant: Merchant) -> Merchant:
        ...

    @abstractmethod
    def get(self, merchant_id: str) -> Optional[Merchant]:
        ...

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[Merchant]:
        ...

    @abstractmethod
    def get_settings(self, merchant_id: str) -> MerchantSettings:
        ...

    @abstractmethod
    def save_settings(self, settings: MerchantSettings) -> MerchantSettings:
        ...


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

    @abstractmethod
    def list_by_merchant(self, merchant_id: Optional[str] = None, limit: int = 100, offset: int = 0, include_unassigned: bool = False) -> list[Customer]:
        ...


class TransactionRepository(ABC):
    @abstractmethod
    def save(self, transaction: Transaction) -> Transaction:
        ...

    @abstractmethod
    def get(self, transaction_id: str) -> Optional[Transaction]:
        ...

    @abstractmethod
    def delete(self, transaction_id: str) -> bool:
        ...

    @abstractmethod
    def list_by_merchant(self, merchant_id: Optional[str] = None, limit: int = 100, offset: int = 0, include_unassigned: bool = False) -> list[Transaction]:
        ...

    @abstractmethod
    def list_by_customer(self, customer_id: str, limit: int = 100) -> list[Transaction]:
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
    def list_by_merchant(
        self,
        merchant_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        include_unassigned: bool = False,
    ) -> list[RecoveryCase]:
        ...

    @abstractmethod
    def list_by_customer(self, customer_id: str, limit: int = 100) -> list[RecoveryCase]:
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
    def list_by_case(self, case_id: str, limit: int = 50) -> list[AuditRecord]:
        ...


class PolicyRepository(ABC):
    @abstractmethod
    def save(self, policy: Policy) -> Policy:
        ...

    @abstractmethod
    def get(self, policy_id: str) -> Optional[Policy]:
        ...

    @abstractmethod
    def get_default(self) -> Policy:
        ...

    @abstractmethod
    def get_active(self, merchant_id: Optional[str] = None) -> Policy:
        ...

    @abstractmethod
    def list_by_merchant(self, merchant_id: Optional[str] = None) -> list[Policy]:
        ...


class MessageDeliveryRepository(ABC):
    @abstractmethod
    def save(self, record: MessageDeliveryRecord) -> MessageDeliveryRecord:
        ...

    @abstractmethod
    def list_by_case(self, case_id: str) -> list[MessageDeliveryRecord]:
        ...

    @abstractmethod
    def list_by_customer(self, customer_id: str) -> list[MessageDeliveryRecord]:
        ...


class NotificationRepository(ABC):
    @abstractmethod
    def save(self, notification: Notification) -> Notification:
        ...

    @abstractmethod
    def list_by_merchant(self, merchant_id: str, limit: int = 50, unread_only: bool = False) -> list[Notification]:
        ...

    @abstractmethod
    def count_unread(self, merchant_id: str) -> int:
        ...

    @abstractmethod
    def mark_read(self, notification_id: str, merchant_id: str) -> Optional[Notification]:
        ...


class ProcessedWebhookEventRepository(ABC):
    @abstractmethod
    def save(self, event: ProcessedWebhookEvent) -> ProcessedWebhookEvent:
        ...

    @abstractmethod
    def get_by_provider_event_id(self, provider: str, provider_event_id: str) -> Optional[ProcessedWebhookEvent]:
        ...

