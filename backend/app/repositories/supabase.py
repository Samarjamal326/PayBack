from datetime import datetime
import logging
from typing import Any, Optional
import httpx

logger = logging.getLogger(__name__)


class SupabaseAccessError(RuntimeError):
    """Raised when Supabase REST denies access — do not silently swallow."""

    def __init__(self, table: str, status_code: int, detail: str = "") -> None:
        self.table = table
        self.status_code = status_code
        super().__init__(
            f"Supabase REST access denied for table '{table}' (HTTP {status_code}). "
            "Verify SUPABASE_SERVICE_ROLE_KEY is configured and migration 002 grants are applied. "
            f"{detail}".strip()
        )

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
            if resp.status_code == 404:
                return []
            if resp.status_code in (401, 403):
                raise SupabaseAccessError(table, resp.status_code, resp.text[:300])
            resp.raise_for_status()
            return resp.json()

    def insert(self, table: str, data: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{self.url}/rest/v1/{table}",
                json=data,
                headers=self._headers,
            )
            if resp.status_code in (401, 403):
                raise SupabaseAccessError(table, resp.status_code, resp.text[:300])
            resp.raise_for_status()
            result = resp.json()
            return result[0] if isinstance(result, list) and result else data

    def upsert(self, table: str, data: dict[str, Any], on_conflict: str = "id") -> dict[str, Any]:
        headers = {**self._headers, "Prefer": f"resolution=merge-duplicates,return=representation"}
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{self.url}/rest/v1/{table}?on_conflict={on_conflict}",
                json=data,
                headers=headers,
            )
            if resp.status_code in (401, 403):
                raise SupabaseAccessError(table, resp.status_code, resp.text[:300])
            resp.raise_for_status()
            result = resp.json()
            return result[0] if isinstance(result, list) and result else data

    def delete(self, table: str, params: dict[str, str]) -> None:
        """Delete rows from a table based on filter parameters."""
        headers = {**self._headers, "Prefer": "return=representation"}
        with httpx.Client(timeout=10.0) as client:
            resp = client.delete(
                f"{self.url}/rest/v1/{table}",
                params=params,
                headers=headers,
            )
            if resp.status_code in (401, 403):
                raise SupabaseAccessError(table, resp.status_code, resp.text[:300])
            # 404 is acceptable for delete operations (no rows to delete)
            if resp.status_code not in (200, 204, 404):
                resp.raise_for_status()


class SupabaseCustomerRepository(CustomerRepository):
    DB_COLUMNS = {"id", "merchant_id", "external_id", "name", "email", "phone", "opted_out", "created_at"}

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def save(self, customer: Customer) -> Customer:
        data = customer.model_dump(mode="json")
        db_data = {k: v for k, v in data.items() if k in self.DB_COLUMNS}
        res = self.client.upsert("customers", db_data)
        return customer.model_copy(update={k: res[k] for k in res if hasattr(customer, k)})

    def get(self, customer_id: str) -> Optional[Customer]:
        rows = self.client.select("customers", {"id": f"eq.{customer_id}"})
        return Customer(**rows[0]) if rows else None

    def get_by_external_id(self, external_id: str) -> Optional[Customer]:
        rows = self.client.select("customers", {"external_id": f"eq.{external_id}"})
        return Customer(**rows[0]) if rows else None

    def list_by_merchant(self, merchant_id: Optional[str] = None, limit: int = 100, offset: int = 0, include_unassigned: bool = False) -> list[Customer]:
        params = {"limit": str(limit), "offset": str(offset), "order": "created_at.desc"}
        if merchant_id:
            if include_unassigned:
                params["or"] = f"(merchant_id.eq.{merchant_id},merchant_id.is.null)"
            else:
                params["merchant_id"] = f"eq.{merchant_id}"
        rows = self.client.select("customers", params)
        return [Customer(**r) for r in rows]


class SupabaseTransactionRepository(TransactionRepository):
    DB_COLUMNS = {
        "id", "merchant_id", "customer_id", "amount", "currency", "payment_method",
        "status", "failure_reason", "failure_code", "razorpay_order_id", "razorpay_payment_id",
        "created_at", "updated_at"
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def save(self, transaction: Transaction) -> Transaction:
        data = transaction.model_dump(mode="json")
        db_data = {k: v for k, v in data.items() if k in self.DB_COLUMNS}
        
        # Convert enum values to strings for database compatibility
        if "status" in db_data and hasattr(db_data["status"], "value"):
            db_data["status"] = db_data["status"].value
        if "currency" in db_data and hasattr(db_data["currency"], "value"):
            db_data["currency"] = db_data["currency"].value
        if "payment_method" in db_data and hasattr(db_data["payment_method"], "value"):
            db_data["payment_method"] = db_data["payment_method"].value
        
        # Ensure merchant_id is provided (use default if None)
        if "merchant_id" in db_data and db_data["merchant_id"] is None:
            db_data["merchant_id"] = "merchant_default"
            
        # Remove any fields that are None to avoid constraint issues
        db_data = {k: v for k, v in db_data.items() if v is not None}
            
        res = self.client.upsert("transactions", db_data)
        return transaction.model_copy(update={k: res[k] for k in res if hasattr(transaction, k)})

    def get(self, transaction_id: str) -> Optional[Transaction]:
        rows = self.client.select("transactions", {"id": f"eq.{transaction_id}"})
        return Transaction(**rows[0]) if rows else None

    def delete(self, transaction_id: str) -> bool:
        try:
            self.client.delete("transactions", {"id": f"eq.{transaction_id}"})
            return True
        except Exception:
            return False

    def list_by_merchant(self, merchant_id: Optional[str] = None, limit: int = 100, offset: int = 0, include_unassigned: bool = False) -> list[Transaction]:
        params = {"limit": str(limit), "offset": str(offset), "order": "created_at.desc"}
        if merchant_id:
            if include_unassigned:
                params["or"] = f"(merchant_id.eq.{merchant_id},merchant_id.is.null)"
            else:
                params["merchant_id"] = f"eq.{merchant_id}"
        rows = self.client.select("transactions", params)
        return [Transaction(**r) for r in rows]

    def list_by_customer(self, customer_id: str, limit: int = 100) -> list[Transaction]:
        rows = self.client.select("transactions", {"customer_id": f"eq.{customer_id}", "limit": str(limit), "order": "created_at.desc"})
        return [Transaction(**r) for r in rows]

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
        "id", "merchant_id", "transaction_id", "customer_id", "amount_at_risk", "reason",
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

    def list_by_merchant(
        self,
        merchant_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        include_unassigned: bool = False,
    ) -> list[RecoveryCase]:
        params = {"limit": str(limit), "offset": str(offset), "order": "created_at.desc"}
        if status:
            params["status"] = f"eq.{status}"
        if merchant_id:
            if include_unassigned:
                params["or"] = f"(merchant_id.eq.{merchant_id},merchant_id.is.null)"
            else:
                params["merchant_id"] = f"eq.{merchant_id}"
        rows = self.client.select("recovery_cases", params)
        return [RecoveryCase(**r) for r in rows]


    def list_by_customer(self, customer_id: str, limit: int = 100) -> list[RecoveryCase]:
        rows = self.client.select("recovery_cases", {"customer_id": f"eq.{customer_id}", "limit": str(limit), "order": "created_at.desc"})
        return [RecoveryCase(**r) for r in rows]

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

    def list_by_case(self, case_id: str, limit: int = 50) -> list[AuditRecord]:
        # Optimized: Add limit to prevent excessive data retrieval
        rows = self.client.select("audit_records", {"recovery_case_id": f"eq.{case_id}", "order": "created_at.asc", "limit": str(limit)})
        return [AuditRecord(**r) for r in rows]


class SupabasePolicyRepository(PolicyRepository):
    DB_COLUMNS = {
        "maximum_retries", "maximum_messages", "recovery_window_hours",
        "high_value_threshold", "human_approval_required", "action_costs",
        "merchant_id"
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def save(self, policy: Policy) -> Policy:
        data = policy.model_dump(mode="json")
        data["merchant_id"] = policy.merchant_id or "default"
        db_data = {k: v for k, v in data.items() if k in self.DB_COLUMNS}
        res = self.client.upsert("policies", db_data, on_conflict="merchant_id")
        return policy.model_copy(update={k: res[k] for k in res if hasattr(policy, k)})

    def get(self, policy_id: str) -> Optional[Policy]:
        rows = self.client.select("policies", {"merchant_id": "eq.default"})
        return Policy(**rows[0]) if rows else None

    def get_default(self) -> Policy:
        rows = self.client.select("policies", {"merchant_id": "eq.default"})
        return Policy(**rows[0]) if rows else Policy()

    def get_active(self, merchant_id: Optional[str] = None) -> Policy:
        mid = merchant_id or "default"
        rows = self.client.select("policies", {"merchant_id": f"eq.{mid}"})
        if rows:
            return Policy(**rows[0])
        return self.get_default()

    def list_by_merchant(self, merchant_id: Optional[str] = None) -> list[Policy]:
        mid = merchant_id or "default"
        rows = self.client.select("policies", {"merchant_id": f"eq.{mid}"})
        return [Policy(**r) for r in rows] if rows else [self.get_default()]


class SupabaseMerchantRepository(MerchantRepository):
    DB_COLUMNS = {"id", "name", "email", "phone", "timezone", "created_at"}

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def save(self, merchant: Merchant) -> Merchant:
        data = merchant.model_dump(mode="json")
        db_data = {k: v for k, v in data.items() if k in self.DB_COLUMNS}
        res = self.client.upsert("merchants", db_data)
        return merchant.model_copy(update={k: res[k] for k in res if hasattr(merchant, k)})

    def get(self, merchant_id: str) -> Optional[Merchant]:
        rows = self.client.select("merchants", {"id": f"eq.{merchant_id}"})
        return Merchant(**rows[0]) if rows else None

    def get_by_email(self, email: str) -> Optional[Merchant]:
        rows = self.client.select("merchants", {"email": f"eq.{email}"})
        return Merchant(**rows[0]) if rows else None

    def get_settings(self, merchant_id: str) -> MerchantSettings:
        rows = self.client.select("merchant_settings", {"merchant_id": f"eq.{merchant_id}"})
        if rows:
            return MerchantSettings(**rows[0])
        return MerchantSettings(merchant_id=merchant_id)

    def save_settings(self, settings: MerchantSettings) -> MerchantSettings:
        data = settings.model_dump(mode="json")
        res = self.client.upsert("merchant_settings", data, on_conflict="merchant_id")
        return MerchantSettings(**res)


class SupabaseMessageDeliveryRepository(MessageDeliveryRepository):
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def save(self, record: MessageDeliveryRecord) -> MessageDeliveryRecord:
        data = record.model_dump(mode="json")
        res = self.client.insert("message_delivery_records", data)
        return MessageDeliveryRecord(**res)

    def list_by_case(self, case_id: str) -> list[MessageDeliveryRecord]:
        rows = self.client.select("message_delivery_records", {"recovery_case_id": f"eq.{case_id}", "order": "created_at.asc"})
        return [MessageDeliveryRecord(**r) for r in rows]

    def list_by_customer(self, customer_id: str) -> list[MessageDeliveryRecord]:
        rows = self.client.select("message_delivery_records", {"customer_id": f"eq.{customer_id}", "order": "created_at.asc"})
        return [MessageDeliveryRecord(**r) for r in rows]


class SupabaseNotificationRepository(NotificationRepository):
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def save(self, notification: Notification) -> Notification:
        data = notification.model_dump(mode="json")
        res = self.client.insert("notifications", data)
        return Notification(**res)

    def list_by_merchant(self, merchant_id: str, limit: int = 50, unread_only: bool = False) -> list[Notification]:
        params = {"merchant_id": f"eq.{merchant_id}", "limit": str(limit), "order": "created_at.desc"}
        if unread_only:
            params["read"] = "eq.false"
        rows = self.client.select("notifications", params)
        return [Notification(**r) for r in rows]

    def count_unread(self, merchant_id: str) -> int:
        rows = self.client.select("notifications", {"merchant_id": f"eq.{merchant_id}", "read": "eq.false", "select": "id"})
        return len(rows)

    def mark_read(self, notification_id: str, merchant_id: str) -> Optional[Notification]:
        res = self.client.upsert("notifications", {"id": notification_id, "merchant_id": merchant_id, "read": True})
        return Notification(**res) if res else None


class SupabaseProcessedWebhookRepository(ProcessedWebhookEventRepository):
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def save(self, event: ProcessedWebhookEvent) -> ProcessedWebhookEvent:
        data = event.model_dump(mode="json")
        res = self.client.upsert("processed_webhook_events", data, on_conflict="id")
        return ProcessedWebhookEvent(**res)

    def get_by_provider_event_id(self, provider: str, provider_event_id: str) -> Optional[ProcessedWebhookEvent]:
        rows = self.client.select("processed_webhook_events", {
            "provider": f"eq.{provider}",
            "provider_event_id": f"eq.{provider_event_id}",
        })
        return ProcessedWebhookEvent(**rows[0]) if rows else None


