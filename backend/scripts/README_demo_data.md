# PayBack Demo Merchant Dataset

This directory contains scripts for creating and managing a realistic, isolated demo merchant dataset for PayBack.

## Overview

The demo merchant dataset is designed to:

1. **Populate the merchant dashboard** with realistic customer/payment/recovery history
2. **Provide meaningful customer history** for the existing PayBack ML model
3. **Generate realistic variation** across amounts, payment outcomes, failure reasons, and customer behavior
4. **Enable live demonstrations** of the PayBack workflow
5. **Maintain complete isolation** from existing merchants and production data
6. **Support ML inference** when new real payments are created for seeded customers

## Files

### `seed_demo_data.py`
Main script for generating the demo merchant dataset.

**Usage:**
```bash
# Create demo data (if it doesn't exist)
python backend/scripts/seed_demo_data.py

# Delete and recreate demo data
python backend/scripts/seed_demo_data.py --reset

# Validate existing demo data
python backend/scripts/seed_demo_data.py --validate

# Specify Supabase credentials explicitly
python backend/scripts/seed_demo_data.py --supabase-url <URL> --supabase-key <KEY>
```

**Features:**
- Creates exactly one demo merchant (`merchant_demo`)
- Generates 10-15 realistic customers with varied behavioral profiles
- Creates 15-30 historical transactions per customer (180-400 total)
- Produces varied transaction amounts across multiple ranges
- Generates realistic payment status distribution (~70% successful)
- Creates recovery cases with varied outcomes
- Generates action records and audit trails
- Deterministic generation using fixed seed (20260830)
- Idempotent operation (safe to run multiple times)
- Isolated from all existing merchants

### `validate_demo_data.py`
Comprehensive validation script for the demo dataset.

**Usage:**
```bash
python backend/scripts/validate_demo_data.py
```

**Validates:**
- Merchant existence and configuration
- Customer count and structure (10-15 customers)
- Transaction volume and distribution (15-30 per customer)
- Amount variation across ranges
- Payment status distribution
- Recovery case outcomes
- ML feature extraction compatibility
- ML inference compatibility
- Merchant isolation from other tenants
- Foreign key integrity
- Cross-tenant validation

### `test_ml_with_demo_data.py`
ML compatibility test script.

**Usage:**
```bash
python backend/scripts/test_ml_with_demo_data.py
```

**Tests:**
- Customer history calculation
- RecoveryContext creation
- ML feature extraction
- ML model inference
- Probability output validation

## Demo Merchant Structure

### Merchant
- **ID:** `merchant_demo`
- **Name:** `PayBack Demo Store`
- **Email:** `demo@payback.io`
- **Timezone:** `Asia/Kolkata`

### Customers
- **Count:** 12 (within 10-15 range)
- **Profiles:** Varied behavioral patterns
  - Highly Reliable (90% success rate)
  - Mixed Behavior (70% success rate)
  - Difficult Customer (50% success rate)
  - High-Value Customer (80% success rate, large transactions)
  - Repeat Recovery (60% success rate, multiple recoveries)
  - Newer Customer (75% success rate, shorter history)

### Transactions
- **Total:** ~240 (within 180-400 range)
- **Per Customer:** 15-30 transactions
- **Amount Ranges:**
  - ₹10-₹500 (low-value)
  - ₹500-₹2,000 (normal-value)
  - ₹2,000-₹10,000 (medium-value)
  - ₹10,000-₹25,000 (high-value)
  - ₹25,000-₹50,000 (very high-value)
  - ₹50,000-₹1,00,000 (premium-value)
- **Status Distribution:** ~70% successful, ~25% failed, ~5% other
- **Payment Methods:** UPI, Card, Net Banking, Wallet

### Recovery Cases
- **Created for:** Failed transactions
- **Outcomes:** Varied (recovered, failed, escalated, expired)
- **Action Records:** Historical recovery actions
- **Audit Trail:** Complete event history

## ML Compatibility

The seeded dataset is designed to work seamlessly with the existing PayBack ML pipeline:

### Feature Support
- ✅ `amount` - Transaction amounts with realistic variation
- ✅ `checkout_intent_score` - Uses documented placeholder (0.5)
- ✅ `customer_tenure_days` - Calculated from customer creation dates
- ✅ `previous_transactions` - Real historical transaction counts
- ✅ `historical_success_rate` - Calculated from transaction history
- ✅ `previous_failures` - Real failure counts
- ✅ `previous_recoveries` - Real recovery counts
- ✅ `days_since_failure` - Calculated from transaction timestamps
- ✅ `retry_count` - Configured in recovery cases
- ✅ `messages_sent` - Configured in recovery cases
- ✅ `opted_out` - Set for customers (currently all False)
- ✅ `high_value` - Derived from amount (≥₹10,000)
- ✅ `prior_recovery_rate` - Calculated from recovery history
- ✅ `customer_history_strength` - Log-scaled transaction count
- ✅ `payment_method` - Mapped to ML categories (upi, card, netbanking, wallet)
- ✅ `failure_type` - Mapped to ML categories (insufficient_funds, timeout, etc.)

### Payment Method Mapping
- Domain `net_banking` → ML `netbanking`
- Domain `emi` → ML `""` (no category)
- Domain `unknown` → ML `""` (no category)

### Failure Type Mapping
The script uses ML-compatible failure reasons:
- `insufficient_funds`
- `temporary_bank_error`
- `timeout`
- `expired_instrument`
- `authentication_failure`
- `unknown`

## Isolation and Safety

### Merchant Isolation
- All records use `merchant_demo` as merchant_id
- No overlap with `merchant_default` or other merchants
- Foreign key relationships maintained within demo merchant
- Cross-tenant validation performed

### Data Safety
- Reset operation only affects `merchant_demo`
- FK-safe deletion order (children before parents)
- Transaction rollback on failure
- No modification to existing merchants
- No external API calls during seeding
- No webhook triggers during seeding
- No email/SMS sending during seeding

### Idempotency
- Safe to run multiple times without duplication
- Checks for existing merchant before creation
- Uses `--reset` flag for clean recreation

## Environment Setup

The scripts require Supabase credentials:

```bash
export SUPABASE_URL="your-supabase-url"
export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
```

Or pass them as command-line arguments.

## Testing

Run the test suite for demo data seeding:

```bash
# Run demo data seeding tests
pytest backend/tests/test_demo_data_seeding.py -v

# Run all tests
pytest backend/tests -q
```

## Live Demo Preparation

After seeding, the following customers are suitable for live demonstrations:

### Demo Customer A (Strong History)
- **Profile:** Highly Reliable
- **Characteristics:** Many successful payments, few failures, high recovery rate
- **Suitable for:** Demonstrating normal recovery workflow

### Demo Customer B (Mixed History)
- **Profile:** Mixed Behavior
- **Characteristics:** Both successful and failed payments, some recoveries
- **Suitable for:** Demonstrating ML decision-making with varied history

### Demo Customer C (High-Value)
- **Profile:** High-Value Customer
- **Characteristics:** Fewer but larger transactions
- **Suitable for:** Demonstrating escalation and high-value policies

## Troubleshooting

### Issue: "Demo merchant already exists"
**Solution:** Use `--reset` flag to delete and recreate, or use `--validate` to check existing data.

### Issue: "Supabase access denied"
**Solution:** Verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set correctly and that migration 002 grants are applied.

### Issue: "ML model artifact not found"
**Solution:** Ensure `ml/artifacts/payback_xgboost.json` exists. The validation script will skip ML tests if artifacts are missing.

### Issue: "Customer count outside range"
**Solution:** This indicates a seeding problem. Use `--reset` to recreate the dataset.

## Verification

After seeding, verify the dataset:

```bash
# Validate the dataset
python backend/scripts/validate_demo_data.py

# Test ML compatibility
python backend/scripts/test_ml_with_demo_data.py

# Run automated tests
pytest backend/tests/test_demo_data_seeding.py -v
```

## Data Statistics

After successful seeding, expect approximately:

- **Customers:** 12
- **Transactions:** ~240
- **Recovery Cases:** ~60-80 (for failed transactions)
- **Action Records:** ~120-240
- **Audit Records:** ~300-480
- **Total Transaction Value:** ~₹8-15 lakhs
- **Recovered Value:** ~₹2-4 lakhs
- **Amount at Risk:** ~₹1-3 lakhs

## Integration with Live Workflow

The seeded dataset supports the live PayBack workflow:

1. **Seeded customer** has meaningful historical data
2. **New real transaction** is created via Razorpay
3. **ML model** uses seeded historical data for feature extraction
4. **Recovery probability** is calculated based on real customer history
5. **Decision engine** makes informed recovery decisions

This enables realistic demonstrations where the ML model has genuine historical context for decision-making.

## Maintenance

To update the demo dataset:

```bash
# Reset and regenerate with current configuration
python backend/scripts/seed_demo_data.py --reset

# Validate the updated dataset
python backend/scripts/validate_demo_data.py

# Test ML compatibility
python backend/scripts/test_ml_with_demo_data.py
```

## Notes

- The seed is deterministic (SEED = 20260830) for reproducibility
- All timestamps are spread over the last 6 months for realism
- Customer names and emails are realistic but not real personal data
- Phone numbers are realistic Indian formats but not real numbers
- Razorpay identifiers are left NULL for historical records
- No real payment links are created during seeding
- The dataset is completely offline with respect to external providers