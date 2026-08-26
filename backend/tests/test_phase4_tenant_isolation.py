from fastapi.testclient import TestClient
from app.main import app
from app.models.domain import Customer, RecoveryCase, RecoveryStatus, Transaction, TransactionStatus
from app.repositories.factory import get_repository_bundle

client = TestClient(app)
_repos = get_repository_bundle()


def test_merchant_data_isolation():
    # Setup data for Merchant A
    cust_a = _repos.customers.save(Customer(id="cust_a", merchant_id="merchant_a", name="Customer A"))
    tx_a = _repos.transactions.save(Transaction(id="tx_a", merchant_id="merchant_a", customer_id="cust_a", amount=1000, status=TransactionStatus.FAILED))
    case_a = _repos.cases.save(RecoveryCase(id="case_a", merchant_id="merchant_a", transaction_id="tx_a", customer_id="cust_a", amount_at_risk=1000, reason="declined"))

    # Setup data for Merchant B
    cust_b = _repos.customers.save(Customer(id="cust_b", merchant_id="merchant_b", name="Customer B"))
    tx_b = _repos.transactions.save(Transaction(id="tx_b", merchant_id="merchant_b", customer_id="cust_b", amount=2000, status=TransactionStatus.FAILED))
    case_b = _repos.cases.save(RecoveryCase(id="case_b", merchant_id="merchant_b", transaction_id="tx_b", customer_id="cust_b", amount_at_risk=2000, reason="insufficient_funds"))

    # Merchant A can access their own customer
    resp_a = client.get("/api/v1/customers/cust_a", headers={"X-Merchant-ID": "merchant_a"})
    assert resp_a.status_code == 200
    assert resp_a.json()["customer"]["name"] == "Customer A"

    # Merchant A CANNOT access Merchant B's customer
    resp_forbidden = client.get("/api/v1/customers/cust_b", headers={"X-Merchant-ID": "merchant_a"})
    assert resp_forbidden.status_code == 403

    # Merchant A CANNOT access Merchant B's recovery case
    resp_case_forbidden = client.get("/api/v1/recoveries/case_b", headers={"X-Merchant-ID": "merchant_a"})
    assert resp_case_forbidden.status_code == 403

    # Merchant A's recovery list only includes Merchant A cases
    resp_list = client.get("/api/v1/recoveries", headers={"X-Merchant-ID": "merchant_a"})
    assert resp_list.status_code == 200
    case_ids = [c["id"] for c in resp_list.json()]
    assert "case_a" in case_ids
    assert "case_b" not in case_ids
