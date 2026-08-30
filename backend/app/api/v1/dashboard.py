from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


def _average_recovery_time_hours(cases: list) -> float:
    """Mean hours from case creation to last update for recovered cases."""
    durations: list[float] = []
    for case in cases:
        recovered = case.outcome == RecoveryOutcome.RECOVERED or case.status == RecoveryStatus.RECOVERED
        if not recovered:
            continue
        created = case.created_at
        updated = case.updated_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        hours = (updated - created).total_seconds() / 3600.0
        if hours >= 0:
            durations.append(hours)
    if not durations:
        return 0.0
    return round(sum(durations) / len(durations), 2)


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(merchant: Merchant = Depends(get_current_merchant)) -> DashboardSummaryResponse:
    # Optimized: Reduce limit from 1000 to 100 for better performance
    cases = _repos.cases.list_by_merchant(merchant_id=merchant.id, limit=100)

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
        average_recovery_time_hours=_average_recovery_time_hours(cases),
    )


@router.get("/trends", response_model=DashboardTrendsResponse)
def get_dashboard_trends(merchant: Merchant = Depends(get_current_merchant)) -> DashboardTrendsResponse:
    # Optimized: Reduce limit from 1000 to 100 for better performance
    # Filter to last 30 days for better chart density
    thirty_days_ago = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
    all_cases = _repos.cases.list_by_merchant(merchant_id=merchant.id, limit=100)
    
    # Filter cases from last 30 days
    cases = [c for c in all_cases if c.created_at >= thirty_days_ago]

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
    # Optimized: Reduce limit from 1000 to 100 for better performance
    cases = _repos.cases.list_by_merchant(merchant_id=merchant.id, limit=100)

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
        # Optimized: Reduce transaction limit from 200 to 50 for better performance
        transactions = _repos.transactions.list_by_merchant(merchant_id=merchant.id, limit=50)
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
