from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    ActionRecordResponse,
    PaymentEventRequest,
    RecoveryCaseResponse,
    StartRecoveryRequest,
)
from app.models.domain import Customer, Policy, Transaction
from app.services.recovery import RecoveryService

router = APIRouter(prefix="/api/v1", tags=["recovery"])

# Phase 1: single shared service instance (no DI container yet)
_service = RecoveryService()


@router.post("/events/payment", response_model=RecoveryCaseResponse, status_code=201)
def ingest_payment_event(payload: PaymentEventRequest) -> RecoveryCaseResponse:
    customer = Customer(
        external_id=payload.customer_external_id,
        name=payload.customer_name,
        email=payload.customer_email,
        phone=payload.customer_phone,
    )
    transaction = Transaction(
        customer_id=customer.id,
        amount=payload.transaction_amount,
        currency=payload.transaction_currency,
        payment_method=payload.payment_method,
        status=payload.transaction_status,
        failure_reason=payload.failure_reason,
    )
    try:
        case = _service.ingest_payment_event(transaction, customer)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return RecoveryCaseResponse(**case.model_dump())


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
