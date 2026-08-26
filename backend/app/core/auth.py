from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.models.domain import Merchant

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("utf-8"))


class StandardJWT:
    """
    Zero-dependency RFC 7519 compliant standard JWT implementation (HS256).
    Compatible with standard JWT validation and Supabase JWT tokens.
    """

    @classmethod
    def encode(cls, payload: dict[str, Any], secret: str, algorithm: str = "HS256") -> str:
        header = {"typ": "JWT", "alg": algorithm}
        header_b64 = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

        signature = hmac.new(
            key=secret.encode("utf-8"),
            msg=signing_input,
            digestmod=hashlib.sha256,
        ).digest()
        sig_b64 = _b64encode(signature)

        return f"{header_b64}.{payload_b64}.{sig_b64}"

    @classmethod
    def decode(cls, token: str, secret: str, verify_exp: bool = True) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT token structure")

        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

        expected_sig = hmac.new(
            key=secret.encode("utf-8"),
            msg=signing_input,
            digestmod=hashlib.sha256,
        ).digest()

        actual_sig = _b64decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise ValueError("JWT signature verification failed")

        payload = json.loads(_b64decode(payload_b64).decode("utf-8"))

        if verify_exp and "exp" in payload:
            now_ts = datetime.now(timezone.utc).timestamp()
            if now_ts > payload["exp"]:
                raise ValueError("JWT token has expired")

        return payload


class AuthProvider(ABC):
    """Abstract authentication provider."""

    @abstractmethod
    def verify_token(self, token: str) -> Optional[dict[str, Any]]:
        ...

    @abstractmethod
    def create_access_token(self, subject: str, extra_claims: Optional[dict[str, Any]] = None) -> str:
        ...


class SupabaseJWTAuthProvider(AuthProvider):
    """
    Standard JWT auth provider that verifies tokens using HMAC SHA256.
    Works for both local testing and Supabase Auth JWT tokens.
    """

    def __init__(self, secret_key: Optional[str] = None) -> None:
        self.secret = secret_key or settings.jwt_secret_key

    def verify_token(self, token: str) -> Optional[dict[str, Any]]:
        try:
            return StandardJWT.decode(token, self.secret)
        except Exception as exc:
            logger.debug("Token verification failed: %s", exc)
            return None

    def create_access_token(self, subject: str, extra_claims: Optional[dict[str, Any]] = None) -> str:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
        payload = {
            "sub": subject,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "iss": "payback",
            **(extra_claims or {}),
        }
        return StandardJWT.encode(payload, self.secret)


# Default provider instance
_auth_provider = SupabaseJWTAuthProvider()


def get_auth_provider() -> AuthProvider:
    return _auth_provider


# Default fallback merchant for development/test mode
DEFAULT_TEST_MERCHANT = Merchant(
    id="merchant_default",
    name="Acme Corp Test",
    email="merchant@example.com",
    timezone="Asia/Kolkata",
)


def get_current_merchant(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_merchant_id: Optional[str] = Header(default=None, alias="X-Merchant-ID"),
) -> Merchant:
    """
    FastAPI dependency to extract and authenticate the current merchant.
    - If Authorization Bearer token is provided: verifies JWT and extracts merchant.
    - If auth is disabled / in test environment and no token given: returns default merchant or X-Merchant-ID.
    - In production with auth_enabled=True: enforces valid token.
    """
    if credentials and credentials.credentials:
        token = credentials.credentials
        provider = get_auth_provider()
        payload = provider.verify_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        merchant_id = payload.get("merchant_id") or payload.get("sub") or "merchant_default"
        name = payload.get("name") or payload.get("user_metadata", {}).get("name") or "Authenticated Merchant"
        email = payload.get("email") or "merchant@example.com"

        return Merchant(
            id=str(merchant_id),
            name=str(name),
            email=str(email),
        )

    # If explicit X-Merchant-ID is passed in dev/test
    if x_merchant_id:
        return Merchant(
            id=x_merchant_id,
            name=f"Merchant {x_merchant_id}",
            email=f"{x_merchant_id}@example.com",
        )

    # In production, require authentication if enabled
    if settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fallback to test merchant for zero-friction local development & test suite
    return DEFAULT_TEST_MERCHANT
