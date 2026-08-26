from __future__ import annotations

import json
import logging
from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.schemas import WebhookResponse
from app.config import settings
from app.services.razorpay.webhook import (
    process_razorpay_webhook_event,
    verify_webhook_signature,
)
from app.services.recovery import RecoveryService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["events"])
_service = RecoveryService()


@router.post("/webhook/razorpay", response_model=WebhookResponse, status_code=status.HTTP_200_OK)
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(default="", alias="X-Razorpay-Signature"),
) -> WebhookResponse:
    raw_body = await request.body()

    # Verify signature if secret is configured
    if settings.razorpay_webhook_secret:
        if not x_razorpay_signature or not verify_webhook_signature(
            raw_body=raw_body,
            signature=x_razorpay_signature,
            secret=settings.razorpay_webhook_secret,
        ):
            logger.warning("Razorpay webhook signature verification failed.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")

    try:
        event_data = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Malformed JSON payload: {exc}")

    result = process_razorpay_webhook_event(event_data, _service)
    return WebhookResponse(
        status="success" if result.processed else "ignored",
        message=result.message,
        event=result.event,
        case_id=result.case_id,
        is_duplicate=result.is_duplicate,
    )
