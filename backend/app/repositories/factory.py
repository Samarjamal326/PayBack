from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.config import Settings, settings
from app.repositories.interfaces import (
    ActionRecordRepository,
    AuditRecordRepository,
    CustomerRepository,
    PolicyRepository,
    RecoveryCaseRepository,
    TransactionRepository,
)
from app.repositories.memory import (
    InMemoryActionRecordRepository,
    InMemoryAuditRecordRepository,
    InMemoryCustomerRepository,
    InMemoryPolicyRepository,
    InMemoryRecoveryCaseRepository,
    InMemoryTransactionRepository,
)
from app.repositories.supabase import (
    SupabaseActionRecordRepository,
    SupabaseAuditRecordRepository,
    SupabaseClient,
    SupabaseCustomerRepository,
    SupabasePolicyRepository,
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


def create_in_memory_repositories() -> RepositoryBundle:
    return RepositoryBundle(
        customers=InMemoryCustomerRepository(),
        transactions=InMemoryTransactionRepository(),
        cases=InMemoryRecoveryCaseRepository(),
        actions=InMemoryActionRecordRepository(),
        audits=InMemoryAuditRecordRepository(),
        policies=InMemoryPolicyRepository(),
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
    )


def get_repository_bundle(app_settings: Optional[Settings] = None) -> RepositoryBundle:
    cfg = app_settings or settings
    key = cfg.supabase_service_role_key or cfg.supabase_anon_key
    if cfg.supabase_url and key:
        return create_supabase_repositories(cfg.supabase_url, key)
    return create_in_memory_repositories()
