from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.schemas import (
    ActionRecordResponse,
    AuditRecordResponse,
    MessageDeliveryResponse,
    RecoveryCaseResponse,
    StartRecoveryRequest,
)
from app.core.auth import get_current_merchant
from app.models.domain import Merchant, Policy
from app.repositories.factory import get_repository_bundle
from app.services.recovery import RecoveryService
router = APIRouter(tags=["recoveries"])
_service = RecoveryService()
_repos = get_repository_bundle()



@router.get("", response_model=list[RecoveryCaseResponse])
def list_recovery_cases(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    merchant: Merchant = Depends(get_current_merchant),
) -> list[RecoveryCaseResponse]:
    cases = _repos.cases.list_by_merchant(
        merchant_id=merchant.id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return [RecoveryCaseResponse(**c.model_dump()) for c in cases]


@router.get("/{recovery_id}", response_model=RecoveryCaseResponse)
def get_recovery_case(
    recovery_id: str,
    merchant: Merchant = Depends(get_current_merchant),
) -> RecoveryCaseResponse:
    try:
        case = _service.get_case(recovery_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    if case.merchant_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: recovery case belongs to another merchant.")

    return RecoveryCaseResponse(**case.model_dump())


@router.get("/{recovery_id}/actions", response_model=list[ActionRecordResponse])
def get_recovery_actions(
    recovery_id: str,
    merchant: Merchant = Depends(get_current_merchant),
) -> list[ActionRecordResponse]:
    case = _repos.cases.get(recovery_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recovery case '{recovery_id}' not found.")
    if case.merchant_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    records = _service.get_action_history(recovery_id)
    return [ActionRecordResponse(**r.model_dump()) for r in records]


@router.get("/{recovery_id}/timeline", response_model=list[AuditRecordResponse])
@router.get("/{recovery_id}/audit", response_model=list[AuditRecordResponse])
def get_recovery_timeline(
    recovery_id: str,
    limit: int = 50,
    merchant: Merchant = Depends(get_current_merchant),
) -> list[AuditRecordResponse]:
    case = _repos.cases.get(recovery_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recovery case '{recovery_id}' not found.")
    if case.merchant_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # Optimized: Limit timeline records for better performance
    records = _service.get_audit_history(recovery_id, limit)
    return [AuditRecordResponse(**r.model_dump()) for r in records]


@router.get("/{recovery_id}/messages", response_model=list[MessageDeliveryResponse])
def get_recovery_messages(
    recovery_id: str,
    merchant: Merchant = Depends(get_current_merchant),
) -> list[MessageDeliveryResponse]:
    case = _repos.cases.get(recovery_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recovery case '{recovery_id}' not found.")
    if case.merchant_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    records = _repos.message_deliveries.list_by_case(recovery_id)
    return [
        MessageDeliveryResponse(
            id=r.id,
            merchant_id=r.merchant_id,
            recovery_case_id=r.recovery_case_id,
            customer_id=r.customer_id,
            channel=r.channel,
            provider=r.provider.value if hasattr(r.provider, "value") else str(r.provider),
            provider_message_id=r.provider_message_id,
            status=r.status,
            content_preview=r.content_preview,
            sent_at=r.sent_at,
            delivered_at=r.delivered_at,
            failure_reason=r.failure_reason,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.post("", response_model=RecoveryCaseResponse, status_code=status.HTTP_202_ACCEPTED)
def start_recovery(
    payload: StartRecoveryRequest,
    merchant: Merchant = Depends(get_current_merchant),
) -> RecoveryCaseResponse:
    policy = Policy(
        merchant_id=merchant.id,
        maximum_retries=payload.maximum_retries,
        maximum_messages=payload.maximum_messages,
        recovery_window_hours=payload.recovery_window_hours,
        high_value_threshold=payload.high_value_threshold,
        human_approval_required=payload.human_approval_required,
    )
    try:
        case = _service.run_recovery(payload.case_id, policy)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return RecoveryCaseResponse(**case.model_dump())
