-- ============================================================================
-- PayBack Migration 003 — Finalize Historical Merchant Dataset
-- ============================================================================
-- Prerequisites: 001 + 002 applied. Run in Supabase SQL Editor.
-- See header comments in repo file for full data policy documentation.
-- ============================================================================

BEGIN;

-- 0. Authoritative development tenant
INSERT INTO public.merchants (id, name, email, timezone)
VALUES ('merchant_default', 'PayBack Development', 'admin@payback.io', 'Asia/Kolkata')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name, email = EXCLUDED.email, timezone = EXCLUDED.timezone, updated_at = NOW();

INSERT INTO public.merchant_settings (id, merchant_id, notify_recovery_completed, notify_recovery_escalated, notify_action_failed, notify_payment_recovered)
SELECT gen_random_uuid()::text, 'merchant_default', TRUE, TRUE, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM public.merchant_settings WHERE merchant_id = 'merchant_default');

-- 1. merchant_id columns (ALTER only)
ALTER TABLE public.customers               ADD COLUMN IF NOT EXISTS merchant_id TEXT;
ALTER TABLE public.transactions            ADD COLUMN IF NOT EXISTS merchant_id TEXT;
ALTER TABLE public.recovery_cases          ADD COLUMN IF NOT EXISTS merchant_id TEXT;
ALTER TABLE public.action_records          ADD COLUMN IF NOT EXISTS merchant_id TEXT;
ALTER TABLE public.audit_records           ADD COLUMN IF NOT EXISTS merchant_id TEXT;
ALTER TABLE public.policies                ADD COLUMN IF NOT EXISTS merchant_id TEXT;
ALTER TABLE public.message_delivery_records ADD COLUMN IF NOT EXISTS merchant_id TEXT;
ALTER TABLE public.processed_webhook_events ADD COLUMN IF NOT EXISTS merchant_id TEXT;

-- 2. merchant_default baseline (pre-migration)
CREATE TEMP TABLE payback_admin_baseline (metric TEXT PRIMARY KEY, row_count BIGINT NOT NULL) ON COMMIT DROP;
INSERT INTO payback_admin_baseline (metric, row_count) VALUES
    ('customers',                (SELECT COUNT(*) FROM public.customers                WHERE merchant_id = 'merchant_default')),
    ('transactions',             (SELECT COUNT(*) FROM public.transactions             WHERE merchant_id = 'merchant_default')),
    ('recovery_cases',           (SELECT COUNT(*) FROM public.recovery_cases           WHERE merchant_id = 'merchant_default')),
    ('action_records',           (SELECT COUNT(*) FROM public.action_records           WHERE merchant_id = 'merchant_default')),
    ('audit_records',            (SELECT COUNT(*) FROM public.audit_records            WHERE merchant_id = 'merchant_default')),
    ('policies',                 (SELECT COUNT(*) FROM public.policies                 WHERE merchant_id = 'merchant_default')),
    ('notifications',            (SELECT COUNT(*) FROM public.notifications            WHERE merchant_id = 'merchant_default')),
    ('message_delivery_records', (SELECT COUNT(*) FROM public.message_delivery_records WHERE merchant_id = 'merchant_default')),
    ('processed_webhook_events', (SELECT COUNT(*) FROM public.processed_webhook_events WHERE merchant_id = 'merchant_default'));

-- 3. Pre-cleanup footprint audit
DO $$
DECLARE r RECORD; winner_id TEXT; winner_total BIGINT := 0;
BEGIN
    RAISE NOTICE '=== PAYBACK 003 PRE-CLEANUP FOOTPRINT ===';
    FOR r IN
        WITH per_table AS (
            SELECT merchant_id, 'customers' AS tbl, COUNT(*)::bigint AS cnt FROM public.customers GROUP BY 1
            UNION ALL SELECT merchant_id, 'transactions', COUNT(*)::bigint FROM public.transactions GROUP BY 1
            UNION ALL SELECT merchant_id, 'recovery_cases', COUNT(*)::bigint FROM public.recovery_cases GROUP BY 1
            UNION ALL SELECT merchant_id, 'action_records', COUNT(*)::bigint FROM public.action_records GROUP BY 1
            UNION ALL SELECT merchant_id, 'audit_records', COUNT(*)::bigint FROM public.audit_records GROUP BY 1
            UNION ALL SELECT merchant_id, 'policies', COUNT(*)::bigint FROM public.policies GROUP BY 1
            UNION ALL SELECT merchant_id, 'notifications', COUNT(*)::bigint FROM public.notifications GROUP BY 1
            UNION ALL SELECT merchant_id, 'message_delivery_records', COUNT(*)::bigint FROM public.message_delivery_records GROUP BY 1
            UNION ALL SELECT merchant_id, 'processed_webhook_events', COUNT(*)::bigint FROM public.processed_webhook_events GROUP BY 1
        ),
        p AS (
            SELECT COALESCE(merchant_id, '__NULL__') AS mid,
                SUM(CASE WHEN tbl='customers' THEN cnt ELSE 0 END) AS customers,
                SUM(CASE WHEN tbl='transactions' THEN cnt ELSE 0 END) AS transactions,
                SUM(CASE WHEN tbl='recovery_cases' THEN cnt ELSE 0 END) AS recovery_cases,
                SUM(CASE WHEN tbl='action_records' THEN cnt ELSE 0 END) AS action_records,
                SUM(CASE WHEN tbl='audit_records' THEN cnt ELSE 0 END) AS audit_records,
                SUM(CASE WHEN tbl='policies' THEN cnt ELSE 0 END) AS policies,
                SUM(CASE WHEN tbl='notifications' THEN cnt ELSE 0 END) AS notifications,
                SUM(CASE WHEN tbl='message_delivery_records' THEN cnt ELSE 0 END) AS message_deliveries,
                SUM(CASE WHEN tbl='processed_webhook_events' THEN cnt ELSE 0 END) AS webhooks,
                SUM(cnt) AS total_footprint
            FROM per_table GROUP BY 1
        )
        SELECT * FROM p ORDER BY total_footprint DESC
    LOOP
        RAISE NOTICE 'merchant_id=% cust=% tx=% rc=% act=% aud=% pol=% ntf=% msg=% wh=% TOTAL=%',
            r.mid, r.customers, r.transactions, r.recovery_cases, r.action_records, r.audit_records,
            r.policies, r.notifications, r.message_deliveries, r.webhooks, r.total_footprint;
        IF r.total_footprint > winner_total THEN winner_total := r.total_footprint; winner_id := r.mid; END IF;
    END LOOP;
    IF winner_id IS DISTINCT FROM 'merchant_default' THEN
        RAISE WARNING 'Highest footprint is % (not merchant_default). No cross-merchant merge will occur.', winner_id;
    ELSE
        RAISE NOTICE 'merchant_default confirmed as authoritative development tenant.';
    END IF;
END $$;

-- 4. Disposable list (exactly seven)
CREATE TEMP TABLE payback_discard_merchants (id TEXT PRIMARY KEY) ON COMMIT DROP;
INSERT INTO payback_discard_merchants (id) VALUES
    ('merchant_a'), ('merchant_b'), ('merch_dedup_446984'),
    ('merch_x_4e946aa1'), ('merch_y_1c7e2d13'), ('merch_x_43a0bce0'), ('merch_y_20612c0f');
DELETE FROM payback_discard_merchants WHERE id IN ('merchant_default','merchant_x','merchant_y','9422b6ce-216a-428a-87f1-5122eaa12740');

-- 5. DELETE confirmed test artifacts BEFORE NULL backfill (FK-safe order)
DELETE FROM public.processed_webhook_events WHERE merchant_id IN (SELECT id FROM payback_discard_merchants);
DELETE FROM public.message_delivery_records md
 WHERE merchant_id IN (SELECT id FROM payback_discard_merchants)
    OR recovery_case_id IN (SELECT rc.id::text FROM public.recovery_cases rc WHERE rc.merchant_id IN (SELECT id FROM payback_discard_merchants));
DELETE FROM public.notifications WHERE merchant_id IN (SELECT id FROM payback_discard_merchants);
DELETE FROM public.audit_records au
 WHERE merchant_id IN (SELECT id FROM payback_discard_merchants)
    OR recovery_case_id IN (SELECT rc.id FROM public.recovery_cases rc WHERE rc.merchant_id IN (SELECT id FROM payback_discard_merchants));
DELETE FROM public.action_records ar
 WHERE merchant_id IN (SELECT id FROM payback_discard_merchants)
    OR recovery_case_id IN (SELECT rc.id FROM public.recovery_cases rc WHERE rc.merchant_id IN (SELECT id FROM payback_discard_merchants));
DELETE FROM public.recovery_cases WHERE merchant_id IN (SELECT id FROM payback_discard_merchants);
DELETE FROM public.transactions  WHERE merchant_id IN (SELECT id FROM payback_discard_merchants);
DELETE FROM public.customers     WHERE merchant_id IN (SELECT id FROM payback_discard_merchants);
DELETE FROM public.policies      WHERE merchant_id IN (SELECT id FROM payback_discard_merchants);
DELETE FROM public.merchant_settings WHERE merchant_id IN (SELECT id FROM payback_discard_merchants);
DELETE FROM public.merchants     WHERE id IN (SELECT id FROM payback_discard_merchants);

-- 6. Unambiguous ownership repair (NULL child inherits from parent ONLY)
UPDATE public.transactions t SET merchant_id = c.merchant_id
FROM public.customers c WHERE t.customer_id = c.id AND t.merchant_id IS NULL AND c.merchant_id IS NOT NULL;

UPDATE public.recovery_cases rc SET merchant_id = t.merchant_id
FROM public.transactions t WHERE rc.transaction_id = t.id AND rc.merchant_id IS NULL AND t.merchant_id IS NOT NULL;

UPDATE public.recovery_cases rc SET merchant_id = c.merchant_id
FROM public.customers c WHERE rc.customer_id = c.id AND rc.merchant_id IS NULL AND c.merchant_id IS NOT NULL;

UPDATE public.action_records ar SET merchant_id = rc.merchant_id
FROM public.recovery_cases rc WHERE ar.recovery_case_id = rc.id AND ar.merchant_id IS NULL AND rc.merchant_id IS NOT NULL;

UPDATE public.audit_records au SET merchant_id = rc.merchant_id
FROM public.recovery_cases rc WHERE au.recovery_case_id = rc.id AND au.merchant_id IS NULL AND rc.merchant_id IS NOT NULL;

UPDATE public.message_delivery_records md SET merchant_id = rc.merchant_id
FROM public.recovery_cases rc WHERE rc.id::text = md.recovery_case_id AND md.merchant_id IS NULL AND rc.merchant_id IS NOT NULL;

-- 7. Legacy NULL → merchant_default (genuinely unassigned dev data only)
UPDATE public.customers                SET merchant_id = 'merchant_default' WHERE merchant_id IS NULL;
UPDATE public.transactions             SET merchant_id = 'merchant_default' WHERE merchant_id IS NULL;
UPDATE public.recovery_cases           SET merchant_id = 'merchant_default' WHERE merchant_id IS NULL;
UPDATE public.action_records           SET merchant_id = 'merchant_default' WHERE merchant_id IS NULL;
UPDATE public.audit_records            SET merchant_id = 'merchant_default' WHERE merchant_id IS NULL;
UPDATE public.policies                 SET merchant_id = 'merchant_default' WHERE merchant_id IS NULL;
UPDATE public.notifications            SET merchant_id = 'merchant_default' WHERE merchant_id IS NULL;
UPDATE public.message_delivery_records SET merchant_id = 'merchant_default' WHERE merchant_id IS NULL;
UPDATE public.processed_webhook_events SET merchant_id = 'merchant_default' WHERE merchant_id IS NULL;

-- 8. Protected ambiguous merchants — parent rows for FK (placeholder metadata only)
INSERT INTO public.merchants (id, name, email, timezone) VALUES
    ('merchant_x', 'Legacy Protected Merchant (ambiguous)', 'legacy-protected-merchant-x@payback.internal', 'Asia/Kolkata'),
    ('merchant_y', 'Legacy Protected Merchant (ambiguous)', 'legacy-protected-merchant-y@payback.internal', 'Asia/Kolkata'),
    ('9422b6ce-216a-428a-87f1-5122eaa12740', 'Legacy Protected Merchant (ambiguous UUID)', 'legacy-protected-9422b6ce@payback.internal', 'Asia/Kolkata')
ON CONFLICT (id) DO NOTHING;

-- 9. Grants (idempotent; service_role only; RLS unchanged)
GRANT USAGE ON SCHEMA public TO service_role;
GRANT ALL ON TABLE public.merchants, public.merchant_settings, public.customers, public.transactions,
    public.recovery_cases, public.action_records, public.audit_records, public.policies,
    public.message_delivery_records, public.notifications, public.processed_webhook_events TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- 10. Foreign keys (skip if merchant_id FK already exists on table)
DO $fk$
DECLARE spec RECORD;
BEGIN
    FOR spec IN SELECT * FROM (VALUES
        ('customers',               'fk_customers_merchant'),
        ('transactions',            'fk_transactions_merchant'),
        ('recovery_cases',          'fk_recovery_cases_merchant'),
        ('action_records',          'fk_action_records_merchant'),
        ('audit_records',           'fk_audit_records_merchant'),
        ('policies',                'fk_policies_merchant'),
        ('notifications',           'fk_notifications_merchant'),
        ('message_delivery_records','fk_message_delivery_merchant'),
        ('processed_webhook_events','fk_processed_webhooks_merchant')
    ) AS t(tbl, cname)
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint c
            JOIN pg_class rel ON rel.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = rel.relnamespace
            WHERE n.nspname = 'public' AND rel.relname = spec.tbl
              AND c.contype = 'f'
              AND pg_get_constraintdef(c.oid) LIKE '%merchant_id%REFERENCES%merchants%'
        ) AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = spec.cname) THEN
            EXECUTE format(
                'ALTER TABLE public.%I ADD CONSTRAINT %I FOREIGN KEY (merchant_id) REFERENCES public.merchants(id)',
                spec.tbl, spec.cname
            );
        END IF;
    END LOOP;
    -- merchant_settings: inline FK from 001 — do not duplicate
END $fk$;

-- 11. Indexes (IF NOT EXISTS; 001 may already have composite merchant indexes)
CREATE INDEX IF NOT EXISTS idx_customers_merchant_id ON public.customers(merchant_id);
CREATE INDEX IF NOT EXISTS idx_transactions_merchant_id ON public.transactions(merchant_id);
CREATE INDEX IF NOT EXISTS idx_transactions_merchant_customer ON public.transactions(merchant_id, customer_id);
CREATE INDEX IF NOT EXISTS idx_recovery_cases_merchant_id ON public.recovery_cases(merchant_id);
CREATE INDEX IF NOT EXISTS idx_recovery_cases_merchant_customer ON public.recovery_cases(merchant_id, customer_id);
CREATE INDEX IF NOT EXISTS idx_recovery_cases_merchant_created ON public.recovery_cases(merchant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_action_records_merchant_id ON public.action_records(merchant_id);
CREATE INDEX IF NOT EXISTS idx_audit_records_merchant_id ON public.audit_records(merchant_id);
CREATE INDEX IF NOT EXISTS idx_policies_merchant_id ON public.policies(merchant_id);
CREATE INDEX IF NOT EXISTS idx_notifications_merchant_id ON public.notifications(merchant_id);
CREATE INDEX IF NOT EXISTS idx_message_delivery_merchant_id ON public.message_delivery_records(merchant_id);
CREATE INDEX IF NOT EXISTS idx_processed_webhook_merchant_id ON public.processed_webhook_events(merchant_id);

-- 12. Validation — NULL merchant_id (all tables)
DO $val$
DECLARE n BIGINT; tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'customers','transactions','recovery_cases','action_records','audit_records',
        'policies','notifications','message_delivery_records','processed_webhook_events'
    ] LOOP
        EXECUTE format('SELECT COUNT(*) FROM public.%I WHERE merchant_id IS NULL', tbl) INTO n;
        IF n > 0 THEN RAISE EXCEPTION 'Validation failed: % has % NULL merchant_id row(s)', tbl, n; END IF;
    END LOOP;
    SELECT COUNT(*) INTO n FROM public.merchant_settings WHERE merchant_id IS NULL;
    IF n > 0 THEN RAISE EXCEPTION 'Validation failed: merchant_settings has % NULL merchant_id row(s)', n; END IF;
END $val$;

-- 13. Cross-tenant validation
DO $xval$
DECLARE n BIGINT;
BEGIN
    SELECT COUNT(*) INTO n FROM public.transactions t JOIN public.customers c ON c.id = t.customer_id WHERE t.merchant_id <> c.merchant_id;
    IF n > 0 THEN RAISE EXCEPTION 'Validation failed: % transaction/customer merchant mismatches', n; END IF;
    SELECT COUNT(*) INTO n FROM public.recovery_cases rc JOIN public.transactions t ON t.id = rc.transaction_id WHERE rc.merchant_id <> t.merchant_id;
    IF n > 0 THEN RAISE EXCEPTION 'Validation failed: % recovery/transaction merchant mismatches', n; END IF;
    SELECT COUNT(*) INTO n FROM public.recovery_cases rc JOIN public.customers c ON c.id = rc.customer_id WHERE rc.merchant_id <> c.merchant_id;
    IF n > 0 THEN RAISE EXCEPTION 'Validation failed: % recovery/customer merchant mismatches', n; END IF;
    SELECT COUNT(*) INTO n FROM public.action_records ar JOIN public.recovery_cases rc ON rc.id = ar.recovery_case_id WHERE ar.merchant_id <> rc.merchant_id;
    IF n > 0 THEN RAISE EXCEPTION 'Validation failed: % action/recovery merchant mismatches', n; END IF;
    SELECT COUNT(*) INTO n FROM public.audit_records au JOIN public.recovery_cases rc ON rc.id = au.recovery_case_id WHERE au.merchant_id <> rc.merchant_id;
    IF n > 0 THEN RAISE EXCEPTION 'Validation failed: % audit/recovery merchant mismatches', n; END IF;
    SELECT COUNT(*) INTO n FROM public.message_delivery_records md JOIN public.recovery_cases rc ON rc.id::text = md.recovery_case_id WHERE md.merchant_id <> rc.merchant_id;
    IF n > 0 THEN RAISE EXCEPTION 'Validation failed: % message/recovery merchant mismatches', n; END IF;
END $xval$;

-- 14. merchant_default must not lose historical rows
DO $admin$
DECLARE r RECORD; post BIGINT; base BIGINT;
BEGIN
    FOR r IN SELECT metric, row_count FROM payback_admin_baseline LOOP
        EXECUTE format('SELECT COUNT(*) FROM public.%I WHERE merchant_id = ''merchant_default''', r.metric) INTO post;
        IF post < r.row_count THEN
            RAISE EXCEPTION 'Validation failed: merchant_default % dropped from % to %', r.metric, r.row_count, post;
        END IF;
        RAISE NOTICE 'merchant_default % : baseline=% post=%', r.metric, r.row_count, post;
    END LOOP;
END $admin$;

-- 15. NOT NULL (after validation passes)
ALTER TABLE public.customers                ALTER COLUMN merchant_id SET NOT NULL;
ALTER TABLE public.transactions             ALTER COLUMN merchant_id SET NOT NULL;
ALTER TABLE public.recovery_cases           ALTER COLUMN merchant_id SET NOT NULL;
ALTER TABLE public.action_records           ALTER COLUMN merchant_id SET NOT NULL;
ALTER TABLE public.audit_records            ALTER COLUMN merchant_id SET NOT NULL;
ALTER TABLE public.policies                 ALTER COLUMN merchant_id SET NOT NULL;
ALTER TABLE public.notifications            ALTER COLUMN merchant_id SET NOT NULL;
ALTER TABLE public.message_delivery_records ALTER COLUMN merchant_id SET NOT NULL;
ALTER TABLE public.processed_webhook_events ALTER COLUMN merchant_id SET NOT NULL;

COMMIT;