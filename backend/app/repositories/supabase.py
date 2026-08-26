from datetime import datetime
from typing import Any, Optional
import httpx

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


class SupabaseClient:
    """
    Minimal zero-dependency REST client for Supabase PostgreSQL free tier.
    Communicates over PostgREST API without requiring heavyweight external SDKs.
    """

    def __init__(self, url: str, key: str) -> None:
        self.url = url.rstrip("/")
        self.key = key
        self._headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def select(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{self.url}/rest/v1/{table}",
                params=params,
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    def insert(self, table: str, data: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{self.url}/rest/v1/{table}",
                json=data,
                headers=self._headers,
            )
            resp.raise_for_status()
            result = resp.json()
            return result[0] if isinstance(result, list) and result else data

    def upsert(self, table: str, data: dict[str, Any], on_conflict: str = "id") -> dict[str, Any]:
        headers = {**self._headers, "Prefer": f"resolution=merge-duplicates,return=representation"}
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{self.url}/rest/v1/{table}",
                params={"on_conflict": on_conflict},
                json=data,
                headers=headers,
            )
            resp.raise_for_status()
            result = resp.json()
            return result[0] if isinstance(result, list) and result else data


class SupabaseCustomerRepository(CustomerRepository):
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def save(self, customer: Customer) -> Customer:
        data = customer.model_dump(mode="json")
        res = self.client.upsert("customers", data)
        return Customer(**res)

    def get(self, customer_id: str) -> Optional[Customer]:
        rows = self.client.select("customers", {"id": f"eq.{customer_id}"})
        return Customer(**rows[0]) if rows else None

    def get_by_external_id(self, external_id: str) -> Optional[Customer]:
        rows = self.client.select("customers", {"external_id": f"eq.{external_id}"})
        return Customer(**rows[0]) if rows else None


class SupabaseTransactionRepository(TransactionRepository):
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def save(self, transaction: Transaction) -> Transaction:
        data = transaction.model_dump(mode="json")
        res = self.client.upsert("transactions", data)
        return Transaction(**res)

    def get(self, transaction_id: str) -> Optional[Transaction]:
        rows = self.client.select("transactions", {"id": f"eq.{transaction_id}"})
        return Transaction(**rows[0]) if rows else None

    def count_by_customer_before(
        self, customer_id: str, before_dt: datetime
    ) -> int:
        iso_ts = before_dt.isoformat()
        rows = self.client.select("transactions", {
            "customer_id": f"eq.{customer_id}",
            "created_at": f"lt.{iso_ts}",
            "select": "id",
        })
        return len(rows)

    def count_successful_by_customer_before(
        self, customer_id: str, before_dt: datetime
    ) -> int:
        iso_ts = before_dt.isoformat()
        rows = self.client.select("transactions", {
            "customer_id": f"eq.{customer_id}",
            "status": "eq.success",
            "created_at": f"lt.{iso_ts}",
            "select": "id",
        })
        return len(rows)

    def count_failed_by_customer_before(
        self, customer_id: str, before_dt: datetime
    ) -> int:
        iso_ts = before_dt.isoformat()
        rows = self.client.select("transactions", {
            "customer_id": f"eq.{customer_id}",
            "status": "eq.failed",
            "created_at": f"lt.{iso_ts}",
            "select": "id",
        })
        return len(rows)


class SupabaseRecoveryCaseRepository(RecoveryCaseRepository):
    # Schema columns supported by Supabase recovery_cases table
    DB_COLUMNS = {
        "id", "transaction_id", "customer_id", "amount_at_risk", "reason",
        "status", "recovery_probability", "selected_action", "decision",
        "stop_reason", "escalate_reason", "outcome", "amount_recovered",
        "retry_count", "message_count", "created_at", "updated_at"
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def save(self, case: RecoveryCase) -> RecoveryCase:
        data = case.model_dump(mode="json")
        # Keep only columns present in Supabase table schema
        db_data = {k: v for k, v in data.items() if k in self.DB_COLUMNS}
        res = self.client.upsert("recovery_cases", db_data)
        # Reconstruct preserving in-memory domain fields
        return case.model_copy(update={k: res[k] for k in res if hasattr(case, k)})


    def get(self, case_id: str) -> Optional[RecoveryCase]:
        rows = self.client.select("recovery_cases", {"id": f"eq.{case_id}"})
        return RecoveryCase(**rows[0]) if rows else None

    def get_by_transaction_id(self, transaction_id: str) -> Optional[RecoveryCase]:
        rows = self.client.select("recovery_cases", {"transaction_id": f"eq.{transaction_id}"})
        return RecoveryCase(**rows[0]) if rows else None

    def count_recovered_by_customer_before(
        self, customer_id: str, before_dt: datetime
    ) -> int:
        iso_ts = before_dt.isoformat()
        # PostgREST or filter: outcome=eq.recovered or status=eq.recovered
        rows = self.client.select("recovery_cases", {
            "customer_id": f"eq.{customer_id}",
            "or": "(outcome.eq.recovered,status.eq.recovered)",
            "created_at": f"lt.{iso_ts}",
            "select": "id",
        })
        return len(rows)


class SupabaseActionRecordRepository(ActionRecordRepository):
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def save(self, record: ActionRecord) -> ActionRecord:
        data = record.model_dump(mode="json")
        res = self.client.insert("action_records", data)
        return ActionRecord(**res)

    def list_by_case(self, case_id: str) -> list[ActionRecord]:
        rows = self.client.select("action_records", {"recovery_case_id": f"eq.{case_id}", "order": "executed_at.asc"})
        return [ActionRecord(**r) for r in rows]


class SupabaseAuditRecordRepository(AuditRecordRepository):
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def save(self, record: AuditRecord) -> AuditRecord:
        data = record.model_dump(mode="json")
        res = self.client.insert("audit_records", data)
        return AuditRecord(**res)

    def list_by_case(self, case_id: str) -> list[AuditRecord]:
        rows = self.client.select("audit_records", {"recovery_case_id": f"eq.{case_id}", "order": "created_at.asc"})
        return [AuditRecord(**r) for r in rows]


class SupabasePolicyRepository(PolicyRepository):
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def save(self, policy: Policy) -> Policy:
        data = policy.model_dump(mode="json")
        data["merchant_id"] = "default"
        res = self.client.upsert("policies", data, on_conflict="merchant_id")
        return Policy(**res)

    def get_default(self) -> Policy:
        rows = self.client.select("policies", {"merchant_id": "eq.default"})
        return Policy(**rows[0]) if rows else Policy()
