"""
Tests for Phase 2 API endpoints: Health check, Audit trail, and Razorpay Webhook.
"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestPhase2Endpoints:
    def test_health_check_returns_200(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "app_env" in data
        assert "razorpay_mode" in data

    def test_audit_trail_endpoint(self):
        # 1. Ingest payment event
        payload = {
            "customer_external_id": "ext-audit-1",
            "customer_name": "Vikram Seth",
            "customer_email": "vikram@example.com",
            "transaction_amount": 1800.0,
            "transaction_currency": "INR",
            "transaction_status": "failed",
            "failure_reason": "card_declined",
        }
        case_resp = client.post("/api/v1/events/payment", json=payload)
        assert case_resp.status_code == 201
        case_id = case_resp.json()["id"]

        # 2. Query audit trail
        audit_resp = client.get(f"/api/v1/recovery/{case_id}/audit")
        assert audit_resp.status_code == 200
        records = audit_resp.json()
        assert len(records) >= 2  # PAYMENT_FAILED + RECOVERY_CASE_CREATED
        assert records[0]["recovery_case_id"] == case_id

    def test_razorpay_webhook_endpoint(self):
        # Ingest event
        payload = {
            "customer_external_id": "ext-wh-1",
            "customer_name": "Meera",
            "transaction_amount": 999.0,
            "transaction_status": "failed",
        }
        case = client.post("/api/v1/events/payment", json=payload).json()

        webhook_data = {
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": "plink_test_wh_999",
                        "amount": 99900,
                        "notes": {"transaction_id": case["transaction_id"]},
                    }
                },
                "payment": {
                    "entity": {
                        "id": "pay_wh_999",
                        "amount": 99900,
                        "status": "captured",
                        "notes": {"transaction_id": case["transaction_id"]},
                    }
                },
            },
        }

        from app.config import settings
        import hmac, hashlib
        raw_body = json.dumps(webhook_data).encode("utf-8")
        headers = {}
        if settings.razorpay_webhook_secret:
            sig = hmac.new(
                key=settings.razorpay_webhook_secret.encode("utf-8"),
                msg=raw_body,
                digestmod=hashlib.sha256,
            ).hexdigest()
            headers["X-Razorpay-Signature"] = sig

        resp = client.post(
            "/api/v1/events/webhook/razorpay",
            content=raw_body,
            headers={"Content-Type": "application/json", **headers},
        )
        assert resp.status_code == 200

        body = resp.json()
        assert body["status"] == "success"
        assert body["case_id"] == case["id"]

        # Check case is recovered
        updated_case = client.get(f"/api/v1/recovery/{case['id']}").json()
        assert updated_case["status"] == "recovered"
        assert updated_case["amount_recovered"] == 999.0
