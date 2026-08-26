"""
Deterministic Message Validator and Sanitizer for PayBack LLM outputs.

Enforces strict financial accuracy, unsupported claim removal, placeholder sanitization,
and mandatory compliance text (e.g., 'Reply STOP to opt out.') on all generated messages
across all LLM providers (Ollama, HuggingFace, Mock, etc.).
"""
from __future__ import annotations

import re
from typing import Optional

from app.services.llm.interface import MessageContext


class MessageValidator:
    """
    Validates and sanitizes raw LLM messages before they can reach customer delivery channels.
    """

    # Unresolved template placeholders that must never reach customers
    PLACEHOLDER_PATTERNS = [
        re.compile(r"\[.*?\]", re.DOTALL),          # e.g. [Customer Support Email], [Insert Link]
        re.compile(r"\{\{.*?\}\}", re.DOTALL),      # e.g. {{placeholder}}
        re.compile(r"<placeholder.*?>", re.IGNORECASE),
        re.compile(r"\bTODO\b", re.IGNORECASE),
        re.compile(r"\bTBD\b", re.IGNORECASE),
    ]

    # Unsupported claims (invented business facts not present in MessageContext)
    UNSUPPORTED_CLAIM_PATTERNS = [
        re.compile(r"\brecent order\b", re.IGNORECASE),
        re.compile(r"\border number\b", re.IGNORECASE),
        re.compile(r"\border details\b", re.IGNORECASE),
        re.compile(r"\bdelivery status\b", re.IGNORECASE),
        re.compile(r"\bshipping status\b", re.IGNORECASE),
        re.compile(r"\bshipped\b", re.IGNORECASE),
        re.compile(r"\brefund status\b", re.IGNORECASE),
        re.compile(r"\bdiscount\b", re.IGNORECASE),
        re.compile(r"\bcoupon\b", re.IGNORECASE),
        re.compile(r"\bpromo code\b", re.IGNORECASE),
        re.compile(r"\baccount balance\b", re.IGNORECASE),
        re.compile(r"\bAlibaba Cloud\b", re.IGNORECASE),
    ]

    OPT_OUT_WHATSAPP = "Reply STOP to opt out."

    @classmethod
    def get_fallback_whatsapp(cls, ctx: MessageContext) -> str:
        """Deterministic, safe WhatsApp template using only context data."""
        link_part = f"\n\nComplete your payment here: {ctx.payment_link}" if ctx.payment_link else ""
        return (
            f"Hi {ctx.customer_name}, your payment of "
            f"{ctx.currency} {ctx.amount:,.2f} could not be processed."
            f"{link_part}\n\n{cls.OPT_OUT_WHATSAPP}"
        )

    @classmethod
    def get_fallback_email(cls, ctx: MessageContext) -> str:
        """Deterministic, safe HTML email template using only context data."""
        link_part = f"\n\n<p><a href='{ctx.payment_link}'>Click here to complete payment</a></p>" if ctx.payment_link else ""
        return (
            f"<p>Dear {ctx.customer_name},</p>\n"
            f"<p>We were unable to process your payment of {ctx.currency} {ctx.amount:,.2f}.</p>"
            f"{link_part}\n"
            f"<p>If you need assistance, please reply to this email.</p>"
        )

    @classmethod
    def validate_whatsapp(cls, raw_text: Optional[str], ctx: MessageContext) -> str:
        """
        Validates and sanitizes a WhatsApp message string.
        Falls back to a safe deterministic template if validation fails.
        """
        if not raw_text or not isinstance(raw_text, str) or not raw_text.strip():
            return cls.get_fallback_whatsapp(ctx)

        text = raw_text.strip()

        # 1. Reject placeholders
        for pattern in cls.PLACEHOLDER_PATTERNS:
            if pattern.search(text):
                return cls.get_fallback_whatsapp(ctx)

        # 2. Reject unsupported claims
        for pattern in cls.UNSUPPORTED_CLAIM_PATTERNS:
            if pattern.search(text):
                return cls.get_fallback_whatsapp(ctx)

        # 3. Verify Payment Link integrity
        if ctx.payment_link:
            # Must contain the exact payment link
            if ctx.payment_link not in text:
                return cls.get_fallback_whatsapp(ctx)
            # Must not invent any OTHER http/https link
            all_links = re.findall(r"https?://[^\s]+", text)
            for link in all_links:
                # Strip trailing punctuation if present
                clean_link = link.rstrip(".,;:)")
                if clean_link != ctx.payment_link and link != ctx.payment_link:
                    return cls.get_fallback_whatsapp(ctx)
        else:
            # If no link in context, message must not contain any URLs
            if re.search(r"https?://", text):
                return cls.get_fallback_whatsapp(ctx)

        # 4. Mandatory Compliance: Ensure Opt-Out text
        if cls.OPT_OUT_WHATSAPP.lower() not in text.lower():
            text = f"{text.rstrip()}\n\n{cls.OPT_OUT_WHATSAPP}"

        return text

    @classmethod
    def validate_email(cls, raw_html: Optional[str], ctx: MessageContext) -> str:
        """
        Validates and sanitizes an HTML email body.
        Falls back to a safe deterministic HTML template if validation fails.
        """
        if not raw_html or not isinstance(raw_html, str) or not raw_html.strip():
            return cls.get_fallback_email(ctx)

        html = raw_html.strip()

        # 1. Reject placeholders
        for pattern in cls.PLACEHOLDER_PATTERNS:
            if pattern.search(html):
                return cls.get_fallback_email(ctx)

        # 2. Reject unsupported claims
        for pattern in cls.UNSUPPORTED_CLAIM_PATTERNS:
            if pattern.search(html):
                return cls.get_fallback_email(ctx)

        # 3. Verify Payment Link integrity
        if ctx.payment_link:
            if ctx.payment_link not in html:
                return cls.get_fallback_email(ctx)
            all_links = re.findall(r"https?://[^\s\"'>]+", html)
            for link in all_links:
                if link != ctx.payment_link:
                    return cls.get_fallback_email(ctx)
        else:
            if re.search(r"https?://", html):
                return cls.get_fallback_email(ctx)

        # 4. Ensure basic HTML tag structure
        if "<p>" not in html or "</p>" not in html:
            # Wrap in paragraph if bare text returned
            html = f"<p>{html}</p>"

        return html
