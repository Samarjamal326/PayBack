from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "razorpay_mode" in data


def test_ready_endpoint():
    resp = client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert "database" in data
    assert "dependencies" in data


def test_dashboard_summary_api():
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_revenue_at_risk" in data
    assert "total_recovered_revenue" in data
    assert "overall_recovery_rate" in data


def test_policies_crud_api():
    # 1. Create policy
    create_resp = client.post(
        "/api/v1/policies",
        json={"name": "Custom Test Policy", "maximum_retries": 5, "high_value_threshold": 50000},
    )
    assert create_resp.status_code == 201
    policy_id = create_resp.json()["id"]

    # 2. Get policy
    get_resp = client.get(f"/api/v1/policies/{policy_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Custom Test Policy"
    assert get_resp.json()["maximum_retries"] == 5

    # 3. Update policy
    update_resp = client.put(
        f"/api/v1/policies/{policy_id}",
        json={"maximum_retries": 4},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["maximum_retries"] == 4


def test_notifications_api():
    # 1. Check unread count
    resp_count = client.get("/api/v1/notifications/unread-count")
    assert resp_count.status_code == 200
    assert "unread_count" in resp_count.json()

    # 2. List notifications
    resp_list = client.get("/api/v1/notifications")
    assert resp_list.status_code == 200
    assert isinstance(resp_list.json(), list)


def test_settings_api():
    resp = client.get("/api/v1/settings/profile")
    assert resp.status_code == 200
    assert "name" in resp.json()

    resp_notif = client.get("/api/v1/settings/notifications")
    assert resp_notif.status_code == 200
    assert "notify_recovery_completed" in resp_notif.json()
