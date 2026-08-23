from __future__ import annotations

from datetime import datetime, timezone

from app.agent.state import RecoveryState
from app.core.decision import evaluate
from app.core.state_machine import assert_transition
from app.models.domain import (
    RecoveryDecision,
    RecoveryStatus,
)
from app.services.actions.executor import ActionExecutor


def _now() -> datetime:
    return datetime.now(timezone.utc)


def node_analyze(state: RecoveryState) -> dict:
    assert_transition(state["case"].status, RecoveryStatus.ANALYZING)
    case = state["case"].model_copy(
        update={"status": RecoveryStatus.ANALYZING, "updated_at": _now()}
    )
    return {"case": case}


def node_check_eligibility(state: RecoveryState) -> dict:
    assert_transition(state["case"].status, RecoveryStatus.ELIGIBILITY_CHECK)
    case = state["case"].model_copy(
        update={"status": RecoveryStatus.ELIGIBILITY_CHECK, "updated_at": _now()}
    )
    return {"case": case}


def node_decide(state: RecoveryState) -> dict:
    assert_transition(state["case"].status, RecoveryStatus.DECISION)
    result = evaluate(
        case=state["case"],
        transaction=state["transaction"],
        customer=state["customer"],
        policy=state["policy"],
    )
    case = state["case"].model_copy(
        update={
            "status": RecoveryStatus.DECISION,
            "decision": result.decision,
            "selected_action": result.action,
            "recovery_probability": result.recovery_probability,
            "stop_reason": result.stop_reason,
            "escalate_reason": result.escalate_reason,
            "updated_at": _now(),
        }
    )
    return {"case": case}


def node_execute_action(state: RecoveryState, executor: ActionExecutor) -> dict:
    case = state["case"]
    assert_transition(case.status, RecoveryStatus.ACTION_PENDING)

    case = case.model_copy(update={"status": RecoveryStatus.ACTION_PENDING, "updated_at": _now()})
    record = executor.execute(
        action=case.selected_action,
        case=case,
        transaction=state["transaction"],
        customer=state["customer"],
    )
    case = case.model_copy(
        update={
            "status": RecoveryStatus.ACTION_EXECUTED,
            "retry_count": case.retry_count + 1,
            "message_count": case.message_count + 1,
            "updated_at": _now(),
        }
    )
    return {"case": case, "action_history": [record]}


def node_monitor(state: RecoveryState) -> dict:
    assert_transition(state["case"].status, RecoveryStatus.MONITORING)
    case = state["case"].model_copy(
        update={"status": RecoveryStatus.MONITORING, "updated_at": _now()}
    )
    return {"case": case}


def node_stop(state: RecoveryState) -> dict:
    current = state["case"].status
    if current != RecoveryStatus.STOPPED:
        assert_transition(current, RecoveryStatus.STOPPED)
    case = state["case"].model_copy(
        update={"status": RecoveryStatus.STOPPED, "updated_at": _now()}
    )
    return {"case": case}


def node_escalate(state: RecoveryState) -> dict:
    current = state["case"].status
    if current != RecoveryStatus.ESCALATED:
        assert_transition(current, RecoveryStatus.ESCALATED)
    case = state["case"].model_copy(
        update={"status": RecoveryStatus.ESCALATED, "updated_at": _now()}
    )
    return {"case": case}


# ---------------------------------------------------------------------------
# Routing functions — return node names, never modify state
# ---------------------------------------------------------------------------

def route_eligibility(state: RecoveryState) -> str:
    # Always proceed to decide. The decide node runs the full decision engine
    # which handles opt-out, window expiry, retries, and all stop/escalate conditions.
    # This ensures decision, stop_reason, and escalate_reason are always populated.
    return "decide"


def route_decision(state: RecoveryState) -> str:
    decision = state["case"].decision
    if decision == RecoveryDecision.RECOVER:
        return "execute_action"
    if decision == RecoveryDecision.ESCALATE:
        return "escalate"
    return "stop"


def route_monitor(state: RecoveryState) -> str:
    """
    After monitoring, decide whether to loop, escalate, or stop.
    Phase 1: always stop after first attempt (no real outcome signal yet).
    """
    return "stop"
