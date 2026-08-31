-- PayBack Phase 4 Database Migrations
-- Additive and non-destructive. Preserves all existing Phase 2/3 tables and data.

-- 1. Merchants & Workspaces
CREATE TABLE IF NOT EXISTS merchants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    timezone TEXT DEFAULT 'Asia/Kolkata',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Merchant Settings & Preferences
CREATE TABLE IF NOT EXISTS merchant_settings (
    id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    notify_recovery_completed BOOLEAN DEFAULT TRUE,
    notify_recovery_escalated BOOLEAN DEFAULT TRUE,
    notify_action_failed BOOLEAN DEFAULT TRUE,
    notify_payment_recovered BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_merchant_settings UNIQUE (merchant_id)
);

-- 3. Add merchant_id columns to existing tables (nullable for backward compatibility)
ALTER TABLE customers ADD COLUMN IF NOT EXISTS merchant_id TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS merchant_id TEXT;
ALTER TABLE recovery_cases ADD COLUMN IF NOT EXISTS merchant_id TEXT;
ALTER TABLE action_records ADD COLUMN IF NOT EXISTS merchant_id TEXT;
ALTER TABLE audit_records ADD COLUMN IF NOT EXISTS merchant_id TEXT;

-- 4. Policies table extension
ALTER TABLE policies ADD COLUMN IF NOT EXISTS merchant_id TEXT;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS name TEXT DEFAULT 'Default Policy';
ALTER TABLE policies ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE policies ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- 5. Message Delivery Records
CREATE TABLE IF NOT EXISTS message_delivery_records (
    id TEXT PRIMARY KEY,
    merchant_id TEXT,
    recovery_case_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'mock',
    provider_message_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    content_preview TEXT,
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    failure_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Merchant Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL,
    notification_type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    recovery_case_id TEXT,
    read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Webhook Idempotency Records
CREATE TABLE IF NOT EXISTS processed_webhook_events (
    id TEXT PRIMARY KEY,
    merchant_id TEXT,
    provider TEXT NOT NULL DEFAULT 'razorpay',
    provider_event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    received_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ DEFAULT NOW(),
    processing_status TEXT DEFAULT 'processed',
    CONSTRAINT unique_provider_event UNIQUE (provider, provider_event_id)
);

-- 8. Performance Indexes
CREATE INDEX IF NOT EXISTS idx_customers_merchant ON customers(merchant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_merchant ON transactions(merchant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_customer ON transactions(customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recovery_cases_merchant ON recovery_cases(merchant_id, status);
CREATE INDEX IF NOT EXISTS idx_recovery_cases_customer ON recovery_cases(customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recovery_cases_tx ON recovery_cases(transaction_id);
CREATE INDEX IF NOT EXISTS idx_audit_records_case ON audit_records(recovery_case_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_notifications_merchant ON notifications(merchant_id, read, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_message_delivery_case ON message_delivery_records(recovery_case_id);
CREATE INDEX IF NOT EXISTS idx_policies_merchant ON policies(merchant_id, is_active);

-- 9. Row Level Security (RLS) Policies
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE recovery_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE action_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_delivery_records ENABLE ROW LEVEL SECURITY;

-- Note: RLS allows service_role full access by default, and scopes authenticated JWTs by merchant_id claim.
