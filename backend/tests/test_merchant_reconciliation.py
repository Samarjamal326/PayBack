"""Tests for merchant footprint selection, reconciliation planning, and tenant isolation."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.core.auth import DEV_MERCHANT_ID
from app.main import app
from app.models.domain import Customer, RecoveryCase, Transaction, TransactionStatus
from app.repositories.factory import get_repository_bundle
from app.services.merchant_reconciliation import (
    MerchantFootprint,
    build_reconciliation_plan,
    classify_merchant,
    select_source_merchant,
)

client = TestClient(app)
_repos = get_repository_bundle()


def test_select_source_merchant_by_total_footprint():
    footprints = [
        MerchantFootprint(merchant_id="merchant_default", customers=62, transactions=44, recovery_cases=26, audit_records=131),
        MerchantFootprint(merchant_id="merchant_a", customers=3, transactions=3, recovery_cases=3),
        MerchantFootprint(merchant_id="merchant_b", customers=3, transactions=3, recovery_cases=3),
    ]
    winner = select_source_merchant(footprints)
    assert winner.merchant_id == "merchant_default"


def test_source_merchant_tie_breaker_by_transactions():
    """Secondary tie-breaker applies when total footprint is equal."""
    footprints = [
        MerchantFootprint(merchant_id="m1", customers=2, transactions=5, recovery_cases=2),
        MerchantFootprint(merchant_id="m2", customers=2, transactions=3, recovery_cases=4),
    ]
    winner = select_source_merchant(footprints)
    assert winner.merchant_id == "m1"


def test_classify_confirmed_test_artifacts():
    assert classify_merchant("merchant_a") == "confirmed_test_artifact"
    assert classify_merchant("merch_dedup_446984") == "confirmed_test_artifact"
    assert classify_merchant("merch_x_abc123") == "confirmed_test_artifact"
    assert classify_merchant("merchant_default") == "protected"


def test_classify_ambiguous_uuid_merchant():
    assert classify_merchant("9422b6ce-216a-428a-87f1-5122eaa12740") == "ambiguous"


def test_reconciliation_plan_from_audit_snapshot():
    """Uses live audit snapshot values from 2026-08-28 Supabase footprint."""
    footprints = [
        MerchantFootprint(merchant_id="merchant_default", customers=62, transactions=44, recovery_cases=26, action_records=11, audit_records=131),
        MerchantFootprint(merchant_id="merchant_a", customers=3, transactions=3, recovery_cases=3),
        MerchantFootprint(merchant_id="merchant_b", customers=3, transactions=3, recovery_cases=3),
        MerchantFootprint(merchant_id="merchant_x", customers=1, transactions=2, recovery_cases=2),
        MerchantFootprint(merchant_id="9422b6ce-216a-428a-87f1-5122eaa12740", customers=1, transactions=1, recovery_cases=1, action_records=1),
        MerchantFootprint(merchant_id="merch_dedup_446984", customers=1, transactions=2, recovery_cases=2),
    ]
    plan = build_reconciliation_plan(footprints)
    assert plan.source_merchant_id == "merchant_default"
    assert not plan.requires_migration
    assert "merchant_a" in plan.discard_merchant_ids
    assert "merchant_b" in plan.discard_merchant_ids
    assert "merch_dedup_446984" in plan.discard_merchant_ids
    assert "9422b6ce-216a-428a-87f1-5122eaa12740" in plan.ambiguous_merchant_ids
    assert "merchant_x" in plan.ambiguous_merchant_ids


def test_demo_admin_dashboard_shows_historical_data():
    cust_id = str(uuid.uuid4())
    tx_id = str(uuid.uuid4())
    case_id = str(uuid.uuid4())
    _repos.customers.save(Customer(id=cust_id, merchant_id=DEV_MERCHANT_ID, name="Admin Customer"))
    _repos.transactions.save(
        Transaction(id=tx_id, merchant_id=DEV_MERCHANT_ID, customer_id=cust_id, amount=5000, status=TransactionStatus.FAILED)
    )
    _repos.cases.save(
        RecoveryCase(id=case_id, merchant_id=DEV_MERCHANT_ID, transaction_id=tx_id, customer_id=cust_id, amount_at_risk=5000, reason="declined")
    )

    resp = client.get("/api/v1/dashboard/summary", headers={"X-Merchant-ID": DEV_MERCHANT_ID})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_revenue_at_risk"] >= 5000.0
    assert body["total_recovery_cases"] >= 1


def test_new_merchant_empty_dashboard():
    new_merchant = f"merchant_new_test_{uuid.uuid4().hex[:8]}"
    resp = client.get("/api/v1/dashboard/summary", headers={"X-Merchant-ID": new_merchant})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_revenue_at_risk"] == 0.0
    assert body["total_recovered_revenue"] == 0.0
    assert body["overall_recovery_rate"] == 0.0
    assert body["active_recovery_cases"] == 0
    assert body["total_recovery_cases"] == 0


def test_critical_isolation_two_clean_merchants():
    m_a = f"merchant_A_test_{uuid.uuid4().hex[:8]}"
    m_b = f"merchant_B_test_{uuid.uuid4().hex[:8]}"

    cust_a = str(uuid.uuid4())
    tx_a = str(uuid.uuid4())
    case_a = str(uuid.uuid4())
    _repos.customers.save(Customer(id=cust_a, merchant_id=m_a, name="A Only"))
    _repos.transactions.save(Transaction(id=tx_a, merchant_id=m_a, customer_id=cust_a, amount=100, status=TransactionStatus.FAILED))
    _repos.cases.save(RecoveryCase(id=case_a, merchant_id=m_a, transaction_id=tx_a, customer_id=cust_a, amount_at_risk=100, reason="x"))

    cust_b = str(uuid.uuid4())
    tx_b = str(uuid.uuid4())
    case_b = str(uuid.uuid4())
    _repos.customers.save(Customer(id=cust_b, merchant_id=m_b, name="B Only"))
    _repos.transactions.save(Transaction(id=tx_b, merchant_id=m_b, customer_id=cust_b, amount=200, status=TransactionStatus.FAILED))
    _repos.cases.save(RecoveryCase(id=case_b, merchant_id=m_b, transaction_id=tx_b, customer_id=cust_b, amount_at_risk=200, reason="y"))

    assert client.get(f"/api/v1/customers/{cust_a}", headers={"X-Merchant-ID": m_a}).status_code == 200
    assert client.get(f"/api/v1/recoveries/{case_a}", headers={"X-Merchant-ID": m_a}).status_code == 200
    assert client.get(f"/api/v1/customers/{cust_b}", headers={"X-Merchant-ID": m_a}).status_code == 403
    assert client.get(f"/api/v1/recoveries/{case_b}", headers={"X-Merchant-ID": m_a}).status_code == 403
    assert client.get(f"/api/v1/customers/{cust_b}", headers={"X-Merchant-ID": m_b}).status_code == 200
    assert client.get(f"/api/v1/customers/{cust_a}", headers={"X-Merchant-ID": m_b}).status_code == 403

    admin_cust = str(uuid.uuid4())
    admin_tx = str(uuid.uuid4())
    admin_case = str(uuid.uuid4())
    _repos.customers.save(Customer(id=admin_cust, merchant_id=DEV_MERCHANT_ID, name="Admin Only"))
    _repos.transactions.save(Transaction(id=admin_tx, merchant_id=DEV_MERCHANT_ID, customer_id=admin_cust, amount=999, status=TransactionStatus.FAILED))
    _repos.cases.save(RecoveryCase(id=admin_case, merchant_id=DEV_MERCHANT_ID, transaction_id=admin_tx, customer_id=admin_cust, amount_at_risk=999, reason="admin"))
    assert client.get(f"/api/v1/customers/{admin_cust}", headers={"X-Merchant-ID": m_a}).status_code == 403
    assert client.get(f"/api/v1/customers/{admin_cust}", headers={"X-Merchant-ID": m_b}).status_code == 403


def test_new_merchant_failed_payment_does_not_affect_admin():
    new_merchant = f"merchant_new_flow_{uuid.uuid4().hex[:8]}"
    admin_before = client.get("/api/v1/dashboard/summary", headers={"X-Merchant-ID": DEV_MERCHANT_ID}).json()

    resp = client.post(
        "/api/v1/events/payment",
        headers={"X-Merchant-ID": new_merchant},
        json={
            "customer_external_id": f"ext_{uuid.uuid4().hex[:6]}",
            "customer_name": "New Merchant Customer",
            "customer_email": f"new_{uuid.uuid4().hex[:6]}@example.com",
            "transaction_amount": 777.0,
            "payment_method": "upi",
            "transaction_status": "failed",
            "failure_reason": "timeout",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["merchant_id"] == new_merchant

    new_dash = client.get("/api/v1/dashboard/summary", headers={"X-Merchant-ID": new_merchant}).json()
    assert new_dash["total_revenue_at_risk"] == 777.0
    assert new_dash["total_recovery_cases"] == 1

    admin_after = client.get("/api/v1/dashboard/summary", headers={"X-Merchant-ID": DEV_MERCHANT_ID}).json()
    assert admin_after["total_revenue_at_risk"] == admin_before["total_revenue_at_risk"]
    assert admin_after["total_recovery_cases"] == admin_before["total_recovery_cases"]
