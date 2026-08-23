from __future__ import annotations

from typing import Annotated, TypedDict

from app.models.domain import (
    ActionRecord,
    Customer,
    Policy,
    RecoveryCase,
    Transaction,
)


class RecoveryState(TypedDict):
    """
    The single state object passed through the LangGraph workflow.
    All fields are immutable snapshots per node invocation.
    """
    transaction: Transaction
    customer: Customer
    case: RecoveryCase
    policy: Policy
    action_history: Annotated[list[ActionRecord], "append"]
    error: str | None
