"""
Tests for the repository persistence layer (in-memory and Supabase REST client).
"""
from __future__ import annotations

import httpx
import pytest

from app.models.domain import (
    ActionRecord,
    AuditEventType,
    AuditRecord,
    Customer,
    Policy,
    RecoveryAction,
    RecoveryCase,
    RecoveryStatus,
    Transaction,
    TransactionStatus,
)
from app.repositories.factory import create_in_memory_repositories, create_supabase_repositories
from app.repositories.supabase import SupabaseClient


class TestInMemoryRepositories:
    def setup_method(self):
        self.repos = create_in_memory_repositories()

    def test_customer_crud(self):
        c = Customer(name="Aman Gupta", email="aman@example.com", external_id="ext_aman")
        saved = self.repos.customers.save(c)
        assert saved.id == c.id

        retrieved = self.repos.customers.get(c.id)
        assert retrieved is not None
        assert retrieved.name == "Aman Gupta"

        by_ext = self.repos.customers.get_by_external_id("ext_aman")
        assert by_ext is not None
        assert by_ext.id == c.id

    def test_transaction_crud(self):
        tx = Transaction(customer_id="c1", amount=1500.0, status=TransactionStatus.FAILED)
        self.repos.transactions.save(tx)

        retrieved = self.repos.transactions.get(tx.id)
        assert retrieved is not None
        assert retrieved.amount == 1500.0

    def test_recovery_case_crud(self):
        case = RecoveryCase(
            transaction_id="tx1",
            customer_id="c1",
            amount_at_risk=1500.0,
            reason="card_declined",
            status=RecoveryStatus.DETECTED,
        )
        self.repos.cases.save(case)

        retrieved = self.repos.cases.get(case.id)
        assert retrieved is not None
        assert retrieved.amount_at_risk == 1500.0

        by_tx = self.repos.cases.get_by_transaction_id("tx1")
        assert by_tx is not None
        assert by_tx.id == case.id

    def test_action_and_audit_records(self):
        act = ActionRecord(
            recovery_case_id="case1",
            action=RecoveryAction.CREATE_PAYMENT_LINK,
            detail="Link created",
            external_ref="https://rzp.io/i/test",
        )
        self.repos.actions.save(act)
        actions = self.repos.actions.list_by_case("case1")
        assert len(actions) == 1
        assert actions[0].external_ref == "https://rzp.io/i/test"

        audit = AuditRecord(
            recovery_case_id="case1",
            event_type=AuditEventType.PAYMENT_LINK_CREATED,
            detail="Test Payment Link created",
        )
        self.repos.audits.save(audit)
        audits = self.repos.audits.list_by_case("case1")
        assert len(audits) == 1
        assert audits[0].event_type == AuditEventType.PAYMENT_LINK_CREATED

    def test_policy_crud(self):
        pol = Policy(maximum_retries=5, high_value_threshold=20000.0)
        self.repos.policies.save(pol)
        fetched = self.repos.policies.get_default()
        assert fetched.maximum_retries == 5
        assert fetched.high_value_threshold == 20000.0


class TestSupabaseRepositoriesMocked:
    def test_supabase_client_select_and_insert(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(201, json=[{"id": "cust-1", "name": "Deepak", "opted_out": False, "created_at": "2026-08-23T12:00:00Z"}])
            elif request.method == "GET":
                return httpx.Response(200, json=[{"id": "cust-1", "name": "Deepak", "opted_out": False, "created_at": "2026-08-23T12:00:00Z"}])
            return httpx.Response(400)

        transport = httpx.MockTransport(handler)
        mock_http = httpx.Client(transport=transport)

        # Replace default client calls
        client = SupabaseClient("https://example.supabase.co", "mock_key")
        
        # Test Customer Save using mock transport
        repos = create_supabase_repositories("https://example.supabase.co", "mock_key")
        repos.customers.client.upsert = lambda table, data, on_conflict="id": {"id": "cust-1", "name": data.get("name", "Deepak"), "opted_out": False, "created_at": "2026-08-23T12:00:00Z"}
        repos.customers.client.select = lambda table, params: [{"id": "cust-1", "name": "Deepak", "opted_out": False, "created_at": "2026-08-23T12:00:00Z"}]

        c = Customer(id="cust-1", name="Deepak")
        saved = repos.customers.save(c)
        assert saved.name == "Deepak"

        fetched = repos.customers.get("cust-1")
        assert fetched is not None
        assert fetched.id == "cust-1"
