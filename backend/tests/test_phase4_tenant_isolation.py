from fastapi.testclient import TestClient
from app.main import app
from app.models.domain import Customer, RecoveryCase, RecoveryStatus, Transaction, TransactionStatus
from app.repositories.factory import get_repository_bundle

client = TestClient(app)
_repos = get_repository_bundle()


import uuid

def test_merchant_data_isolation():
    # Setup data for Merchant A with valid UUIDs
    cust_a_id = str(uuid.uuid4())
    tx_a_id = str(uuid.uuid4())
    case_a_id = str(uuid.uuid4())
    cust_a = _repos.customers.save(Customer(id=cust_a_id, merchant_id="merchant_a", name="Customer A"))
    tx_a = _repos.transactions.save(Transaction(id=tx_a_id, merchant_id="merchant_a", customer_id=cust_a_id, amount=1000, status=TransactionStatus.FAILED))
    case_a = _repos.cases.save(RecoveryCase(id=case_a_id, merchant_id="merchant_a", transaction_id=tx_a_id, customer_id=cust_a_id, amount_at_risk=1000, reason="declined"))

    # Setup data for Merchant B with valid UUIDs
    cust_b_id = str(uuid.uuid4())
    tx_b_id = str(uuid.uuid4())
    case_b_id = str(uuid.uuid4())
    cust_b = _repos.customers.save(Customer(id=cust_b_id, merchant_id="merchant_b", name="Customer B"))
    tx_b = _repos.transactions.save(Transaction(id=tx_b_id, merchant_id="merchant_b", customer_id=cust_b_id, amount=2000, status=TransactionStatus.FAILED))
    case_b = _repos.cases.save(RecoveryCase(id=case_b_id, merchant_id="merchant_b", transaction_id=tx_b_id, customer_id=cust_b_id, amount_at_risk=2000, reason="insufficient_funds"))

    # Merchant A can access their own customer
    resp_a = client.get(f"/api/v1/customers/{cust_a_id}", headers={"X-Merchant-ID": "merchant_a"})
    assert resp_a.status_code == 200
    assert resp_a.json()["customer"]["name"] == "Customer A"

    # Merchant A CANNOT access Merchant B's customer
    resp_forbidden = client.get(f"/api/v1/customers/{cust_b_id}", headers={"X-Merchant-ID": "merchant_a"})
    assert resp_forbidden.status_code == 403

    # Merchant A CANNOT access Merchant B's recovery case
    resp_case_forbidden = client.get(f"/api/v1/recoveries/{case_b_id}", headers={"X-Merchant-ID": "merchant_a"})
    assert resp_case_forbidden.status_code == 403

    # Merchant A's recovery list only includes Merchant A cases
    resp_list = client.get("/api/v1/recoveries", headers={"X-Merchant-ID": "merchant_a"})
    assert resp_list.status_code == 200
    case_ids = [c["id"] for c in resp_list.json()]
    assert case_a_id in case_ids
    assert case_b_id not in case_ids


def test_payment_ingestion_and_dashboard_isolation():
    # Use unique merchant IDs for this test run
    m_x_id = f"merch_x_{str(uuid.uuid4())[:8]}"
    m_y_id = f"merch_y_{str(uuid.uuid4())[:8]}"

    # Ingest a failed payment event as Merchant X
    resp_x = client.post(
        "/api/v1/events/payment",
        headers={"X-Merchant-ID": m_x_id},
        json={
            "customer_external_id": f"cust_ext_x_{str(uuid.uuid4())[:6]}",
            "customer_name": "Merchant X Customer",
            "customer_email": f"x_{str(uuid.uuid4())[:6]}@example.com",
            "transaction_amount": 3500.0,
            "payment_method": "upi",
            "transaction_status": "failed",
            "failure_reason": "UPI timeout",
        },
    )
    assert resp_x.status_code == 201
    case_x = resp_x.json()
    assert case_x["merchant_id"] == m_x_id
    assert case_x["amount_at_risk"] == 3500.0

    # Ingest a failed payment event as Merchant Y
    resp_y = client.post(
        "/api/v1/events/payment",
        headers={"X-Merchant-ID": m_y_id},
        json={
            "customer_external_id": f"cust_ext_y_{str(uuid.uuid4())[:6]}",
            "customer_name": "Merchant Y Customer",
            "customer_email": f"y_{str(uuid.uuid4())[:6]}@example.com",
            "transaction_amount": 1200.0,
            "payment_method": "card",
            "transaction_status": "failed",
            "failure_reason": "Card declined",
        },
    )
    assert resp_y.status_code == 201
    case_y = resp_y.json()
    assert case_y["merchant_id"] == m_y_id
    assert case_y["amount_at_risk"] == 1200.0

    # Merchant X dashboard only sees Merchant X totals
    dash_x = client.get("/api/v1/dashboard/summary", headers={"X-Merchant-ID": m_x_id})
    assert dash_x.status_code == 200
    assert dash_x.json()["total_revenue_at_risk"] == 3500.0

    # Merchant Y dashboard only sees Merchant Y totals
    dash_y = client.get("/api/v1/dashboard/summary", headers={"X-Merchant-ID": m_y_id})
    assert dash_y.status_code == 200
    assert dash_y.json()["total_revenue_at_risk"] == 1200.0

    # Customer list isolation
    custs_x = client.get("/api/v1/customers", headers={"X-Merchant-ID": m_x_id}).json()
    assert len(custs_x) == 1
    assert custs_x[0]["merchant_id"] == m_x_id


