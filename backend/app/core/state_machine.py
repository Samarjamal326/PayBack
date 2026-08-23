from app.models.domain import RecoveryStatus

# Defines which transitions are legal. Anything not listed is forbidden.
_ALLOWED: dict[RecoveryStatus, set[RecoveryStatus]] = {
    RecoveryStatus.DETECTED: {RecoveryStatus.ANALYZING},
    RecoveryStatus.ANALYZING: {RecoveryStatus.ELIGIBILITY_CHECK},
    RecoveryStatus.ELIGIBILITY_CHECK: {
        RecoveryStatus.DECISION,
        RecoveryStatus.STOPPED,
    },
    RecoveryStatus.DECISION: {
        RecoveryStatus.ACTION_PENDING,
        RecoveryStatus.ESCALATED,
        RecoveryStatus.STOPPED,
    },
    RecoveryStatus.ACTION_PENDING: {RecoveryStatus.ACTION_EXECUTED},
    RecoveryStatus.ACTION_EXECUTED: {RecoveryStatus.MONITORING},
    RecoveryStatus.MONITORING: {
        RecoveryStatus.RECOVERED,
        RecoveryStatus.ESCALATED,
        RecoveryStatus.STOPPED,
        RecoveryStatus.ACTION_PENDING,  # retry loop
    },
    # Terminal states — no further transitions
    RecoveryStatus.RECOVERED: set(),
    RecoveryStatus.ESCALATED: set(),
    RecoveryStatus.STOPPED: set(),
}


class InvalidTransitionError(Exception):
    pass


def assert_transition(current: RecoveryStatus, next_status: RecoveryStatus) -> None:
    allowed = _ALLOWED.get(current, set())
    if next_status not in allowed:
        raise InvalidTransitionError(
            f"Cannot transition from {current!r} to {next_status!r}. "
            f"Allowed: {sorted(s.value for s in allowed)}"
        )


def can_transition(current: RecoveryStatus, next_status: RecoveryStatus) -> bool:
    return next_status in _ALLOWED.get(current, set())
