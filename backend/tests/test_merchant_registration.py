"""Tests for merchant registration and login data flow."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.repositories.factory import get_repository_bundle

client = TestClient(app)
_repos = get_repository_bundle()


def test_register_creates_merchant_and_settings():
    email = f"merchant_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"name": "Test Store", "email": email, "password": "secret123"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == email
    assert body["access_token"]
    assert body["merchant_id"]

    saved = _repos.merchants.get(body["merchant_id"])
    assert saved is not None
    assert saved.email == email

    settings_obj = _repos.merchants.get_settings(body["merchant_id"])
    assert settings_obj.merchant_id == body["merchant_id"]


def test_login_unknown_email_rejected():
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": f"unknown_{uuid.uuid4().hex}@example.com", "password": "x"},
    )
    assert resp.status_code == 401


def test_duplicate_customer_email_not_created_on_second_payment():
    merchant_header = {"X-Merchant-ID": f"merch_dedup_{uuid.uuid4().hex[:6]}"}
    email = f"rahul_{uuid.uuid4().hex[:6]}@example.com"
    payload = {
        "customer_external_id": "cus_rahul_verma",
        "customer_name": "Rahul Verma",
        "customer_email": email,
        "transaction_amount": 1500.0,
        "payment_method": "upi",
        "transaction_status": "failed",
        "failure_reason": "Insufficient funds",
    }

    first = client.post("/api/v1/events/payment", headers=merchant_header, json=payload)
    second = client.post("/api/v1/events/payment", headers=merchant_header, json=payload)
    assert first.status_code == 201
    assert second.status_code == 201

    customers = _repos.customers.list_by_merchant(merchant_id=merchant_header["X-Merchant-ID"], limit=100)
    matching = [c for c in customers if c.email == email]
    assert len(matching) == 1
