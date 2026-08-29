import pytest
from fastapi.testclient import TestClient
from app.core.auth import SupabaseJWTAuthProvider, StandardJWT, get_current_merchant, DEFAULT_TEST_MERCHANT
from app.main import app
from app.models.domain import Merchant

client = TestClient(app)


def test_standard_jwt_encode_decode():
    secret = "super-secret-test-key"
    payload = {"sub": "merchant_123", "name": "Test Merchant", "role": "admin"}
    token = StandardJWT.encode(payload, secret)
    assert isinstance(token, str)
    assert len(token.split(".")) == 3

    decoded = StandardJWT.decode(token, secret)
    assert decoded["sub"] == "merchant_123"
    assert decoded["name"] == "Test Merchant"


def test_standard_jwt_invalid_signature():
    secret = "secret-1"
    token = StandardJWT.encode({"sub": "m_1"}, secret)
    with pytest.raises(ValueError, match="signature verification failed"):
        StandardJWT.decode(token, "wrong-secret")


def test_auth_provider_create_and_verify():
    provider = SupabaseJWTAuthProvider(secret_key="auth-test-secret")
    token = provider.create_access_token("m_456", extra_claims={"name": "Priya Store", "email": "priya@store.com"})
    assert token is not None

    verified = provider.verify_token(token)
    assert verified is not None
    assert verified["sub"] == "m_456"
    assert verified["name"] == "Priya Store"


def test_get_current_merchant_fallback_dev_mode():
    merchant = get_current_merchant(credentials=None, x_merchant_id=None)
    assert merchant.id == DEFAULT_TEST_MERCHANT.id
    assert merchant.email == DEFAULT_TEST_MERCHANT.email


def test_demo_admin_login():
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@payback.io", "password": "demo"},
    )
    assert resp.status_code == 200
    assert resp.json()["merchant_id"] == DEFAULT_TEST_MERCHANT.id


def test_get_current_merchant_explicit_header():
    merchant = get_current_merchant(credentials=None, x_merchant_id="merchant_abc")
    assert merchant.id == "merchant_abc"
    assert merchant.name == "Merchant merchant_abc"
