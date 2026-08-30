"""
ML Inference Test with Demo Data

Tests the ML model compatibility with demo merchant customer histories.
This script validates that the existing ML pipeline can successfully process
the seeded customer data and generate recovery probabilities.

Usage:
    python backend/scripts/test_ml_with_demo_data.py

This script:
- Loads seeded customer data from the demo merchant
- Tests customer history calculation
- Tests RecoveryContext creation
- Tests ML feature extraction
- Tests ML model inference
- Validates probability outputs
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
script_dir = Path(__file__).resolve().parent
backend_root = script_dir.parent
sys.path.insert(0, str(backend_root))

# Set environment to use Supabase
os.environ["DATABASE_MODE"] = "supabase"

from app.config import settings
from app.models.domain import (
    Customer,
    RecoveryCase,
    Transaction,
    TransactionStatus,
)
from app.repositories.factory import get_repository_bundle
from app.core.probability import recovery_context_from_domain
from app.services.ml.xgboost_model import XGBoostRecoveryProbabilityModel
from app.services.ml.customer_history import compute_customer_history
from app.services.ml.feature_adapter import RecoveryFeatures, extract_recovery_features

# Demo merchant configuration
DEMO_MERCHANT_ID = "merchant_demo"


def test_customer_history_calculation():
    """Test customer history calculation for seeded customers."""
    print("=" * 60)
    print("TEST: Customer History Calculation")
    print("=" * 60)
    
    bundle = get_repository_bundle()
    customer_repo = bundle.customers
    transaction_repo = bundle.transactions
    recovery_repo = bundle.cases
    
    customers = customer_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=5)
    
    if not customers:
        print("[FAIL] No customers found for demo merchant")
        return False
    
    print(f"Found {len(customers)} customers")
    
    successful_calculations = 0
    
    for customer in customers:
        transactions = transaction_repo.list_by_customer(customer.id, limit=10)
        if not transactions:
            print(f"[WARN] No transactions for customer {customer.name}")
            continue
        
        reference_transaction = transactions[0]
        
        try:
            history = compute_customer_history(
                customer=customer,
                reference_dt=reference_transaction.created_at,
                transaction_repo=transaction_repo,
                case_repo=recovery_repo,
            )
            
            print(f"\nCustomer: {customer.name}")
            print(f"  Previous transactions: {history.previous_transactions}")
            print(f"  Historical success rate: {history.historical_success_rate:.2%}")
            print(f"  Previous failures: {history.previous_failures}")
            print(f"  Previous recoveries: {history.previous_recoveries}")
            print(f"  Prior recovery rate: {history.prior_recovery_rate:.2%}")
            print(f"  Customer history strength: {history.customer_history_strength:.2%}")
            print(f"  Customer tenure days: {history.customer_tenure_days:.1f}")
            
            # Validate ranges
            assert 0.0 <= history.historical_success_rate <= 1.0, "Success rate out of range"
            assert 0.0 <= history.prior_recovery_rate <= 1.0, "Prior recovery rate out of range"
            assert 0.0 <= history.customer_history_strength <= 1.0, "History strength out of range"
            assert history.previous_transactions >= 0, "Negative transaction count"
            
            successful_calculations += 1
            
        except Exception as e:
            print(f"[FAIL] Failed for customer {customer.name}: {e}")
            return False
    
    print(f"\n[PASS] Successfully calculated history for {successful_calculations}/{len(customers)} customers")
    return successful_calculations > 0


def test_recovery_context_creation():
    """Test RecoveryContext creation from seeded domain objects."""
    print("\n" + "=" * 60)
    print("TEST: RecoveryContext Creation")
    print("=" * 60)
    
    bundle = get_repository_bundle()
    customer_repo = bundle.customers
    transaction_repo = bundle.transactions
    recovery_repo = bundle.cases
    
    customers = customer_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=3)
    
    successful_contexts = 0
    
    for customer in customers:
        transactions = transaction_repo.list_by_customer(customer.id, limit=5)
        failed_transactions = [t for t in transactions if t.status == TransactionStatus.FAILED]
        
        if not failed_transactions:
            print(f"[WARN] No failed transactions for customer {customer.name}")
            continue
        
        transaction = failed_transactions[0]
        case = recovery_repo.get_by_transaction_id(transaction.id)
        
        if not case:
            print(f"[WARN] No recovery case for transaction {transaction.id}")
            continue
        
        try:
            context = recovery_context_from_domain(
                transaction=transaction,
                customer=customer,
                case=case,
                transaction_repo=transaction_repo,
                case_repo=recovery_repo,
            )
            
            print(f"\nCustomer: {customer.name}")
            print(f"  Amount: INR {context.amount:,.2f}")
            print(f"  Payment method: {context.payment_method_raw}")
            print(f"  Failure reason: {context.failure_reason_raw}")
            print(f"  Previous transactions: {context.previous_transactions}")
            print(f"  Historical success rate: {context.historical_success_rate:.2%}")
            print(f"  Previous failures: {context.previous_failures}")
            print(f"  Previous recoveries: {context.previous_recoveries}")
            print(f"  Days since failure: {context.days_since_failure:.1f}")
            print(f"  Customer tenure days: {context.customer_tenure_days:.1f}")
            
            # Validate context structure
            assert context.amount >= 0, "Negative amount"
            assert 0.0 <= context.historical_success_rate <= 1.0, "Success rate out of range"
            assert context.previous_transactions >= 0, "Negative transaction count"
            
            successful_contexts += 1
            
        except Exception as e:
            print(f"[FAIL] Failed for customer {customer.name}: {e}")
            return False
    
    print(f"\n[PASS] Successfully created context for {successful_contexts} customers")
    return successful_contexts > 0


def test_feature_extraction():
    """Test ML feature extraction from RecoveryContext."""
    print("\n" + "=" * 60)
    print("TEST: ML Feature Extraction")
    print("=" * 60)
    
    bundle = get_repository_bundle()
    customer_repo = bundle.customers
    transaction_repo = bundle.transactions
    recovery_repo = bundle.cases
    
    customers = customer_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=3)
    
    successful_extractions = 0
    
    for customer in customers:
        transactions = transaction_repo.list_by_customer(customer.id, limit=5)
        failed_transactions = [t for t in transactions if t.status == TransactionStatus.FAILED]
        
        if not failed_transactions:
            continue
        
        transaction = failed_transactions[0]
        case = recovery_repo.get_by_transaction_id(transaction.id)
        
        if not case:
            continue
        
        try:
            context = recovery_context_from_domain(
                transaction=transaction,
                customer=customer,
                case=case,
                transaction_repo=transaction_repo,
                case_repo=recovery_repo,
            )
            
            # Extract features using the feature adapter
            features = extract_recovery_features(
                amount=context.amount,
                checkout_intent_score=context.checkout_intent_score,
                customer_tenure_days=context.customer_tenure_days,
                previous_transactions=context.previous_transactions,
                historical_success_rate=context.historical_success_rate,
                previous_failures=context.previous_failures,
                previous_recoveries=context.previous_recoveries,
                days_since_failure=context.days_since_failure,
                retry_count=float(context.retry_count),
                messages_sent=float(context.messages_sent),
                opted_out=context.opted_out,
                payment_method=context.payment_method_raw,
                failure_type=context.failure_reason_raw,
            )
            
            print(f"\nCustomer: {customer.name}")
            print(f"  Features extracted successfully")
            print(f"  Amount: {features.amount}")
            print(f"  Payment method: {features.payment_method}")
            print(f"  Failure type: {features.failure_type}")
            print(f"  High value: {features.high_value}")
            print(f"  Customer history strength: {features.customer_history_strength:.3f}")
            
            # Validate feature structure
            assert features.amount >= 0, "Negative amount feature"
            assert 0.0 <= features.historical_success_rate <= 1.0, "Success rate out of range"
            assert features.payment_method in ["upi", "card", "netbanking", "wallet", ""], "Invalid payment method"
            assert features.failure_type in [
                "temporary_bank_error", "timeout", "insufficient_funds",
                "expired_instrument", "authentication_failure", "unknown"
            ], "Invalid failure type"
            
            successful_extractions += 1
            
        except Exception as e:
            print(f"[FAIL] Failed for customer {customer.name}: {e}")
            return False
    
    print(f"\n[PASS] Successfully extracted features for {successful_extractions} customers")
    return successful_extractions > 0


def test_ml_inference():
    """Test ML model inference with seeded customer contexts."""
    print("\n" + "=" * 60)
    print("TEST: ML Model Inference")
    print("=" * 60)
    
    # Check if ML model artifacts exist
    model_path = "ml/artifacts/payback_xgboost.json"
    if not os.path.exists(model_path):
        print(f"[WARN] ML model artifact not found at {model_path}")
        print("Skipping ML inference test")
        return True
    
    try:
        model = XGBoostRecoveryProbabilityModel()
        print("[PASS] ML model loaded successfully")
    except Exception as e:
        print(f"[FAIL] Failed to load ML model: {e}")
        return False
    
    bundle = get_repository_bundle()
    customer_repo = bundle.customers
    transaction_repo = bundle.transactions
    recovery_repo = bundle.cases
    
    customers = customer_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=5)
    
    successful_predictions = []
    
    for customer in customers:
        transactions = transaction_repo.list_by_customer(customer.id, limit=5)
        failed_transactions = [t for t in transactions if t.status == TransactionStatus.FAILED]
        
        if not failed_transactions:
            continue
        
        transaction = failed_transactions[0]
        case = recovery_repo.get_by_transaction_id(transaction.id)
        
        if not case:
            continue
        
        try:
            context = recovery_context_from_domain(
                transaction=transaction,
                customer=customer,
                case=case,
                transaction_repo=transaction_repo,
                case_repo=recovery_repo,
            )
            
            probability = model.predict(context)
            
            print(f"\nCustomer: {customer.name}")
            print(f"  Transaction amount: INR {transaction.amount:,.2f}")
            print(f"  Recovery probability: {probability:.2%}")
            
            # Validate probability range
            if not (0.0 <= probability <= 1.0):
                print(f"[FAIL] Invalid probability {probability} for customer {customer.name}")
                return False
            
            successful_predictions.append({
                "customer": customer.name,
                "amount": transaction.amount,
                "probability": probability,
            })
            
        except Exception as e:
            print(f"[FAIL] ML inference failed for customer {customer.name}: {e}")
            return False
    
    if not successful_predictions:
        print("[WARN] No successful predictions (no failed transactions with recovery cases)")
        return True
    
    print(f"\n[PASS] Successfully generated {len(successful_predictions)} predictions")
    
    # Show probability distribution
    probabilities = [p["probability"] for p in successful_predictions]
    avg_probability = sum(probabilities) / len(probabilities)
    min_probability = min(probabilities)
    max_probability = max(probabilities)
    
    print(f"\nProbability Statistics:")
    print(f"  Average: {avg_probability:.2%}")
    print(f"  Min: {min_probability:.2%}")
    print(f"  Max: {max_probability:.2%}")
    
    # Verify different customers produce different probabilities
    if len(set(probabilities)) > 1:
        print(f"[PASS] Different customers produce different probabilities (good variation)")
    else:
        print(f"[WARN] All customers produce the same probability (limited variation)")
    
    return True


def main():
    """Run all ML compatibility tests."""
    print("=" * 60)
    print("ML COMPATIBILITY TEST FOR DEMO DATA")
    print("=" * 60)
    
    tests = [
        ("Customer History Calculation", test_customer_history_calculation),
        ("RecoveryContext Creation", test_recovery_context_creation),
        ("ML Feature Extraction", test_feature_extraction),
        ("ML Model Inference", test_ml_inference),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"\n[FAIL] Test '{test_name}' failed with exception: {e}")
            results[test_name] = False
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, result in results.items():
        status = "[PASS] PASSED" if result else "[FAIL] FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("[PASS] ALL ML TESTS PASSED")
    else:
        print("[FAIL] SOME ML TESTS FAILED")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())