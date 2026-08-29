"""Merchant footprint selection and test-artifact classification."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

FOOTPRINT_TABLES = (
    "customers",
    "transactions",
    "recovery_cases",
    "action_records",
    "audit_records",
    "policies",
    "notifications",
    "message_delivery_records",
    "processed_webhook_events",
)

PROTECTED_MERCHANT_IDS = frozenset({"merchant_default"})
DEV_MERCHANT_EMAIL = "admin@payback.io"

# Explicit IDs from backend/tests that created live Supabase rows
CONFIRMED_TEST_ARTIFACT_IDS = frozenset({
    "merchant_a",
    "merchant_b",
    "merchant_abc",
    "merch_dedup_446984",
    "merch_x_4e946aa1",
    "merch_y_1c7e2d13",
    "merch_x_43a0bce0",
    "merch_y_20612c0f",
})

TEST_ARTIFACT_PREFIXES = (
    "merch_x_",
    "merch_y_",
    "merch_dedup_",
)


@dataclass
class MerchantFootprint:
    merchant_id: str
    customers: int = 0
    transactions: int = 0
    recovery_cases: int = 0
    action_records: int = 0
    audit_records: int = 0
    policies: int = 0
    notifications: int = 0
    message_delivery_records: int = 0
    processed_webhook_events: int = 0
    name: Optional[str] = None
    email: Optional[str] = None

    @property
    def total_footprint(self) -> int:
        return (
            self.customers
            + self.transactions
            + self.recovery_cases
            + self.action_records
            + self.audit_records
            + self.policies
            + self.notifications
            + self.message_delivery_records
            + self.processed_webhook_events
        )

    def sort_key(self) -> tuple[int, int, int, int, int]:
        return (
            self.total_footprint,
            self.transactions,
            self.recovery_cases,
            self.customers,
            self.policies,
        )


@dataclass
class ReconciliationPlan:
    source_merchant_id: str
    target_merchant_id: str = "merchant_default"
    discard_merchant_ids: list[str] = field(default_factory=list)
    ambiguous_merchant_ids: list[str] = field(default_factory=list)
    footprints: list[MerchantFootprint] = field(default_factory=list)

    @property
    def requires_migration(self) -> bool:
        return self.source_merchant_id != self.target_merchant_id


def classify_merchant(merchant_id: str, email: Optional[str] = None) -> str:
    """
    Returns: 'protected' | 'confirmed_test_artifact' | 'ambiguous' | 'production_candidate'
    """
    if merchant_id in PROTECTED_MERCHANT_IDS:
        return "protected"
    if merchant_id in CONFIRMED_TEST_ARTIFACT_IDS:
        return "confirmed_test_artifact"
    if merchant_id in ("merchant_a", "merchant_b", "merchant_abc"):
        return "confirmed_test_artifact"
    for prefix in TEST_ARTIFACT_PREFIXES:
        if merchant_id.startswith(prefix):
            return "confirmed_test_artifact"
    # UUID-shaped merchant IDs may be real registrations from /auth/register
    if len(merchant_id) == 36 and merchant_id.count("-") == 4:
        return "ambiguous"
    # Short literal test headers without merchants row
    if merchant_id in ("merchant_x", "merchant_y"):
        return "ambiguous"
    if merchant_id.startswith("merchant_") and merchant_id not in PROTECTED_MERCHANT_IDS:
        return "ambiguous"
    if email and email.endswith("@example.com") and "test" in email.lower():
        return "confirmed_test_artifact"
    return "production_candidate"


def select_source_merchant(footprints: Iterable[MerchantFootprint]) -> MerchantFootprint:
    """Deterministic source selection by total footprint + tie-breakers."""
    candidates = list(footprints)
    if not candidates:
        raise ValueError("No merchant footprints provided")
    return max(candidates, key=lambda f: f.sort_key())


def build_reconciliation_plan(
    footprints: Iterable[MerchantFootprint],
    target_merchant_id: str = "merchant_default",
) -> ReconciliationPlan:
    fps = sorted(footprints, key=lambda f: f.sort_key(), reverse=True)
    source = select_source_merchant(fps)
    discard: list[str] = []
    ambiguous: list[str] = []

    for fp in fps:
        if fp.merchant_id == target_merchant_id:
            continue
        classification = classify_merchant(fp.merchant_id, fp.email)
        if classification == "confirmed_test_artifact":
            discard.append(fp.merchant_id)
        elif classification == "ambiguous":
            ambiguous.append(fp.merchant_id)
        elif classification == "production_candidate" and fp.total_footprint == 0:
            discard.append(fp.merchant_id)

    return ReconciliationPlan(
        source_merchant_id=source.merchant_id,
        target_merchant_id=target_merchant_id,
        discard_merchant_ids=sorted(set(discard)),
        ambiguous_merchant_ids=sorted(set(ambiguous)),
        footprints=fps,
    )
