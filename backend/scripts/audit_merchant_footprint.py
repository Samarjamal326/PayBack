#!/usr/bin/env python3
"""Audit merchant data footprint in Supabase. Read-only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import httpx
from app.config import settings

TABLES = [
    "customers",
    "transactions",
    "recovery_cases",
    "action_records",
    "audit_records",
    "policies",
    "notifications",
    "message_delivery_records",
    "processed_webhook_events",
]

# Patterns from backend/tests — confirmed test artifacts when in DB
TEST_ARTIFACT_PATTERNS = (
    "merchant_a",
    "merchant_b",
    "merchant_abc",
    "merch_x_",
    "merch_y_",
    "merch_dedup_",
    "merch_",
)

PROTECTED = {"merchant_default"}


def fetch_all(client: httpx.Client, base: str, headers: dict, table: str, col: str = "merchant_id") -> dict[str | None, int]:
    """Count rows grouped by merchant_id via paginated fetch."""
    counts: dict[str | None, int] = {}
    offset = 0
    limit = 1000
    while True:
        params = {
            "select": col,
            "limit": str(limit),
            "offset": str(offset),
        }
        resp = client.get(f"{base}/rest/v1/{table}", params=params, headers=headers)
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            break
        for row in rows:
            mid = row.get(col)
            key = mid if mid is not None else "__NULL__"
            counts[key] = counts.get(key, 0) + 1
        if len(rows) < limit:
            break
        offset += limit
    return counts


def fetch_merchants(client: httpx.Client, base: str, headers: dict) -> list[dict]:
    resp = client.get(f"{base}/rest/v1/merchants", params={"select": "id,name,email,created_at"}, headers=headers)
    resp.raise_for_status()
    return resp.json()


def is_test_artifact(merchant_id: str, email: str = "") -> bool:
    if merchant_id in PROTECTED:
        return False
    if merchant_id.startswith("merch_") or merchant_id.startswith("merchant_a") or merchant_id.startswith("merchant_b"):
        return True
    if merchant_id == "merchant_abc":
        return True
    if merchant_id.startswith("merchant_") and merchant_id not in PROTECTED:
        # merchant_<uuid> from registration tests - need email check
        pass
    # Heuristic: random UUID merchant ids from register tests
    if len(merchant_id) == 36 and merchant_id.count("-") == 4:
        return False  # ambiguous - real registration
    for pat in TEST_ARTIFACT_PATTERNS:
        if merchant_id.startswith(pat) or merchant_id == pat.rstrip("_"):
            return True
    return False


def main() -> int:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        print("Supabase not configured.")
        return 1

    base = settings.supabase_url.rstrip("/")
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }

    merchants = fetch_merchants(httpx.Client(timeout=30), base, headers)

    report: dict[str, dict] = {}
    for m in merchants:
        mid = m["id"]
        report[mid] = {
            "name": m.get("name"),
            "email": m.get("email"),
            "customers": 0,
            "transactions": 0,
            "recovery_cases": 0,
            "action_records": 0,
            "audit_records": 0,
            "policies": 0,
            "notifications": 0,
            "message_delivery_records": 0,
            "processed_webhook_events": 0,
            "total_footprint": 0,
        }

    # Ensure merchant_default in report even if no merchants row
    if "merchant_default" not in report:
        report["merchant_default"] = {
            "name": "PayBack Development",
            "email": "admin@payback.io",
            "customers": 0,
            "transactions": 0,
            "recovery_cases": 0,
            "action_records": 0,
            "audit_records": 0,
            "policies": 0,
            "notifications": 0,
            "message_delivery_records": 0,
            "processed_webhook_events": 0,
            "total_footprint": 0,
        }

    with httpx.Client(timeout=60) as client:
        for table in TABLES:
            counts = fetch_all(client, base, headers, table)
            col_key = table if table != "policies" else table
            for mid_key, cnt in counts.items():
                mid = None if mid_key == "__NULL__" else mid_key
                if mid not in report:
                    report[mid or "__NULL__"] = {
                        "name": None,
                        "email": None,
                        "customers": 0,
                        "transactions": 0,
                        "recovery_cases": 0,
                        "action_records": 0,
                        "audit_records": 0,
                        "policies": 0,
                        "notifications": 0,
                        "message_delivery_records": 0,
                        "processed_webhook_events": 0,
                        "total_footprint": 0,
                    }
                key = mid or "__NULL__"
                field = table
                report[key][field] = cnt

    for mid, data in report.items():
        data["total_footprint"] = sum(data[t] for t in TABLES)

    # Sort by footprint
    ranked = sorted(report.items(), key=lambda x: (-x[1]["total_footprint"], -x[1]["transactions"], -x[1]["recovery_cases"], -x[1]["customers"], -x[1]["policies"]))

    print("MERCHANT FOOTPRINT REPORT")
    print("=" * 80)
    for mid, data in ranked:
        artifact = is_test_artifact(mid, data.get("email") or "") if mid != "__NULL__" else False
        print(json.dumps({"merchant_id": mid, **data, "likely_test_artifact": artifact}, indent=2))
        print("-" * 40)

    if ranked:
        winner_id, winner = ranked[0]
        print(f"\nSELECTED SOURCE (by footprint): {winner_id}")
        print(f"Total footprint: {winner['total_footprint']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
