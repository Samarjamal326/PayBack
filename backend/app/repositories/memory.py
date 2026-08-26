from datetime import datetime, timezone
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
from app.repositories.interfaces import (
    ActionRecordRepository,
    AuditRecordRepository,
    CustomerRepository,
    MerchantRepository,
    MessageDeliveryRepository,
    NotificationRepository,
    PolicyRepository,
    ProcessedWebhookEventRepository,
    RecoveryCaseRepository,
    TransactionRepository,
)


class InMemoryMerchantRepository(MerchantRepository):
    def __init__(self) -> None:
        self._store: dict[str, Merchant] = {}
        self._settings: dict[str, MerchantSettings] = {}

    def save(self, merchant: Merchant) -> Merchant:
        self._store[merchant.id] = merchant.model_copy()
        return merchant

    def get(self, merchant_id: str) -> Optional[Merchant]:
        item = self._store.get(merchant_id)
        return item.model_copy() if item else None

    def get_by_email(self, email: str) -> Optional[Merchant]:
        for m in self._store.values():
            if m.email.lower() == email.lower():
                return m.model_copy()
        return None

    def get_settings(self, merchant_id: str) -> MerchantSettings:
        if merchant_id in self._settings:
            return self._settings[merchant_id].model_copy()
        return MerchantSettings(merchant_id=merchant_id)

    def save_settings(self, settings: MerchantSettings) -> MerchantSettings:
        self._settings[settings.merchant_id] = settings.model_copy()
        return settings


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

    def list_by_merchant(self, merchant_id: Optional[str] = None, limit: int = 100, offset: int = 0) -> list[Customer]:
        items = list(self._store.values())
        if merchant_id:
            items = [c for c in items if c.merchant_id == merchant_id or c.merchant_id is None]
        return [c.model_copy() for c in items[offset : offset + limit]]


class InMemoryTransactionRepository(TransactionRepository):
    def __init__(self) -> None:
        self._store: dict[str, Transaction] = {}

    def save(self, transaction: Transaction) -> Transaction:
        self._store[transaction.id] = transaction.model_copy()
        return transaction

    def get(self, transaction_id: str) -> Optional[Transaction]:
        item = self._store.get(transaction_id)
        return item.model_copy() if item else None

    def list_by_merchant(self, merchant_id: Optional[str] = None, limit: int = 100, offset: int = 0) -> list[Transaction]:
        items = list(self._store.values())
        if merchant_id:
            items = [t for t in items if t.merchant_id == merchant_id or t.merchant_id is None]
        return [t.model_copy() for t in items[offset : offset + limit]]

    def list_by_customer(self, customer_id: str, limit: int = 100) -> list[Transaction]:
        items = [t for t in self._store.values() if t.customer_id == customer_id]
        return [t.model_copy() for t in items[:limit]]

    def count_by_customer_before(
        self, customer_id: str, before_dt: datetime
    ) -> int:
        target_dt = before_dt if before_dt.tzinfo is not None else before_dt.replace(tzinfo=timezone.utc)
        count = 0
        for tx in self._store.values():
            if tx.customer_id == customer_id:
                tx_dt = tx.created_at if tx.created_at.tzinfo is not None else tx.created_at.replace(tzinfo=timezone.utc)
                if tx_dt < target_dt:
                    count += 1
        return count

    def count_successful_by_customer_before(
        self, customer_id: str, before_dt: datetime
    ) -> int:
        from app.models.domain import TransactionStatus
        target_dt = before_dt if before_dt.tzinfo is not None else before_dt.replace(tzinfo=timezone.utc)
        count = 0
        for tx in self._store.values():
            if tx.customer_id == customer_id and tx.status == TransactionStatus.SUCCESS:
                tx_dt = tx.created_at if tx.created_at.tzinfo is not None else tx.created_at.replace(tzinfo=timezone.utc)
                if tx_dt < target_dt:
                    count += 1
        return count

    def count_failed_by_customer_before(
        self, customer_id: str, before_dt: datetime
    ) -> int:
        from app.models.domain import TransactionStatus
        target_dt = before_dt if before_dt.tzinfo is not None else before_dt.replace(tzinfo=timezone.utc)
        count = 0
        for tx in self._store.values():
            if tx.customer_id == customer_id and tx.status == TransactionStatus.FAILED:
                tx_dt = tx.created_at if tx.created_at.tzinfo is not None else tx.created_at.replace(tzinfo=timezone.utc)
                if tx_dt < target_dt:
                    count += 1
        return count


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

    def list_by_merchant(
        self,
        merchant_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RecoveryCase]:
        items = list(self._store.values())
        if merchant_id:
            items = [c for c in items if c.merchant_id == merchant_id or c.merchant_id is None]
        if status:
            items = [c for c in items if c.status.value == status or c.status == status]
        return [c.model_copy() for c in items[offset : offset + limit]]

    def list_by_customer(self, customer_id: str, limit: int = 100) -> list[RecoveryCase]:
        items = [c for c in self._store.values() if c.customer_id == customer_id]
        return [c.model_copy() for c in items[:limit]]

    def count_recovered_by_customer_before(
        self, customer_id: str, before_dt: datetime
    ) -> int:
        from app.models.domain import RecoveryOutcome, RecoveryStatus
        target_dt = before_dt if before_dt.tzinfo is not None else before_dt.replace(tzinfo=timezone.utc)
        count = 0
        for case in self._store.values():
            if case.customer_id == customer_id:
                if case.outcome == RecoveryOutcome.RECOVERED or case.status == RecoveryStatus.RECOVERED:
                    case_dt = case.created_at if case.created_at.tzinfo is not None else case.created_at.replace(tzinfo=timezone.utc)
                    if case_dt < target_dt:
                        count += 1
        return count


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
        self._store: dict[str, Policy] = {}
        self._default: Policy = Policy()

    def save(self, policy: Policy) -> Policy:
        self._store[policy.id] = policy.model_copy()
        if policy.is_active:
            self._default = policy.model_copy()
        return policy

    def get(self, policy_id: str) -> Optional[Policy]:
        item = self._store.get(policy_id)
        return item.model_copy() if item else None

    def get_default(self) -> Policy:
        return self._default.model_copy()

    def get_active(self, merchant_id: Optional[str] = None) -> Policy:
        if merchant_id:
            for p in self._store.values():
                if p.merchant_id == merchant_id and p.is_active:
                    return p.model_copy()
        return self.get_default()

    def list_by_merchant(self, merchant_id: Optional[str] = None) -> list[Policy]:
        if not self._store:
            return [self.get_default()]
        items = list(self._store.values())
        if merchant_id:
            items = [p for p in items if p.merchant_id == merchant_id or p.merchant_id is None]
        return [p.model_copy() for p in items]


class InMemoryMessageDeliveryRepository(MessageDeliveryRepository):
    def __init__(self) -> None:
        self._store: dict[str, list[MessageDeliveryRecord]] = {}

    def save(self, record: MessageDeliveryRecord) -> MessageDeliveryRecord:
        records = self._store.setdefault(record.recovery_case_id, [])
        records.append(record.model_copy())
        return record

    def list_by_case(self, case_id: str) -> list[MessageDeliveryRecord]:
        return [r.model_copy() for r in self._store.get(case_id, [])]

    def list_by_customer(self, customer_id: str) -> list[MessageDeliveryRecord]:
        all_records = []
        for records in self._store.values():
            for r in records:
                if r.customer_id == customer_id:
                    all_records.append(r.model_copy())
        return all_records


class InMemoryNotificationRepository(NotificationRepository):
    def __init__(self) -> None:
        self._store: dict[str, list[Notification]] = {}

    def save(self, notification: Notification) -> Notification:
        notifications = self._store.setdefault(notification.merchant_id, [])
        notifications.append(notification.model_copy())
        return notification

    def list_by_merchant(self, merchant_id: str, limit: int = 50, unread_only: bool = False) -> list[Notification]:
        notifications = self._store.get(merchant_id, [])
        if unread_only:
            notifications = [n for n in notifications if not n.read]
        # Return sorted by newest first
        sorted_notifications = sorted(notifications, key=lambda n: n.created_at, reverse=True)
        return [n.model_copy() for n in sorted_notifications[:limit]]

    def count_unread(self, merchant_id: str) -> int:
        notifications = self._store.get(merchant_id, [])
        return sum(1 for n in notifications if not n.read)

    def mark_read(self, notification_id: str, merchant_id: str) -> Optional[Notification]:
        notifications = self._store.get(merchant_id, [])
        for i, n in enumerate(notifications):
            if n.id == notification_id:
                updated = n.model_copy(update={"read": True})
                notifications[i] = updated
                return updated.model_copy()
        return None


class InMemoryProcessedWebhookEventRepository(ProcessedWebhookEventRepository):
    def __init__(self) -> None:
        self._store: dict[str, ProcessedWebhookEvent] = {}

    def save(self, event: ProcessedWebhookEvent) -> ProcessedWebhookEvent:
        key = f"{event.provider}:{event.provider_event_id}"
        self._store[key] = event.model_copy()
        return event

    def get_by_provider_event_id(self, provider: str, provider_event_id: str) -> Optional[ProcessedWebhookEvent]:
        key = f"{provider}:{provider_event_id}"
        item = self._store.get(key)
        return item.model_copy() if item else None

