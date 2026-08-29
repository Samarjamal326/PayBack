-- PayBack Phase 4.1 Database Migration
-- Add Razorpay integration fields to transactions table for proper payment flow

-- Add Razorpay fields to transactions table
ALTER TABLE transactions 
ADD COLUMN IF NOT EXISTS failure_code TEXT,
ADD COLUMN IF NOT EXISTS razorpay_order_id TEXT,
ADD COLUMN IF NOT EXISTS razorpay_payment_id TEXT;

-- Add indexes for Razorpay fields to improve webhook lookup performance
CREATE INDEX IF NOT EXISTS idx_transactions_razorpay_order ON transactions(razorpay_order_id);
CREATE INDEX IF NOT EXISTS idx_transactions_razorpay_payment ON transactions(razorpay_payment_id);

-- Add unique constraint on razorpay_order_id to prevent duplicate Razorpay orders
-- Note: Made nullable since not all transactions may have Razorpay integration
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_razorpay_order ON transactions(razorpay_order_id) WHERE razorpay_order_id IS NOT NULL;
