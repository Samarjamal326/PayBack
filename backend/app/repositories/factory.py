from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.config import Settings, settings
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
from app.repositories.memory import (
    InMemoryActionRecordRepository,
    InMemoryAuditRecordRepository,
    InMemoryCustomerRepository,
    InMemoryMerchantRepository,
    InMemoryMessageDeliveryRepository,
    InMemoryNotificationRepository,
    InMemoryPolicyRepository,
    InMemoryProcessedWebhookEventRepository,
    InMemoryRecoveryCaseRepository,
    InMemoryTransactionRepository,
)
from app.repositories.supabase import (
    SupabaseActionRecordRepository,
    SupabaseAuditRecordRepository,
    SupabaseClient,
    SupabaseCustomerRepository,
    SupabaseMerchantRepository,
    SupabaseMessageDeliveryRepository,
    SupabaseNotificationRepository,
    SupabasePolicyRepository,
    SupabaseProcessedWebhookRepository,
    SupabaseRecoveryCaseRepository,
    SupabaseTransactionRepository,
)


@dataclass
class RepositoryBundle:
    customers: CustomerRepository
    transactions: TransactionRepository
    cases: RecoveryCaseRepository
    actions: ActionRecordRepository
    audits: AuditRecordRepository
    policies: PolicyRepository
    merchants: MerchantRepository = None  # type: ignore
    message_deliveries: MessageDeliveryRepository = None  # type: ignore
    notifications: NotificationRepository = None  # type: ignore
    processed_webhooks: ProcessedWebhookEventRepository = None  # type: ignore

    def __post_init__(self):
        if self.merchants is None:
            self.merchants = InMemoryMerchantRepository()
        if self.message_deliveries is None:
            self.message_deliveries = InMemoryMessageDeliveryRepository()
        if self.notifications is None:
            self.notifications = InMemoryNotificationRepository()
        if self.processed_webhooks is None:
            self.processed_webhooks = InMemoryProcessedWebhookEventRepository()


_shared_in_memory_bundle: Optional[RepositoryBundle] = None


def create_in_memory_repositories() -> RepositoryBundle:
    return RepositoryBundle(
        customers=InMemoryCustomerRepository(),
        transactions=InMemoryTransactionRepository(),
        cases=InMemoryRecoveryCaseRepository(),
        actions=InMemoryActionRecordRepository(),
        audits=InMemoryAuditRecordRepository(),
        policies=InMemoryPolicyRepository(),
        merchants=InMemoryMerchantRepository(),
        message_deliveries=InMemoryMessageDeliveryRepository(),
        notifications=InMemoryNotificationRepository(),
        processed_webhooks=InMemoryProcessedWebhookEventRepository(),
    )


def create_supabase_repositories(url: str, key: str) -> RepositoryBundle:
    client = SupabaseClient(url=url, key=key)
    return RepositoryBundle(
        customers=SupabaseCustomerRepository(client),
        transactions=SupabaseTransactionRepository(client),
        cases=SupabaseRecoveryCaseRepository(client),
        actions=SupabaseActionRecordRepository(client),
        audits=SupabaseAuditRecordRepository(client),
        policies=SupabasePolicyRepository(client),
        merchants=SupabaseMerchantRepository(client),
        message_deliveries=SupabaseMessageDeliveryRepository(client),
        notifications=SupabaseNotificationRepository(client),
        processed_webhooks=SupabaseProcessedWebhookRepository(client),
    )


def get_repository_bundle(app_settings: Optional[Settings] = None) -> RepositoryBundle:
    global _shared_in_memory_bundle
    cfg = app_settings or settings
    key = cfg.supabase_service_role_key or cfg.supabase_anon_key
    # Only use remote Supabase when database_mode/app_env explicitly configured or when requested
    if getattr(cfg, "database_mode", "") == "supabase" or (cfg.supabase_url and key and getattr(cfg, "payback_env", "") == "production"):
        return create_supabase_repositories(cfg.supabase_url, key)
    # Default to zero-cost, offline-safe singleton in-memory bundle for dev and test suites
    if _shared_in_memory_bundle is None:
        _shared_in_memory_bundle = create_in_memory_repositories()
    return _shared_in_memory_bundle



