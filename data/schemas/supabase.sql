-- PayBack — Supabase PostgreSQL Schema (Phase 2)
-- Designed for Supabase free-tier PostgreSQL database.

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id TEXT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    opted_out BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id),
    amount NUMERIC(12, 2) NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    payment_method TEXT NOT NULL DEFAULT 'unknown',
    status TEXT NOT NULL,
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS recovery_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES transactions(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    amount_at_risk NUMERIC(12, 2) NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'detected',
    recovery_probability NUMERIC(5, 4) NOT NULL DEFAULT 0,
    selected_action TEXT,
    decision TEXT,
    stop_reason TEXT,
    escalate_reason TEXT,
    outcome TEXT,
    amount_recovered NUMERIC(12, 2) NOT NULL DEFAULT 0,
    retry_count INTEGER NOT NULL DEFAULT 0,
    message_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS action_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recovery_case_id UUID NOT NULL REFERENCES recovery_cases(id),
    action TEXT NOT NULL,
    outcome TEXT,
    detail TEXT,
    external_ref TEXT,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recovery_case_id UUID NOT NULL REFERENCES recovery_cases(id),
    event_type TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id TEXT NOT NULL,
    maximum_retries INTEGER NOT NULL DEFAULT 3,
    maximum_messages INTEGER NOT NULL DEFAULT 3,
    recovery_window_hours INTEGER NOT NULL DEFAULT 72,
    high_value_threshold NUMERIC(12, 2) NOT NULL DEFAULT 10000,
    human_approval_required BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
