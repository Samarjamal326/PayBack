from __future__ import annotations

import logging
from typing import Optional
import httpx

from app.services.llm.interface import MessageContext, MessageGenerator
from app.services.llm.mock import MockMessageGenerator
from app.services.llm.validator import MessageValidator

logger = logging.getLogger(__name__)


class OllamaMessageGenerator(MessageGenerator):
    """
    Message generator powered by local Ollama instance (defaulting to Qwen 2.5 3B).
    Strictly local inference with zero external network or monetary cost.
    The LLM never makes business or financial decisions.
    Falls back cleanly to MockMessageGenerator if Ollama is unreachable.
    Outputs are validated by MessageValidator before delivery.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_name: str = "qwen2.5:3b",
        http_client: Optional[httpx.Client] = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name.strip()
        self._http_client = http_client
        self.timeout = timeout
        self._fallback_generator = MockMessageGenerator()

    def _get_client(self) -> httpx.Client:
        if self._http_client is not None:
            return self._http_client
        return httpx.Client(timeout=self.timeout)

    def _call_ollama(self, prompt: str) -> Optional[str]:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
            },
        }

        try:
            client = self._get_client()
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                raw_text = resp.json().get("response", "").strip()
                return raw_text if raw_text else None
            logger.warning("Ollama returned status code %s: %s", resp.status_code, resp.text)
            return None
        except Exception as exc:
            logger.warning("Ollama local generation failed (%s). Using fallback template.", exc)
            return None

    def whatsapp_message(self, ctx: MessageContext) -> str:
        link_instruction = (
            f"Include this exact payment link: {ctx.payment_link}"
            if ctx.payment_link
            else "Do not include any payment link."
        )
        prompt = (
            "You are a helpful customer billing assistant for an Indian e-commerce merchant.\n"
            f"Write a concise, {ctx.merchant_tone}, polite, and reassuring 2-sentence payment recovery WhatsApp notification message.\n"
            "Rules:\n"
            "- Do not invent order details, shipping status, discounts, or additional fees.\n"
            "- Keep the tone professional, friendly, and non-threatening.\n"
            f"- Customer Name: {ctx.customer_name}\n"
            f"- Transaction Amount: {ctx.currency} {ctx.amount:,.2f}\n"
            f"- Failure Context: {ctx.failure_reason or 'temporary connection error'}\n"
            f"- {link_instruction}\n"
            "- Include: 'Reply STOP to opt out.'\n"
            "Return ONLY the exact text message to be sent to the customer without preamble or quotes."
        )

        generated = self._call_ollama(prompt)
        return MessageValidator.validate_whatsapp(generated, ctx)

    def email_body(self, ctx: MessageContext) -> str:
        link_instruction = (
            f"Include this exact payment link: {ctx.payment_link}"
            if ctx.payment_link
            else "Do not include any payment link."
        )
        prompt = (
            "You are a helpful customer billing assistant for an Indian e-commerce merchant.\n"
            f"Write a brief, professional HTML email body regarding a failed payment.\n"
            "Rules:\n"
            "- Do not invent order details, shipping status, discounts, or customer support contact placeholders.\n"
            f"- Customer Name: {ctx.customer_name}\n"
            f"- Transaction Amount: {ctx.currency} {ctx.amount:,.2f}\n"
            f"- {link_instruction}\n"
            "Return ONLY the clean HTML fragment starting with <p> and ending with </p> without markdown code fences."
        )

        generated = self._call_ollama(prompt)
        return MessageValidator.validate_email(generated, ctx)

