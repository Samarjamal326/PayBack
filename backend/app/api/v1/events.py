from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import PaymentEventRequest, RecoveryCaseResponse
from app.core.auth import get_current_merchant
from app.models.domain import Merchant
from app.repositories.factory import get_repository_bundle
from app.services.payment_ingestion import build_transaction_for_payment, resolve_customer_for_payment
from app.services.recovery import RecoveryService

router = APIRouter(prefix="/events", tags=["events"])
_service = RecoveryService()
_repos = get_repository_bundle()


@router.post("/payment", response_model=RecoveryCaseResponse, status_code=status.HTTP_201_CREATED)
def ingest_payment_event(
    payload: PaymentEventRequest,
    merchant: Merchant = Depends(get_current_merchant),
) -> RecoveryCaseResponse:
    customer = resolve_customer_for_payment(payload, merchant, _repos.customers)
    transaction = build_transaction_for_payment(payload, merchant, customer)
    try:
        case = _service.ingest_payment_event(transaction, customer)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return RecoveryCaseResponse(**case.model_dump())
