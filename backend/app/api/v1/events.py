from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import PaymentEventRequest, RecoveryCaseResponse
from app.core.auth import get_current_merchant
from app.models.domain import Customer, Merchant, Transaction
from app.services.recovery import RecoveryService

router = APIRouter(prefix="/events", tags=["events"])
_service = RecoveryService()


@router.post("/payment", response_model=RecoveryCaseResponse, status_code=status.HTTP_201_CREATED)
def ingest_payment_event(
    payload: PaymentEventRequest,
    merchant: Merchant = Depends(get_current_merchant),
) -> RecoveryCaseResponse:
    customer = Customer(
        merchant_id=merchant.id,
        external_id=payload.customer_external_id,
        name=payload.customer_name,
        email=payload.customer_email,
        phone=payload.customer_phone,
    )
    transaction = Transaction(
        merchant_id=merchant.id,
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
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return RecoveryCaseResponse(**case.model_dump())
