#!/usr/bin/env python3
"""
One-time / idempotent legacy data reconciliation for PayBack.

Assigns merchant_id IS NULL rows to the designated development merchant
(merchant_default / admin@payback.io). Does NOT assign records based on
email/name matching.

Usage:
    python backend/scripts/reconcile_legacy_merchant_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.models.domain import Merchant, MerchantSettings  # noqa: E402
from app.repositories.factory import get_repository_bundle  # noqa: E402

DEV_MERCHANT_ID = "merchant_default"
DEV_MERCHANT_EMAIL = "admin@payback.io"
DEV_MERCHANT_NAME = "PayBack Development"

TABLES_WITH_MERCHANT = (
    "customers",
    "transactions",
    "recovery_cases",
    "action_records",
    "audit_records",
    "policies",
    "message_delivery_records",
    "notifications",
    "processed_webhook_events",
)


def main() -> int:
    if not settings.is_supabase_configured():
        print("Supabase is not configured. Run SQL migration 002 manually or configure .env.")
        return 1

    repos = get_repository_bundle(settings)
    merchant_repo = repos.merchants

    existing = merchant_repo.get(DEV_MERCHANT_ID)
    if not existing:
        merchant_repo.save(
            Merchant(
                id=DEV_MERCHANT_ID,
                name=DEV_MERCHANT_NAME,
                email=DEV_MERCHANT_EMAIL,
            )
        )
        print(f"Created development merchant '{DEV_MERCHANT_ID}'")
    else:
        print(f"Development merchant '{DEV_MERCHANT_ID}' already exists")

    settings_obj = merchant_repo.get_settings(DEV_MERCHANT_ID)
    if not settings_obj.id:
        merchant_repo.save_settings(MerchantSettings(merchant_id=DEV_MERCHANT_ID))
        print("Created default merchant_settings")

    client = getattr(repos.customers, "client", None)
    if client is None:
        print("In-memory mode: nothing to reconcile remotely.")
        return 0

    print("Reconciling NULL merchant_id rows via Supabase REST…")
    for table in TABLES_WITH_MERCHANT:
        # PostgREST PATCH filter: merchant_id=is.null
        try:
            import httpx

            headers = client._headers
            url = f"{client.url}/rest/v1/{table}"
            with httpx.Client(timeout=30.0) as http:
                resp = http.patch(
                    url,
                    params={"merchant_id": "is.null"},
                    json={"merchant_id": DEV_MERCHANT_ID},
                    headers={**headers, "Prefer": "return=representation"},
                )
                if resp.status_code >= 400:
                    print(f"  {table}: HTTP {resp.status_code} — {resp.text[:200]}")
                else:
                    updated = resp.json()
                    count = len(updated) if isinstance(updated, list) else 0
                    print(f"  {table}: updated {count} row(s)")
        except Exception as exc:
            print(f"  {table}: ERROR — {exc}")
            return 1

    print("Reconciliation complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
