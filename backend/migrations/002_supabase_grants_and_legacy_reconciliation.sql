-- ============================================================================
-- PayBack Migration 002 (CORRECTED)
-- Supabase PostgreSQL grants + idempotent legacy merchant reconciliation
--
-- Run this in: Supabase Dashboard → SQL Editor
-- Safe to run multiple times (non-destructive).
--
-- Root cause of HTTP 403 / Postgres 42501:
--   Migration 001 created Phase 4 tables (merchants, merchant_settings, …)
--   but did NOT grant table privileges to service_role.
--   Supabase PostgREST uses service_role JWT; it bypasses RLS but still
--   requires explicit GRANT on each table.
--
-- Prerequisites: Migration 001 and data/schemas/supabase.sql already applied.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 0. Pre-flight: required tables must exist
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'merchants'
  ) THEN
    RAISE EXCEPTION 'Table public.merchants is missing. Run 001_phase4_production_readiness.sql first.';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'customers'
  ) THEN
    RAISE EXCEPTION 'Table public.customers is missing. Run data/schemas/supabase.sql first.';
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 1. Schema usage (required before any table access via PostgREST)
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA public TO service_role;

-- ---------------------------------------------------------------------------
-- 2. Table privileges for service_role — ALL tables used by backend repos
--
-- Derived from backend/app/repositories/supabase.py:
--
--   merchants                 SELECT, UPSERT (register/login/settings)
--   merchant_settings         SELECT, UPSERT
--   customers                 SELECT, UPSERT
--   transactions              SELECT, UPSERT
--   recovery_cases            SELECT, UPSERT
--   action_records            SELECT, INSERT
--   audit_records             SELECT, INSERT
--   policies                  SELECT, UPSERT
--   message_delivery_records  SELECT, INSERT
--   notifications             SELECT, INSERT, UPSERT (mark read)
--   processed_webhook_events  SELECT, UPSERT
--
-- GRANT ALL is the minimum Supabase-recommended set for backend service_role.
-- RLS remains ENABLED where already configured; service_role bypasses RLS.
-- We do NOT grant additional privileges to anon or authenticated here.
-- ---------------------------------------------------------------------------
GRANT ALL ON TABLE public.customers                TO service_role;
GRANT ALL ON TABLE public.transactions             TO service_role;
GRANT ALL ON TABLE public.recovery_cases           TO service_role;
GRANT ALL ON TABLE public.action_records           TO service_role;
GRANT ALL ON TABLE public.audit_records            TO service_role;
GRANT ALL ON TABLE public.policies                 TO service_role;
GRANT ALL ON TABLE public.merchants                TO service_role;
GRANT ALL ON TABLE public.merchant_settings        TO service_role;
GRANT ALL ON TABLE public.message_delivery_records TO service_role;
GRANT ALL ON TABLE public.notifications            TO service_role;
GRANT ALL ON TABLE public.processed_webhook_events TO service_role;

-- Sequences (safe no-op if none exist; PayBack mostly uses gen_random_uuid())
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- Future tables created in public schema by migrations
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON TABLES TO service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO service_role;

-- ---------------------------------------------------------------------------
-- 3. Development / demo merchant (idempotent)
--    Owns legacy rows where merchant_id IS NULL after reconciliation.
-- ---------------------------------------------------------------------------
INSERT INTO public.merchants (id, name, email, timezone)
VALUES (
    'merchant_default',
    'PayBack Development',
    'admin@payback.io',
    'Asia/Kolkata'
)
ON CONFLICT (id) DO UPDATE SET
    name      = EXCLUDED.name,
    email     = EXCLUDED.email,
    timezone  = EXCLUDED.timezone,
    updated_at = NOW();

-- ---------------------------------------------------------------------------
-- 4. Default merchant settings (idempotent)
-- ---------------------------------------------------------------------------
INSERT INTO public.merchant_settings (
    id,
    merchant_id,
    notify_recovery_completed,
    notify_recovery_escalated,
    notify_action_failed,
    notify_payment_recovered
)
SELECT
    gen_random_uuid()::text,
    'merchant_default',
    TRUE,
    TRUE,
    TRUE,
    TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM public.merchant_settings
    WHERE merchant_id = 'merchant_default'
);

-- ---------------------------------------------------------------------------
-- 5. Pre-reconciliation integrity report (does NOT block migration)
--    Orphan FK rows are left unchanged; only merchant_id IS NULL is backfilled.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  orphan_tx   INTEGER;
  orphan_rc   INTEGER;
  orphan_act  INTEGER;
  orphan_aud  INTEGER;
BEGIN
  SELECT COUNT(*) INTO orphan_tx
  FROM public.transactions t
  WHERE NOT EXISTS (SELECT 1 FROM public.customers c WHERE c.id = t.customer_id);

  SELECT COUNT(*) INTO orphan_rc
  FROM public.recovery_cases rc
  WHERE NOT EXISTS (SELECT 1 FROM public.transactions t WHERE t.id = rc.transaction_id)
     OR NOT EXISTS (SELECT 1 FROM public.customers c WHERE c.id = rc.customer_id);

  SELECT COUNT(*) INTO orphan_act
  FROM public.action_records ar
  WHERE NOT EXISTS (SELECT 1 FROM public.recovery_cases rc WHERE rc.id = ar.recovery_case_id);

  SELECT COUNT(*) INTO orphan_aud
  FROM public.audit_records au
  WHERE NOT EXISTS (SELECT 1 FROM public.recovery_cases rc WHERE rc.id = au.recovery_case_id);

  RAISE NOTICE 'PayBack 002 pre-check: orphan transactions=%, orphan recovery_cases=%, orphan action_records=%, orphan audit_records=%',
    orphan_tx, orphan_rc, orphan_act, orphan_aud;
END $$;

-- ---------------------------------------------------------------------------
-- 6. Legacy reconciliation — ONLY rows with merchant_id IS NULL
--    Does NOT reassign rows already owned by another merchant.
--    Does NOT match by email/name.
-- ---------------------------------------------------------------------------

-- Parent entities first
UPDATE public.customers
SET merchant_id = 'merchant_default'
WHERE merchant_id IS NULL;

UPDATE public.transactions
SET merchant_id = 'merchant_default'
WHERE merchant_id IS NULL;

UPDATE public.recovery_cases
SET merchant_id = 'merchant_default'
WHERE merchant_id IS NULL;

UPDATE public.policies
SET merchant_id = 'merchant_default'
WHERE merchant_id IS NULL;

UPDATE public.notifications
SET merchant_id = 'merchant_default'
WHERE merchant_id IS NULL;

UPDATE public.message_delivery_records
SET merchant_id = 'merchant_default'
WHERE merchant_id IS NULL;

UPDATE public.processed_webhook_events
SET merchant_id = 'merchant_default'
WHERE merchant_id IS NULL;

UPDATE public.action_records
SET merchant_id = 'merchant_default'
WHERE merchant_id IS NULL;

UPDATE public.audit_records
SET merchant_id = 'merchant_default'
WHERE merchant_id IS NULL;

-- Child rows: inherit merchant_id from recovery case when still NULL
-- Note: Phase 4 tables (message_delivery_records) use TEXT ids;
--       Phase 2 tables (recovery_cases, action_records, audit_records) use UUID.
UPDATE public.action_records ar
SET merchant_id = rc.merchant_id
FROM public.recovery_cases rc
WHERE ar.recovery_case_id = rc.id
  AND ar.merchant_id IS NULL
  AND rc.merchant_id IS NOT NULL;

UPDATE public.audit_records au
SET merchant_id = rc.merchant_id
FROM public.recovery_cases rc
WHERE au.recovery_case_id = rc.id
  AND au.merchant_id IS NULL
  AND rc.merchant_id IS NOT NULL;

UPDATE public.message_delivery_records md
SET merchant_id = rc.merchant_id
FROM public.recovery_cases rc
WHERE rc.id::text = md.recovery_case_id
  AND md.merchant_id IS NULL
  AND rc.merchant_id IS NOT NULL;

-- Align transaction merchant_id with customer when transaction is NULL but customer is set
UPDATE public.transactions t
SET merchant_id = c.merchant_id
FROM public.customers c
WHERE t.customer_id = c.id
  AND t.merchant_id IS NULL
  AND c.merchant_id IS NOT NULL;

-- Align recovery_case merchant_id with transaction when case is NULL but transaction is set
UPDATE public.recovery_cases rc
SET merchant_id = t.merchant_id
FROM public.transactions t
WHERE rc.transaction_id = t.id
  AND rc.merchant_id IS NULL
  AND t.merchant_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 7. Indexes (idempotent)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_merchants_email
  ON public.merchants(email);

COMMIT;

-- ---------------------------------------------------------------------------
-- 8. Post-run verification (run manually after COMMIT if desired)
-- ---------------------------------------------------------------------------
-- SELECT tablename, has_table_privilege('service_role', 'public.' || tablename, 'SELECT') AS can_select,
--        has_table_privilege('service_role', 'public.' || tablename, 'INSERT') AS can_insert,
--        has_table_privilege('service_role', 'public.' || tablename, 'UPDATE') AS can_update
-- FROM pg_tables
-- WHERE schemaname = 'public'
--   AND tablename IN (
--     'merchants','merchant_settings','customers','transactions','recovery_cases',
--     'action_records','audit_records','policies','message_delivery_records',
--     'notifications','processed_webhook_events'
--   );
