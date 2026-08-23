from __future__ import annotations

import logging
from typing import Optional
import httpx

from app.models.domain import RecoveryOutcome
from app.services.actions.interfaces import ActionResult, PaymentActionProvider

logger = logging.getLogger(__name__)


class LiveKeyForbiddenError(ValueError):
    """Raised whenever a live Razorpay key is detected to prevent accidental live charges."""
    pass


class RazorpayPaymentProvider(PaymentActionProvider):
    """
    Razorpay integration in TEST MODE ONLY.
    Strictly forbids live credentials to ensure zero cost.
    """

    BASE_URL = "https://api.razorpay.com/v1"

    def __init__(
        self,
        key_id: str,
        key_secret: str,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.key_id = key_id.strip() if key_id else ""
        self.key_secret = key_secret.strip() if key_secret else ""
        self._http_client = http_client

        # Safety Guard: Live keys are strictly prohibited
        if self.key_id.startswith("rzp_live_"):
            raise LiveKeyForbiddenError(
                "LIVE Razorpay key detected! Live transactions are forbidden. "
                "Only Test Mode keys beginning with 'rzp_test_' are permitted."
            )

    def _get_client(self) -> httpx.Client:
        if self._http_client is not None:
            return self._http_client
        return httpx.Client(
            auth=(self.key_id, self.key_secret),
            timeout=10.0,
        )

    def create_payment_link(
        self,
        transaction_id: str,
        amount: float,
        customer_email: str,
        customer_phone: Optional[str] = None,
        customer_name: Optional[str] = None,
    ) -> ActionResult:
        """
        Creates a Razorpay Test Mode Payment Link for the exact amount at risk.
        Converts INR amount to paise (1 INR = 100 paise).
        """
        if not self.key_id or not self.key_secret:
            raise RuntimeError("Razorpay Test Mode credentials are not configured.")

        if not self.key_id.startswith("rzp_test_"):
            raise LiveKeyForbiddenError(
                f"Invalid key prefix '{self.key_id[:8]}...'. Expected 'rzp_test_' for Test Mode."
            )

        amount_in_paise = int(round(amount * 100))
        payload = {
            "amount": amount_in_paise,
            "currency": "INR",
            "accept_partial": False,
            "description": f"PayBack recovery for transaction {transaction_id}",
            "customer": {
                "name": customer_name or "Customer",
                "email": customer_email or "",
                "contact": customer_phone or "",
            },
            "notify": {
                "sms": False,
                "email": False,
            },
            "reminder_enable": False,
            "notes": {
                "transaction_id": transaction_id,
                "recovery_source": "payback_ai_recovery",
            },
        }

        try:
            client = self._get_client()
            resp = client.post(f"{self.BASE_URL}/payment_links", json=payload)
            resp.raise_for_status()
            data = resp.json()
            link_url = data.get("short_url") or data.get("url") or f"https://rzp.io/i/{data.get('id')}"
            link_id = data.get("id", "unknown_link_id")

            return ActionResult(
                outcome=RecoveryOutcome.FAILED,  # Status remains pending until customer pays via webhook
                detail=f"Created Razorpay Test Payment Link {link_id}",
                external_ref=link_url,
            )
        except httpx.HTTPStatusError as exc:
            logger.error("Razorpay API error: %s - %s", exc.response.status_code, exc.response.text)
            return ActionResult(
                outcome=RecoveryOutcome.FAILED,
                detail=f"Razorpay API error ({exc.response.status_code}): {exc.response.text}",
            )
        except Exception as exc:
            logger.error("Razorpay request failed: %s", exc)
            return ActionResult(
                outcome=RecoveryOutcome.FAILED,
                detail=f"Razorpay request failed: {str(exc)}",
            )

    def retry_payment(self, transaction_id: str, amount: float) -> ActionResult:
        """Simulated payment retry in Test Mode."""
        if not self.key_id or not self.key_secret:
            raise RuntimeError("Razorpay Test Mode credentials are not configured.")

        return ActionResult(
            outcome=RecoveryOutcome.FAILED,
            detail=f"[test_mode] payment retry simulated for tx={transaction_id} amount={amount}",
        )
