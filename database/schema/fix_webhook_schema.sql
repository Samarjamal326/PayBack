-- ============================================
-- Fix Webhook Events Database Schema
-- ============================================
-- This SQL will create/update the processed_webhook_events table
-- to support webhook idempotency and connect with other tables

-- Drop existing table if it exists (to start fresh)
DROP TABLE IF EXISTS processed_webhook_events CASCADE;

-- Create the processed_webhook_events table with proper schema
CREATE TABLE processed_webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id VARCHAR(255),
    provider VARCHAR(50) NOT NULL DEFAULT 'razorpay',
    provider_event_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    processing_status VARCHAR(50) DEFAULT 'processed',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add indexes for performance
CREATE INDEX idx_processed_webhook_events_provider_event_id ON processed_webhook_events(provider, provider_event_id);
CREATE INDEX idx_processed_webhook_events_merchant_id ON processed_webhook_events(merchant_id);
CREATE INDEX idx_processed_webhook_events_event_type ON processed_webhook_events(event_type);
CREATE INDEX idx_processed_webhook_events_received_at ON processed_webhook_events(received_at);

-- Add foreign key constraint to merchants table if it exists
-- This ensures tenant isolation
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'merchants') THEN
        ALTER TABLE processed_webhook_events 
        ADD CONSTRAINT fk_processed_webhook_events_merchant 
        FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Add check constraint for processing_status
ALTER TABLE processed_webhook_events 
ADD CONSTRAINT chk_processing_status 
CHECK (processing_status IN ('processed', 'duplicate', 'failed', 'ignored'));

-- Add check constraint for provider
ALTER TABLE processed_webhook_events 
ADD CONSTRAINT chk_provider 
CHECK (provider IN ('razorpay', 'stripe', 'paypal'));

-- Add unique constraint to prevent duplicate processing of same event
-- This is crucial for idempotency
CREATE UNIQUE INDEX idx_processed_webhook_events_unique_event 
ON processed_webhook_events(provider, provider_event_id) 
WHERE processing_status != 'failed';

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_processed_webhook_events_updated_at 
    BEFORE UPDATE ON processed_webhook_events 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Additional improvements for related tables
-- ============================================

-- Ensure transactions table has proper columns and indexes for webhook processing
-- First, check if columns exist, add them if they don't
DO $$
BEGIN
    -- Add razorpay_order_id if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'transactions' AND column_name = 'razorpay_order_id'
    ) THEN
        ALTER TABLE transactions ADD COLUMN razorpay_order_id VARCHAR(255);
    END IF;
    
    -- Add razorpay_payment_id if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'transactions' AND column_name = 'razorpay_payment_id'
    ) THEN
        ALTER TABLE transactions ADD COLUMN razorpay_payment_id VARCHAR(255);
    END IF;
    
    -- Add failure_code if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'transactions' AND column_name = 'failure_code'
    ) THEN
        ALTER TABLE transactions ADD COLUMN failure_code VARCHAR(100);
    END IF;
END $$;

-- Create indexes for webhook processing
CREATE INDEX IF NOT EXISTS idx_transactions_razorpay_order_id ON transactions(razorpay_order_id);
CREATE INDEX IF NOT EXISTS idx_transactions_razorpay_payment_id ON transactions(razorpay_payment_id);
CREATE INDEX IF NOT EXISTS idx_transactions_customer_id ON transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_merchant_id ON transactions(merchant_id);

-- Fix conflict resolution for transactions table
-- This resolves the 409 Conflict error during webhook processing
ALTER TABLE transactions 
ALTER COLUMN id SET DEFAULT gen_random_uuid();

-- Ensure proper constraints
ALTER TABLE transactions 
ADD CONSTRAINT chk_transaction_status 
CHECK (status IN ('success', 'failed', 'pending', 'abandoned', 'refunded'));

-- Ensure recovery_cases table has proper indexes
CREATE INDEX IF NOT EXISTS idx_recovery_cases_transaction_id ON recovery_cases(transaction_id);
CREATE INDEX IF NOT EXISTS idx_recovery_cases_customer_id ON recovery_cases(customer_id);
CREATE INDEX IF NOT EXISTS idx_recovery_cases_status ON recovery_cases(status);
CREATE INDEX IF NOT EXISTS idx_recovery_cases_merchant_id ON recovery_cases(merchant_id);

-- ============================================
-- Enable Row Level Security (RLS) for Supabase
-- ============================================

ALTER TABLE processed_webhook_events ENABLE ROW LEVEL SECURITY;

-- Policy: Users can read webhook events for their own merchant
CREATE POLICY "Users can read own merchant webhook events"
ON processed_webhook_events FOR SELECT
USING (
    merchant_id IS NULL OR 
    merchant_id = auth.uid()::text OR
    EXISTS (
        SELECT 1 FROM merchants 
        WHERE merchants.id = processed_webhook_events.merchant_id
        AND merchants.user_id = auth.uid()::text
    )
);

-- Policy: Service role can insert webhook events (for webhooks)
CREATE POLICY "Service role can insert webhook events"
ON processed_webhook_events FOR INSERT
WITH CHECK (true);

-- Policy: Service role can update webhook events
CREATE POLICY "Service role can update webhook events"
ON processed_webhook_events FOR UPDATE
USING (true);

-- ============================================
-- Grant permissions
-- ============================================

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO anon, authenticated;

-- Grant select on table
GRANT SELECT ON processed_webhook_events TO anon, authenticated;

-- Grant insert, update on table for service operations
GRANT INSERT, UPDATE ON processed_webhook_events TO service_role;

-- ============================================
-- Comments for documentation
-- ============================================

COMMENT ON TABLE processed_webhook_events IS 'Stores processed webhook events for idempotency and audit trail';
COMMENT ON COLUMN processed_webhook_events.id IS 'Unique identifier for the webhook event record';
COMMENT ON COLUMN processed_webhook_events.merchant_id IS 'Foreign key to merchants table for tenant isolation';
COMMENT ON COLUMN processed_webhook_events.provider IS 'Payment provider (razorpay, stripe, paypal)';
COMMENT ON COLUMN processed_webhook_events.provider_event_id IS 'Event ID from the payment provider';
COMMENT ON COLUMN processed_webhook_events.event_type IS 'Type of webhook event (payment.captured, payment.failed, etc.)';
COMMENT ON COLUMN processed_webhook_events.received_at IS 'Timestamp when the webhook was received';
COMMENT ON COLUMN processed_webhook_events.processed_at IS 'Timestamp when the webhook was processed';
COMMENT ON COLUMN processed_webhook_events.processing_status IS 'Status of processing (processed, duplicate, failed, ignored)';

-- ============================================
-- Verification queries
-- ============================================

-- Check if table was created successfully
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'processed_webhook_events'
ORDER BY ordinal_position;

-- Check indexes
SELECT 
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'processed_webhook_events';

-- Check constraints
SELECT 
    conname as constraint_name,
    contype as constraint_type,
    pg_get_constraintdef(oid) as constraint_definition
FROM pg_constraint 
WHERE conrelid = 'processed_webhook_events'::regclass;

-- ============================================
-- Sample data insertion (for testing)
-- ============================================

-- Insert a sample webhook event record
INSERT INTO processed_webhook_events (
    id,
    merchant_id,
    provider,
    provider_event_id,
    event_type,
    received_at,
    processed_at,
    processing_status
) VALUES (
    gen_random_uuid(),
    'merchant_default',
    'razorpay',
    'evt_test_sample_123',
    'payment.captured',
    NOW(),
    NOW(),
    'processed'
) ON CONFLICT DO NOTHING;

-- ============================================
-- Cleanup
-- ============================================

-- Remove sample data after testing
-- DELETE FROM processed_webhook_events WHERE provider_event_id = 'evt_test_sample_123';