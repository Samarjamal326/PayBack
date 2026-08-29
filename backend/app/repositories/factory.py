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
from app.core.auth import DEFAULT_TEST_MERCHANT, DEV_MERCHANT_ID
from app.models.domain import MerchantSettings
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
_shared_supabase_bundle: Optional[RepositoryBundle] = None


def _seed_development_merchant(bundle: RepositoryBundle) -> None:
    """Ensure the designated development merchant exists for demo login and legacy data."""
    existing = bundle.merchants.get(DEV_MERCHANT_ID)
    if not existing:
        bundle.merchants.save(DEFAULT_TEST_MERCHANT)
    settings_obj = bundle.merchants.get_settings(DEV_MERCHANT_ID)
    if not getattr(settings_obj, "id", None):
        bundle.merchants.save_settings(MerchantSettings(merchant_id=DEV_MERCHANT_ID))


def create_in_memory_repositories() -> RepositoryBundle:
    bundle = RepositoryBundle(
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
    _seed_development_merchant(bundle)
    return bundle


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


def reset_in_memory_repositories() -> RepositoryBundle:
    """Clear all in-memory stores while preserving the singleton instance (test isolation)."""
    global _shared_in_memory_bundle
    if _shared_in_memory_bundle is None:
        _shared_in_memory_bundle = create_in_memory_repositories()
        return _shared_in_memory_bundle

    bundle = _shared_in_memory_bundle
    bundle.merchants._store.clear()  # type: ignore[attr-defined]
    bundle.merchants._settings.clear()  # type: ignore[attr-defined]
    bundle.customers._store.clear()  # type: ignore[attr-defined]
    bundle.customers._by_external_id.clear()  # type: ignore[attr-defined]
    bundle.transactions._store.clear()  # type: ignore[attr-defined]
    bundle.cases._store.clear()  # type: ignore[attr-defined]
    bundle.cases._by_tx_id.clear()  # type: ignore[attr-defined]
    bundle.actions._store.clear()  # type: ignore[attr-defined]
    bundle.audits._store.clear()  # type: ignore[attr-defined]
    bundle.policies._store.clear()  # type: ignore[attr-defined]
    bundle.message_deliveries._store.clear()  # type: ignore[attr-defined]
    bundle.notifications._store.clear()  # type: ignore[attr-defined]
    bundle.processed_webhooks._store.clear()  # type: ignore[attr-defined]
    _seed_development_merchant(bundle)
    return bundle


def get_repository_bundle(app_settings: Optional[Settings] = None) -> RepositoryBundle:
    global _shared_in_memory_bundle, _shared_supabase_bundle
    cfg = app_settings or settings
    key = cfg.supabase_service_role_key or cfg.supabase_anon_key
    use_supabase = (
        cfg.database_mode == "supabase"
        and cfg.supabase_url
        and key
    )
    if use_supabase:
        if not cfg.supabase_service_role_key:
            import logging
            logging.getLogger(__name__).warning(
                "SUPABASE_SERVICE_ROLE_KEY is not set; falling back to anon key. "
                "Backend writes to merchants/policies may fail with HTTP 403."
            )
        if _shared_supabase_bundle is None:
            _shared_supabase_bundle = create_supabase_repositories(cfg.supabase_url, key)
        return _shared_supabase_bundle
    # Default to zero-cost, offline-safe singleton in-memory bundle for dev and test suites
    if _shared_in_memory_bundle is None:
        _shared_in_memory_bundle = create_in_memory_repositories()
    else:
        _seed_development_merchant(_shared_in_memory_bundle)
    return _shared_in_memory_bundle



