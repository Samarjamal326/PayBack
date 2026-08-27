from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends

from app.api.schemas import (
    ActionBreakdownItem,
    DashboardBreakdownResponse,
    DashboardSummaryResponse,
    DashboardTrendsResponse,
    TrendDataPoint,
)
from app.core.auth import get_current_merchant
from app.models.domain import Merchant, RecoveryOutcome, RecoveryStatus
from app.repositories.factory import get_repository_bundle

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
_repos = get_repository_bundle()


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(merchant: Merchant = Depends(get_current_merchant)) -> DashboardSummaryResponse:
    cases = _repos.cases.list_by_merchant(merchant_id=merchant.id, limit=1000)

    total_cases = len(cases)
    total_at_risk = sum(c.amount_at_risk for c in cases)
    total_recovered = sum(c.amount_recovered for c in cases)
    successful_count = sum(1 for c in cases if c.outcome == RecoveryOutcome.RECOVERED or c.status == RecoveryStatus.RECOVERED)
    escalated_count = sum(1 for c in cases if c.status == RecoveryStatus.ESCALATED)
    stopped_count = sum(1 for c in cases if c.status == RecoveryStatus.STOPPED)
    active_count = sum(1 for c in cases if c.status not in (RecoveryStatus.RECOVERED, RecoveryStatus.STOPPED, RecoveryStatus.ESCALATED))

    recovery_rate = (total_recovered / total_at_risk) if total_at_risk > 0 else 0.0

    return DashboardSummaryResponse(
        total_revenue_at_risk=round(total_at_risk, 2),
        total_recovered_revenue=round(total_recovered, 2),
        overall_recovery_rate=round(recovery_rate, 4),
        active_recovery_cases=active_count,
        total_recovery_cases=total_cases,
        successful_recoveries=successful_count,
        escalated_cases=escalated_count,
        stopped_cases=stopped_count,
        average_recovery_time_hours=2.4,
    )


@router.get("/trends", response_model=DashboardTrendsResponse)
def get_dashboard_trends(merchant: Merchant = Depends(get_current_merchant)) -> DashboardTrendsResponse:
    cases = _repos.cases.list_by_merchant(merchant_id=merchant.id, limit=1000)

    by_date: dict[str, dict] = {}
    for c in cases:
        date_str = c.created_at.strftime("%Y-%m-%d")
        bucket = by_date.setdefault(date_str, {"at_risk": 0.0, "recovered": 0.0, "rec_cnt": 0, "failed_cnt": 0})
        bucket["at_risk"] += c.amount_at_risk
        bucket["recovered"] += c.amount_recovered
        if c.outcome == RecoveryOutcome.RECOVERED or c.status == RecoveryStatus.RECOVERED:
            bucket["rec_cnt"] += 1
        elif c.status in (RecoveryStatus.STOPPED, RecoveryStatus.ESCALATED):
            bucket["failed_cnt"] += 1

    trends = [
        TrendDataPoint(
            date=d,
            at_risk_amount=round(v["at_risk"], 2),
            recovered_amount=round(v["recovered"], 2),
            recovered_count=v["rec_cnt"],
            failed_count=v["failed_cnt"],
        )
        for d, v in sorted(by_date.items())
    ]

    return DashboardTrendsResponse(period="30d", trends=trends)


@router.get("/breakdown", response_model=DashboardBreakdownResponse)
def get_dashboard_breakdown(merchant: Merchant = Depends(get_current_merchant)) -> DashboardBreakdownResponse:
    cases = _repos.cases.list_by_merchant(merchant_id=merchant.id, limit=1000)

    by_status: dict[str, int] = {}
    by_action_map: dict[str, dict] = {}

    for c in cases:
        st = c.status.value
        by_status[st] = by_status.get(st, 0) + 1

        if c.selected_action:
            act = c.selected_action.value
            bucket = by_action_map.setdefault(act, {"count": 0, "recovered": 0.0, "success": 0})
            bucket["count"] += 1
            bucket["recovered"] += c.amount_recovered
            if c.outcome == RecoveryOutcome.RECOVERED or c.status == RecoveryStatus.RECOVERED:
                bucket["success"] += 1

    by_action = [
        ActionBreakdownItem(
            action=k,
            count=v["count"],
            recovered_amount=round(v["recovered"], 2),
            success_rate=round(v["success"] / v["count"], 4) if v["count"] > 0 else 0.0,
        )
        for k, v in by_action_map.items()
    ]

    by_payment_method: dict[str, int] = {}
    try:
        transactions = _repos.transactions.list_by_merchant(merchant_id=merchant.id, limit=200)
        for t in transactions:
            pm = t.payment_method.value
            by_payment_method[pm] = by_payment_method.get(pm, 0) + 1
    except Exception:
        pass

    return DashboardBreakdownResponse(
        by_action=by_action,
        by_status=by_status,
        by_payment_method=by_payment_method,
    )
