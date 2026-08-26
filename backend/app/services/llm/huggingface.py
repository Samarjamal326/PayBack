from __future__ import annotations

import logging
from typing import Optional
import httpx

from app.services.llm.interface import MessageContext, MessageGenerator
from app.services.llm.mock import MockMessageGenerator
from app.services.llm.validator import MessageValidator

logger = logging.getLogger(__name__)


class HuggingFaceMessageGenerator(MessageGenerator):
    """
    Message generator powered by Hugging Face free-tier / open model inference.
    Generates customer-facing messages from structured data only.
    The LLM never makes business or financial decisions.
    Falls back cleanly to MockMessageGenerator if no API key is provided.
    Outputs are validated by MessageValidator before delivery.
    """

    HF_API_BASE = "https://api-inference.huggingface.co/models"

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "mistralai/Mistral-7B-Instruct-v0.2",
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.model_name = model_name.strip()
        self._http_client = http_client
        self._fallback_generator = MockMessageGenerator()

    def _get_client(self) -> httpx.Client:
        if self._http_client is not None:
            return self._http_client
        return httpx.Client(timeout=10.0)

    def _call_hf(self, prompt: str) -> Optional[str]:
        if not self.api_key:
            return None

        url = f"{self.HF_API_BASE}/{self.model_name}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 120,
                "temperature": 0.3,
                "return_full_text": False,
            },
        }

        try:
            client = self._get_client()
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and data and "generated_text" in data[0]:
                return data[0]["generated_text"].strip()
            return None
        except Exception as exc:
            logger.warning("HuggingFace message generation failed, using template fallback: %s", exc)
            return None

    def whatsapp_message(self, ctx: MessageContext) -> str:
        prompt = (
            f"You are a recovery assistant for a merchant. Write a concise, {ctx.merchant_tone} "
            f"WhatsApp message to customer '{ctx.customer_name}' whose payment of "
            f"{ctx.currency} {ctx.amount:,.2f} failed. "
            f"Include payment link: {ctx.payment_link or 'N/A'}. Include opt-out reply instructions."
        )

        generated = self._call_hf(prompt)
        return MessageValidator.validate_whatsapp(generated, ctx)

    def email_body(self, ctx: MessageContext) -> str:
        prompt = (
            f"You are a recovery assistant for a merchant. Write a brief, professional HTML email "
            f"body to '{ctx.customer_name}' regarding their failed payment of {ctx.currency} {ctx.amount:,.2f}. "
            f"Include a link to complete payment: {ctx.payment_link or 'N/A'}."
        )

        generated = self._call_hf(prompt)
        return MessageValidator.validate_email(generated, ctx)

