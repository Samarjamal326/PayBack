"""
PayBack Demo Data Validation Script

Performs comprehensive validation of the demo merchant dataset to ensure it meets
all requirements for ML compatibility, data integrity, and merchant isolation.

Usage:
    python backend/scripts/validate_demo_data.py

This script validates:
- Merchant existence and configuration
- Customer count and structure (10-15 customers)
- Transaction volume and distribution (15-30 per customer)
- Amount variation across ranges
- Payment status distribution
- Recovery case outcomes
- ML feature extraction compatibility
- ML inference compatibility
- Merchant isolation
- Foreign key integrity
- Cross-tenant validation
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

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
    RecoveryStatus,
    Transaction,
    TransactionStatus,
)
from app.repositories.factory import get_repository_bundle
from app.core.probability import recovery_context_from_domain
from app.services.ml.xgboost_model import XGBoostRecoveryProbabilityModel
from app.services.ml.customer_history import compute_customer_history

# Demo merchant configuration
DEMO_MERCHANT_ID = "merchant_demo"
DEMO_MERCHANT_NAME = "PayBack Demo Store"


class DemoDataValidator:
    """Comprehensive validator for demo merchant dataset."""
    
    def __init__(self):
        # Use repository bundle directly with Supabase configuration
        bundle = get_repository_bundle()
        self.bundle = bundle
        
        self.merchant_repo = self.bundle.merchants
        self.customer_repo = self.bundle.customers
        self.transaction_repo = self.bundle.transactions
        self.recovery_repo = self.bundle.cases
        
        self.validation_results: Dict[str, Any] = {}
        self.errors = []
        self.warnings = []
    
    def log_success(self, message: str) -> None:
        """Log a successful validation."""
        print(f"[PASS] {message}")
    
    def log_error(self, message: str) -> None:
        """Log a validation error."""
        print(f"[FAIL] {message}")
        self.errors.append(message)
    
    def log_warning(self, message: str) -> None:
        """Log a validation warning."""
        print(f"[WARN] {message}")
        self.warnings.append(message)
    
    def log_info(self, message: str) -> None:
        """Log an informational message."""
        print(f"[INFO] {message}")
    
    def validate_merchant(self) -> bool:
        """Validate demo merchant existence and configuration."""
        print("\n" + "=" * 60)
        print("VALIDATING DEMO MERCHANT")
        print("=" * 60)
        
        merchant = self.merchant_repo.get(DEMO_MERCHANT_ID)
        
        if not merchant:
            self.log_error(f"Demo merchant '{DEMO_MERCHANT_ID}' does not exist")
            return False
        
        self.log_success(f"Demo merchant exists: {DEMO_MERCHANT_ID}")
        
        if merchant.name != DEMO_MERCHANT_NAME:
            self.log_error(f"Merchant name mismatch: expected '{DEMO_MERCHANT_NAME}', got '{merchant.name}'")
            return False
        
        self.log_success(f"Merchant name correct: {merchant.name}")
        
        settings = self.merchant_repo.get_settings(DEMO_MERCHANT_ID)
        if not settings:
            self.log_error("Merchant settings not found")
            return False
        
        self.log_success("Merchant settings exist")
        
        self.validation_results["merchant_exists"] = True
        self.validation_results["merchant_name"] = merchant.name
        return True
    
    def validate_customers(self) -> bool:
        """Validate customer count and structure."""
        print("\n" + "=" * 60)
        print("VALIDATING CUSTOMERS")
        print("=" * 60)
        
        customers = self.customer_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=100)
        customer_count = len(customers)
        
        self.validation_results["customer_count"] = customer_count
        
        if not (10 <= customer_count <= 15):
            self.log_error(f"Customer count {customer_count} outside required range [10, 15]")
            return False
        
        self.log_success(f"Customer count within range: {customer_count}")
        
        # Check all customers belong to demo merchant
        invalid_customers = [c for c in customers if c.merchant_id != DEMO_MERCHANT_ID]
        if invalid_customers:
            self.log_error(f"{len(invalid_customers)} customers belong to wrong merchant")
            return False
        
        self.log_success("All customers belong to demo merchant")
        
        # Check for artificial names
        artificial_patterns = ["Customer", "Test", "Demo", "User"]
        artificial_names = [c.name for c in customers if any(p in c.name for p in artificial_patterns)]
        if artificial_names:
            self.log_warning(f"Found potentially artificial names: {artificial_names}")
        
        # Check email uniqueness
        emails = [c.email for c in customers if c.email]
        if len(emails) != len(set(emails)):
            self.log_error("Duplicate email addresses found")
            return False
        
        self.log_success("Customer emails are unique")
        
        return True
    
    def validate_transactions(self) -> bool:
        """Validate transaction volume and distribution."""
        print("\n" + "=" * 60)
        print("VALIDATING TRANSACTIONS")
        print("=" * 60)
        
        transactions = self.transaction_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=1000)
        transaction_count = len(transactions)
        
        self.validation_results["transaction_count"] = transaction_count
        
        if not (180 <= transaction_count <= 400):
            self.log_error(f"Transaction count {transaction_count} outside expected range [180, 400]")
            return False
        
        self.log_success(f"Transaction count within range: {transaction_count}")
        
        # Check transactions per customer
        customers = self.customer_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=100)
        txn_per_customer = []
        
        for customer in customers:
            customer_txns = self.transaction_repo.list_by_customer(customer.id, limit=100)
            txn_count = len(customer_txns)
            txn_per_customer.append(txn_count)
            
            if not (15 <= txn_count <= 30):
                self.log_error(f"Customer {customer.name} has {txn_count} transactions, expected [15, 30]")
                return False
        
        self.log_success(f"Transactions per customer within range: min={min(txn_per_customer)}, max={max(txn_per_customer)}")
        
        self.validation_results["min_transactions_per_customer"] = min(txn_per_customer)
        self.validation_results["max_transactions_per_customer"] = max(txn_per_customer)
        
        # Check amount variation
        amounts = [t.amount for t in transactions]
        has_low_value = any(10 <= amt <= 500 for amt in amounts)
        has_normal_value = any(500 < amt <= 2000 for amt in amounts)
        has_high_value = any(amt > 10000 for amt in amounts)
        
        if not has_low_value:
            self.log_warning("No low-value transactions found (₹10-₹500)")
        else:
            self.log_success("Low-value transactions present")
        
        if not has_normal_value:
            self.log_warning("No normal-value transactions found (₹500-₹2,000)")
        else:
            self.log_success("Normal-value transactions present")
        
        if not has_high_value:
            self.log_warning("No high-value transactions found (>₹10,000)")
        else:
            self.log_success("High-value transactions present")
        
        # Check status distribution
        success_count = sum(1 for t in transactions if t.status == TransactionStatus.SUCCESS)
        failed_count = sum(1 for t in transactions if t.status == TransactionStatus.FAILED)
        success_rate = success_count / transaction_count if transaction_count > 0 else 0
        
        self.validation_results["successful_transactions"] = success_count
        self.validation_results["failed_transactions"] = failed_count
        self.validation_results["success_rate"] = success_rate
        
        if not (0.60 <= success_rate <= 0.80):
            self.log_warning(f"Success rate {success_rate:.2%} outside expected range [60%, 80%]")
        else:
            self.log_success(f"Success rate within range: {success_rate:.2%}")
        
        # Check merchant isolation
        invalid_txns = [t for t in transactions if t.merchant_id != DEMO_MERCHANT_ID]
        if invalid_txns:
            self.log_error(f"{len(invalid_txns)} transactions belong to wrong merchant")
            return False
        
        self.log_success("All transactions belong to demo merchant")
        
        return True
    
    def validate_recovery_cases(self) -> bool:
        """Validate recovery case structure and outcomes."""
        print("\n" + "=" * 60)
        print("VALIDATING RECOVERY CASES")
        print("=" * 60)
        
        recovery_cases = self.recovery_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=1000)
        recovery_count = len(recovery_cases)
        
        self.validation_results["recovery_case_count"] = recovery_count
        
        # Check recovery cases for failed transactions
        transactions = self.transaction_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=1000)
        failed_transactions = [t for t in transactions if t.status == TransactionStatus.FAILED]
        
        recovery_count_for_failed = 0
        for transaction in failed_transactions:
            case = self.recovery_repo.get_by_transaction_id(transaction.id)
            if case:
                recovery_count_for_failed += 1
        
        recovery_rate = recovery_count_for_failed / len(failed_transactions) if failed_transactions else 0
        
        if recovery_rate < 0.8:
            self.log_warning(f"Only {recovery_rate:.2%} of failed transactions have recovery cases")
        else:
            self.log_success(f"Recovery case coverage: {recovery_rate:.2%}")
        
        # Check outcome variation
        outcomes = [case.outcome for case in recovery_cases if case.outcome]
        unique_outcomes = set(outcomes)
        
        if len(unique_outcomes) < 2:
            self.log_warning(f"Limited outcome variation: {unique_outcomes}")
        else:
            self.log_success(f"Outcome variation present: {unique_outcomes}")
        
        # Count specific outcomes
        recovered_count = sum(1 for o in outcomes if o == "recovered")
        escalated_count = sum(1 for o in outcomes if o == "escalated")
        
        self.validation_results["recovered_count"] = recovered_count
        self.validation_results["escalated_count"] = escalated_count
        
        # Check merchant isolation
        invalid_cases = [c for c in recovery_cases if c.merchant_id != DEMO_MERCHANT_ID]
        if invalid_cases:
            self.log_error(f"{len(invalid_cases)} recovery cases belong to wrong merchant")
            return False
        
        self.log_success("All recovery cases belong to demo merchant")
        
        return True
    
    def validate_ml_features(self) -> bool:
        """Validate ML feature extraction compatibility."""
        print("\n" + "=" * 60)
        print("VALIDATING ML FEATURE EXTRACTION")
        print("=" * 60)
        
        customers = self.customer_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=5)
        successful_history = 0
        
        for customer in customers:
            transactions = self.transaction_repo.list_by_customer(customer.id, limit=10)
            if not transactions:
                continue
            
            reference_transaction = transactions[0]
            
            try:
                history = compute_customer_history(
                    customer=customer,
                    reference_dt=reference_transaction.created_at,
                    transaction_repo=self.transaction_repo,
                    case_repo=self.recovery_repo,
                )
                
                # Validate history structure
                assert history.previous_transactions >= 0
                assert 0.0 <= history.historical_success_rate <= 1.0
                assert history.previous_failures >= 0
                assert history.previous_recoveries >= 0
                assert 0.0 <= history.prior_recovery_rate <= 1.0
                assert 0.0 <= history.customer_history_strength <= 1.0
                
                successful_history += 1
                
            except Exception as e:
                self.log_error(f"Feature extraction failed for customer {customer.id}: {e}")
                return False
        
        if successful_history == 0:
            self.log_error("No successful customer history calculations")
            return False
        
        self.log_success(f"ML feature extraction successful for {successful_history} customers")
        
        # Check for meaningful history
        customers_with_history = 0
        for customer in customers:
            transactions = self.transaction_repo.list_by_customer(customer.id, limit=10)
            if not transactions:
                continue
            
            reference_transaction = transactions[0]
            history = compute_customer_history(
                customer=customer,
                reference_dt=reference_transaction.created_at,
                transaction_repo=self.transaction_repo,
                case_repo=self.recovery_repo,
            )
            
            if history.previous_transactions > 0:
                customers_with_history += 1
        
        if customers_with_history == 0:
            self.log_warning("No customers with meaningful transaction history")
        else:
            self.log_success(f"{customers_with_history} customers have meaningful history")
        
        return True
    
    def validate_ml_inference(self) -> bool:
        """Validate ML inference compatibility."""
        print("\n" + "=" * 60)
        print("VALIDATING ML INFERENCE")
        print("=" * 60)
        
        # Check if ML model artifacts exist
        model_path = "ml/artifacts/payback_xgboost.json"
        if not os.path.exists(model_path):
            self.log_warning("ML model artifact not found, skipping inference validation")
            return True
        
        customers = self.customer_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=3)
        
        try:
            model = XGBoostRecoveryProbabilityModel()
        except Exception as e:
            self.log_error(f"Failed to load ML model: {e}")
            return False
        
        successful_predictions = 0
        
        for customer in customers:
            transactions = self.transaction_repo.list_by_customer(customer.id, limit=5)
            failed_transactions = [t for t in transactions if t.status == TransactionStatus.FAILED]
            
            if not failed_transactions:
                continue
            
            transaction = failed_transactions[0]
            case = self.recovery_repo.get_by_transaction_id(transaction.id)
            
            if not case:
                continue
            
            try:
                context = recovery_context_from_domain(
                    transaction=transaction,
                    customer=customer,
                    case=case,
                    transaction_repo=self.transaction_repo,
                    case_repo=self.recovery_repo,
                )
                
                probability = model.predict(context)
                
                if not (0.0 <= probability <= 1.0):
                    self.log_error(f"Invalid probability {probability} for customer {customer.id}")
                    return False
                
                successful_predictions += 1
                
            except Exception as e:
                self.log_error(f"ML inference failed for customer {customer.id}: {e}")
                return False
        
        if successful_predictions == 0:
            self.log_warning("No successful ML predictions (no failed transactions with recovery cases)")
            return True
        
        self.log_success(f"ML inference successful for {successful_predictions} predictions")
        
        return True
    
    def validate_merchant_isolation(self) -> bool:
        """Validate merchant isolation from other tenants."""
        print("\n" + "=" * 60)
        print("VALIDATING MERCHANT ISOLATION")
        print("=" * 60)
        
        # Check customer isolation
        demo_customers = self.customer_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=100)
        demo_customer_ids = {c.id for c in demo_customers}
        
        default_customers = self.customer_repo.list_by_merchant("merchant_default", limit=1000)
        default_customer_ids = {c.id for c in default_customers}
        
        customer_overlap = demo_customer_ids & default_customer_ids
        if customer_overlap:
            self.log_error(f"Customer overlap between merchants: {customer_overlap}")
            return False
        
        self.log_success("No customer overlap with merchant_default")
        
        # Check transaction isolation
        demo_transactions = self.transaction_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=1000)
        demo_transaction_ids = {t.id for t in demo_transactions}
        
        default_transactions = self.transaction_repo.list_by_merchant("merchant_default", limit=1000)
        default_transaction_ids = {t.id for t in default_transactions}
        
        transaction_overlap = demo_transaction_ids & default_transaction_ids
        if transaction_overlap:
            self.log_error(f"Transaction overlap between merchants: {transaction_overlap}")
            return False
        
        self.log_success("No transaction overlap with merchant_default")
        
        self.validation_results["merchant_isolation_valid"] = True
        
        return True
    
    def validate_foreign_keys(self) -> bool:
        """Validate foreign key integrity."""
        print("\n" + "=" * 60)
        print("VALIDATING FOREIGN KEY INTEGRITY")
        print("=" * 60)
        
        # Check transaction-customer FK
        transactions = self.transaction_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=100)
        customer_ids = {c.id for c in self.customer_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=100)}
        
        invalid_txns = [t for t in transactions if t.customer_id not in customer_ids]
        if invalid_txns:
            self.log_error(f"{len(invalid_txns)} transactions reference invalid customers")
            return False
        
        self.log_success("All transaction-customer foreign keys valid")
        
        # Check recovery-transaction FK
        recovery_cases = self.recovery_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=100)
        transaction_ids = {t.id for t in self.transaction_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=1000)}
        
        invalid_cases = [c for c in recovery_cases if c.transaction_id not in transaction_ids]
        if invalid_cases:
            self.log_error(f"{len(invalid_cases)} recovery cases reference invalid transactions")
            return False
        
        self.log_success("All recovery-transaction foreign keys valid")
        
        # Check recovery-customer FK
        invalid_customer_cases = [c for c in recovery_cases if c.customer_id not in customer_ids]
        if invalid_customer_cases:
            self.log_error(f"{len(invalid_customer_cases)} recovery cases reference invalid customers")
            return False
        
        self.log_success("All recovery-customer foreign keys valid")
        
        return True
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate comprehensive summary report."""
        print("\n" + "=" * 60)
        print("SUMMARY REPORT")
        print("=" * 60)
        
        # Calculate additional metrics
        transactions = self.transaction_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=1000)
        total_value = sum(t.amount for t in transactions)
        
        recovery_cases = self.recovery_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=1000)
        total_recovered = sum(c.amount_recovered for c in recovery_cases)
        total_at_risk = sum(c.amount_at_risk for c in recovery_cases)
        
        # Find customer with highest lifetime value
        customers = self.customer_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=100)
        customer_ltv = []
        
        for customer in customers:
            customer_txns = self.transaction_repo.list_by_customer(customer.id, limit=100)
            successful_txns = [t for t in customer_txns if t.status == TransactionStatus.SUCCESS]
            ltv = sum(t.amount for t in successful_txns)
            customer_ltv.append((customer.name, ltv))
        
        customer_ltv.sort(key=lambda x: x[1], reverse=True)
        highest_ltv_customer = customer_ltv[0] if customer_ltv else ("None", 0)
        
        summary = {
            "demo_merchant_id": DEMO_MERCHANT_ID,
            "demo_merchant_name": DEMO_MERCHANT_NAME,
            "validation_passed": len(self.errors) == 0,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "customer_count": self.validation_results.get("customer_count", 0),
            "transaction_count": self.validation_results.get("transaction_count", 0),
            "recovery_case_count": self.validation_results.get("recovery_case_count", 0),
            "successful_transactions": self.validation_results.get("successful_transactions", 0),
            "failed_transactions": self.validation_results.get("failed_transactions", 0),
            "recovered_count": self.validation_results.get("recovered_count", 0),
            "escalated_count": self.validation_results.get("escalated_count", 0),
            "total_transaction_value": total_value,
            "total_recovered_value": total_recovered,
            "total_amount_at_risk": total_at_risk,
            "highest_ltv_customer": highest_ltv_customer[0],
            "highest_ltv_value": highest_ltv_customer[1],
            "merchant_isolation_valid": self.validation_results.get("merchant_isolation_valid", False),
        }
        
        # Print summary
        for key, value in summary.items():
            if isinstance(value, float):
                print(f"{key}: {value:,.2f}" if "value" in key or "rate" in key else f"{key}: {value:.4f}")
            else:
                print(f"{key}: {value}")
        
        return summary
    
    def run_all_validations(self) -> bool:
        """Run all validation checks."""
        print("=" * 60)
        print("PAYBACK DEMO DATA VALIDATION")
        print("=" * 60)
        
        validations = [
            self.validate_merchant,
            self.validate_customers,
            self.validate_transactions,
            self.validate_recovery_cases,
            self.validate_ml_features,
            self.validate_ml_inference,
            self.validate_merchant_isolation,
            self.validate_foreign_keys,
        ]
        
        all_passed = True
        for validation in validations:
            try:
                if not validation():
                    all_passed = False
            except Exception as e:
                self.log_error(f"Validation failed with exception: {e}")
                all_passed = False
        
        # Generate summary
        summary = self.generate_summary_report()
        
        # Print final result
        print("\n" + "=" * 60)
        if all_passed and len(self.errors) == 0:
            print("[PASS] ALL VALIDATIONS PASSED")
        else:
            print("[FAIL] VALIDATIONS FAILED")
        print("=" * 60)
        
        if self.warnings:
            print(f"\nWarnings: {len(self.warnings)}")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        if self.errors:
            print(f"\nErrors: {len(self.errors)}")
            for error in self.errors:
                print(f"  - {error}")
        
        return all_passed and len(self.errors) == 0


def main():
    """Main entry point."""
    validator = DemoDataValidator()
    success = validator.run_all_validations()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()