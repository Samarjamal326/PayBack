from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.schemas import (
    CustomerDetailResponse,
    CustomerMetrics,
    CustomerResponse,
    RecoveryCaseResponse,
    TransactionResponse,
)
from app.core.auth import get_current_merchant
from app.models.domain import Merchant, RecoveryOutcome, RecoveryStatus, TransactionStatus
from app.repositories.factory import get_repository_bundle
router = APIRouter(prefix="/customers", tags=["customers"])
_repos = get_repository_bundle()


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    merchant: Merchant = Depends(get_current_merchant),
) -> list[CustomerResponse]:
    customers = _repos.customers.list_by_merchant(merchant_id=merchant.id, limit=limit, offset=offset)
    if not customers:
        return []

    # Efficient batch aggregation for the returned customers
    customer_ids = {c.id for c in customers}
    
    # Pre-fetch recent transactions and cases for this merchant in single queries
    all_txs = _repos.transactions.list_by_merchant(merchant_id=merchant.id, limit=1000)
    all_cases = _repos.cases.list_by_merchant(merchant_id=merchant.id, limit=1000)

    paid_map: dict[str, float] = {}
    for t in all_txs:
        if t.customer_id in customer_ids and t.status == TransactionStatus.SUCCESS:
            paid_map[t.customer_id] = paid_map.get(t.customer_id, 0.0) + t.amount

    open_cases_map: dict[str, int] = {}
    for c in all_cases:
        if c.customer_id in customer_ids and c.status not in (RecoveryStatus.RECOVERED, RecoveryStatus.STOPPED, RecoveryStatus.ESCALATED):
            open_cases_map[c.customer_id] = open_cases_map.get(c.customer_id, 0) + 1

    return [
        CustomerResponse(
            **c.model_dump(),
            total_paid_amount=round(paid_map.get(c.id, 0.0), 2),
            open_recovery_cases=open_cases_map.get(c.id, 0),
        )
        for c in customers
    ]


@router.get("/{customer_id}", response_model=CustomerDetailResponse)
def get_customer_detail(
    customer_id: str,
    merchant: Merchant = Depends(get_current_merchant),
) -> CustomerDetailResponse:
    customer = _repos.customers.get(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found.",
        )

    if customer.merchant_id != merchant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: customer belongs to another merchant.",
        )

    transactions = _repos.transactions.list_by_customer(customer_id)
    cases = _repos.cases.list_by_customer(customer_id)

    total_payments = len(transactions)
    successful_payments = sum(1 for t in transactions if t.status == TransactionStatus.SUCCESS)
    failed_payments = sum(1 for t in transactions if t.status == TransactionStatus.FAILED)
    total_paid_amount = sum(t.amount for t in transactions if t.status == TransactionStatus.SUCCESS)
    failed_amount = sum(t.amount for t in transactions if t.status == TransactionStatus.FAILED)

    recovery_cases_count = len(cases)
    successful_recoveries_count = sum(1 for c in cases if c.outcome == RecoveryOutcome.RECOVERED or c.status == RecoveryStatus.RECOVERED)
    recovered_revenue = sum(c.amount_recovered for c in cases)
    recovery_rate = (recovered_revenue / failed_amount) if failed_amount > 0 else 0.0
    hist_success_rate = (successful_payments / total_payments) if total_payments > 0 else 0.0

    now_dt = datetime.now(timezone.utc)
    cust_created = customer.created_at if customer.created_at.tzinfo else customer.created_at.replace(tzinfo=timezone.utc)
    tenure_days = max(1, (now_dt - cust_created).days)

    metrics = CustomerMetrics(
        total_payments=total_payments,
        successful_payments=successful_payments,
        failed_payments=failed_payments,
        total_paid_amount=round(total_paid_amount, 2),
        failed_amount=round(failed_amount, 2),
        recovery_cases_count=recovery_cases_count,
        successful_recoveries_count=successful_recoveries_count,
        recovered_revenue=round(recovered_revenue, 2),
        recovery_rate=round(recovery_rate, 4),
        historical_success_rate=round(hist_success_rate, 4),
        customer_tenure_days=tenure_days,
    )

    return CustomerDetailResponse(
        customer=CustomerResponse(**customer.model_dump()),
        metrics=metrics,
        recent_transactions=[TransactionResponse(**t.model_dump()) for t in transactions[:10]],
        recent_recoveries=[RecoveryCaseResponse(**c.model_dump()) for c in cases[:10]],
    )


@router.get("/{customer_id}/payments", response_model=list[TransactionResponse])
def get_customer_payments(
    customer_id: str,
    merchant: Merchant = Depends(get_current_merchant),
) -> list[TransactionResponse]:
    customer = _repos.customers.get(customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer '{customer_id}' not found.")
    if customer.merchant_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    transactions = _repos.transactions.list_by_customer(customer_id)
    return [TransactionResponse(**t.model_dump()) for t in transactions]


@router.get("/{customer_id}/recoveries", response_model=list[RecoveryCaseResponse])
def get_customer_recoveries(
    customer_id: str,
    merchant: Merchant = Depends(get_current_merchant),
) -> list[RecoveryCaseResponse]:
    customer = _repos.customers.get(customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Customer '{customer_id}' not found.")
    if customer.merchant_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    cases = _repos.cases.list_by_customer(customer_id)
    return [RecoveryCaseResponse(**c.model_dump()) for c in cases]
