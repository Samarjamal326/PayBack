from __future__ import annotations

import json
import logging
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.api.schemas import (
    ActionRecordResponse,
    AuditRecordResponse,
    HealthResponse,
    RecoveryCaseResponse,
    StartRecoveryRequest,
    WebhookResponse,
)
from app.config import settings
from app.models.domain import Policy
from app.services.razorpay.webhook import (
    process_razorpay_webhook_event,
    verify_webhook_signature,
)
from app.services.recovery import RecoveryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["recovery"])

# Shared service instance
_service = RecoveryService()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_env=settings.app_env,
        razorpay_mode=settings.razorpay_mode,
    )


# Payment ingestion lives in app.api.v1.events — avoid duplicate route registration here.

@router.post("/events/webhook/razorpay", response_model=WebhookResponse, status_code=200)
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
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        event_data = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Malformed JSON payload: {exc}")

    result = process_razorpay_webhook_event(event_data, _service)
    return WebhookResponse(
        status="success" if result.processed else "ignored",
        message=result.message,
        event=result.event,
        case_id=result.case_id,
        is_duplicate=result.is_duplicate,
    )


@router.post("/recovery", response_model=RecoveryCaseResponse, status_code=202)
def start_recovery(payload: StartRecoveryRequest) -> RecoveryCaseResponse:
    policy = Policy(
        maximum_retries=payload.maximum_retries,
        maximum_messages=payload.maximum_messages,
        recovery_window_hours=payload.recovery_window_hours,
        high_value_threshold=payload.high_value_threshold,
        human_approval_required=payload.human_approval_required,
    )
    try:
        case = _service.run_recovery(payload.case_id, policy)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return RecoveryCaseResponse(**case.model_dump())


@router.get("/recovery/{recovery_id}", response_model=RecoveryCaseResponse)
def get_recovery_case(recovery_id: str) -> RecoveryCaseResponse:
    try:
        case = _service.get_case(recovery_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return RecoveryCaseResponse(**case.model_dump())


@router.get("/recovery/{recovery_id}/actions", response_model=list[ActionRecordResponse])
def get_recovery_actions(recovery_id: str) -> list[ActionRecordResponse]:
    try:
        records = _service.get_action_history(recovery_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return [ActionRecordResponse(**r.model_dump()) for r in records]


@router.get("/recovery/{recovery_id}/audit", response_model=list[AuditRecordResponse])
def get_recovery_audit(recovery_id: str, limit: int = 50) -> list[AuditRecordResponse]:
    try:
        # Optimized: Limit audit records for better performance
        records = _service.get_audit_history(recovery_id, limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return [AuditRecordResponse(**r.model_dump()) for r in records]
