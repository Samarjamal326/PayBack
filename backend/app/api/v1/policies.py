from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import CreatePolicyRequest, PolicyResponse, UpdatePolicyRequest
from app.core.auth import get_current_merchant
from app.models.domain import Merchant, Policy
from app.repositories.factory import get_repository_bundle

router = APIRouter(prefix="/policies", tags=["policies"])
_repos = get_repository_bundle()


@router.get("", response_model=list[PolicyResponse])
def list_policies(merchant: Merchant = Depends(get_current_merchant)) -> list[PolicyResponse]:
    policies = _repos.policies.list_by_merchant(merchant_id=merchant.id)
    return [PolicyResponse(**p.model_dump()) for p in policies]


@router.get("/active", response_model=PolicyResponse)
def get_active_policy(merchant: Merchant = Depends(get_current_merchant)) -> PolicyResponse:
    policy = _repos.policies.get_active(merchant_id=merchant.id)
    return PolicyResponse(**policy.model_dump())


@router.get("/{policy_id}", response_model=PolicyResponse)
def get_policy(
    policy_id: str,
    merchant: Merchant = Depends(get_current_merchant),
) -> PolicyResponse:
    policy = _repos.policies.get(policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Policy '{policy_id}' not found.")
    if policy.merchant_id and policy.merchant_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    return PolicyResponse(**policy.model_dump())


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
def create_policy(
    payload: CreatePolicyRequest,
    merchant: Merchant = Depends(get_current_merchant),
) -> PolicyResponse:
    policy = Policy(
        merchant_id=merchant.id,
        name=payload.name,
        is_active=payload.is_active,
        maximum_retries=payload.maximum_retries,
        maximum_messages=payload.maximum_messages,
        recovery_window_hours=payload.recovery_window_hours,
        high_value_threshold=payload.high_value_threshold,
        human_approval_required=payload.human_approval_required,
        action_costs=payload.action_costs or Policy().action_costs,
    )
    saved = _repos.policies.save(policy)
    return PolicyResponse(**saved.model_dump())


@router.put("/{policy_id}", response_model=PolicyResponse)
def update_policy(
    policy_id: str,
    payload: UpdatePolicyRequest,
    merchant: Merchant = Depends(get_current_merchant),
) -> PolicyResponse:
    policy = _repos.policies.get(policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Policy '{policy_id}' not found.")
    if policy.merchant_id and policy.merchant_id != merchant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    update_dict = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    updated = policy.model_copy(update=update_dict)
    saved = _repos.policies.save(updated)
    return PolicyResponse(**saved.model_dump())
