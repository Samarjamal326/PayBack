"""
Tests for the FastAPI routes.
Uses httpx TestClient — no real server needed.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FAILED_PAYMENT_EVENT = {
    "customer_external_id": "ext-001",
    "customer_name": "Sneha Patel",
    "customer_email": "sneha@example.com",
    "customer_phone": "+919876543210",
    "transaction_amount": 2499.0,
    "transaction_currency": "INR",
    "payment_method": "card",
    "transaction_status": "failed",
    "failure_reason": "card_declined",
}


class TestPaymentEventEndpoint:
    def test_ingest_failed_payment_returns_201(self):
        resp = client.post("/api/v1/events/payment", json=FAILED_PAYMENT_EVENT)
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "detected"
        assert body["amount_at_risk"] == 2499.0

    def test_ingest_successful_payment_returns_422(self):
        payload = {**FAILED_PAYMENT_EVENT, "transaction_status": "success"}
        resp = client.post("/api/v1/events/payment", json=payload)
        assert resp.status_code == 422


class TestRecoveryEndpoints:
    def _create_case(self) -> dict:
        resp = client.post("/api/v1/events/payment", json=FAILED_PAYMENT_EVENT)
        assert resp.status_code == 201
        return resp.json()

    def test_start_recovery_returns_202(self):
        case = self._create_case()
        resp = client.post("/api/v1/recovery", json={"case_id": case["id"]})
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] in ("stopped", "escalated", "recovered", "monitoring")

    def test_get_case_returns_200(self):
        case = self._create_case()
        resp = client.get(f"/api/v1/recovery/{case['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == case["id"]

    def test_get_actions_returns_list(self):
        case = self._create_case()
        client.post("/api/v1/recovery", json={"case_id": case["id"]})
        resp = client.get(f"/api/v1/recovery/{case['id']}/actions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_unknown_recovery_id_returns_404(self):
        resp = client.get("/api/v1/recovery/does-not-exist")
        assert resp.status_code == 404

    def test_unknown_recovery_start_returns_404(self):
        resp = client.post("/api/v1/recovery", json={"case_id": "does-not-exist"})
        assert resp.status_code == 404
