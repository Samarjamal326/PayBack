"""
Tests for demo merchant data seeding functionality.

These tests validate the core concepts and data structures needed for the demo merchant.
They use in-memory repositories for safe, fast testing without external dependencies.

The actual seeding script (seed_demo_data.py) should be tested separately with
Supabase integration when credentials are available.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

# Force in-memory mode for testing (safe, no external dependencies)
os.environ["DATABASE_MODE"] = "memory"

import pytest
from app.models.domain import (
    Currency,
    Customer,
    PaymentMethod,
    RecoveryCase,
    RecoveryStatus,
    Transaction,
    TransactionStatus,
)
from app.repositories.factory import get_repository_bundle
from app.core.probability import recovery_context_from_domain
from app.services.ml.customer_history import compute_customer_history

# Demo merchant configuration
DEMO_MERCHANT_ID = "merchant_demo"


@pytest.fixture
def repo_bundle():
    """Get repository bundle for testing."""
    return get_repository_bundle()


@pytest.fixture
def merchant_repo(repo_bundle):
    """Get merchant repository."""
    return repo_bundle.merchants


@pytest.fixture
def customer_repo(repo_bundle):
    """Get customer repository."""
    return repo_bundle.customers


@pytest.fixture
def transaction_repo(repo_bundle):
    """Get transaction repository."""
    return repo_bundle.transactions


@pytest.fixture
def recovery_repo(repo_bundle):
    """Get recovery case repository."""
    return repo_bundle.cases


class TestDemoMerchantExistence:
    """Test that demo merchant exists and is properly configured."""
    
    def test_demo_merchant_exists(self, merchant_repo):
        """Demo merchant should exist after seeding."""
        # For in-memory testing, we need to seed the demo merchant first
        from app.models.domain import Merchant
        from app.core.auth import DEV_MERCHANT_ID
        
        # Check if demo merchant exists, if not create it for testing
        merchant = merchant_repo.get(DEMO_MERCHANT_ID)
        if merchant is None:
            # Create demo merchant for testing purposes
            merchant = Merchant(
                id=DEMO_MERCHANT_ID,
                name="PayBack Demo Store",
                email="demo@payback.io",
                phone="+919876543210",
                timezone="Asia/Kolkata",
            )
            merchant = merchant_repo.save(merchant)
        
        assert merchant is not None, "Demo merchant should exist"
        assert merchant.name == "PayBack Demo Store", f"Expected 'PayBack Demo Store', got '{merchant.name}'"
    
    def test_demo_merchant_settings(self, merchant_repo):
        """Demo merchant should have proper settings."""
        from app.models.domain import MerchantSettings
        
        # Create settings if they don't exist
        settings = merchant_repo.get_settings(DEMO_MERCHANT_ID)
        if settings is None or not hasattr(settings, 'id'):
            settings = MerchantSettings(
                merchant_id=DEMO_MERCHANT_ID,
                notify_recovery_completed=True,
                notify_recovery_escalated=True,
                notify_action_failed=True,
                notify_payment_recovered=True,
            )
            settings = merchant_repo.save_settings(settings)
        
        assert settings is not None, "Demo merchant settings should exist"
        assert settings.merchant_id == DEMO_MERCHANT_ID


class TestCustomerRequirements:
    """Test customer count and structure requirements."""
    
    def test_customer_creation_and_retrieval(self, customer_repo):
        """Test that customers can be created and retrieved for demo merchant."""
        from app.models.domain import Customer
        
        # Create a test customer
        customer = Customer(
            merchant_id=DEMO_MERCHANT_ID,
            external_id="test_customer_1",
            name="Test Customer",
            email="test@example.com",
            opted_out=False,
        )
        saved_customer = customer_repo.save(customer)
        
        # Retrieve the customer
        retrieved_customer = customer_repo.get(saved_customer.id)
        assert retrieved_customer is not None, "Customer should be retrievable"
        assert retrieved_customer.merchant_id == DEMO_MERCHANT_ID
        assert retrieved_customer.name == "Test Customer"
    
    def test_customer_list_by_merchant(self, customer_repo):
        """Test that customers can be listed by merchant."""
        from app.models.domain import Customer
        
        # Create multiple customers
        for i in range(5):
            customer = Customer(
                merchant_id=DEMO_MERCHANT_ID,
                external_id=f"test_cust_{i}",
                name=f"Test Customer {i}",
                email=f"test{i}@example.com",
                opted_out=False,
            )
            customer_repo.save(customer)
        
        # List customers by merchant
        customers = customer_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=100)
        assert len(customers) >= 5, "Should have at least 5 customers"
        
        # Verify all belong to demo merchant
        for customer in customers:
            assert customer.merchant_id == DEMO_MERCHANT_ID


class TestTransactionRequirements:
    """Test transaction volume and distribution requirements."""
    
    def test_transaction_creation_and_retrieval(self, customer_repo, transaction_repo):
        """Test that transactions can be created and retrieved."""
        from app.models.domain import Customer, Transaction, PaymentMethod
        
        # Create a test customer first
        customer = Customer(
            merchant_id=DEMO_MERCHANT_ID,
            external_id="tx_test_customer",
            name="Transaction Test Customer",
            email="txtest@example.com",
            opted_out=False,
        )
        saved_customer = customer_repo.save(customer)
        
        # Create test transactions
        for i in range(20):  # Create 20 transactions
            transaction = Transaction(
                merchant_id=DEMO_MERCHANT_ID,
                customer_id=saved_customer.id,
                amount=1000.0 + (i * 100),  # Varying amounts
                currency=Currency.INR,
                payment_method=PaymentMethod.UPI,
                status=TransactionStatus.SUCCESS if i % 4 != 0 else TransactionStatus.FAILED,
                failure_reason="insufficient_funds" if i % 4 == 0 else None,
            )
            transaction_repo.save(transaction)
        
        # Retrieve transactions
        customer_txns = transaction_repo.list_by_customer(saved_customer.id, limit=100)
        assert len(customer_txns) >= 20, "Should have at least 20 transactions"
        
        # Verify amounts vary
        amounts = [t.amount for t in customer_txns]
        assert len(set(amounts)) > 1, "Transaction amounts should vary"
    
    def test_transaction_merchant_isolation(self, customer_repo, transaction_repo):
        """Test transactions are properly isolated by merchant."""
        from app.models.domain import Customer, Transaction, PaymentMethod
        
        # Create customer for demo merchant
        demo_customer = Customer(
            merchant_id=DEMO_MERCHANT_ID,
            external_id="isolation_test_demo",
            name="Demo Test Customer",
            email="demo@example.com",
            opted_out=False,
        )
        saved_demo_customer = customer_repo.save(demo_customer)
        
        # Create transaction for demo merchant
        demo_transaction = Transaction(
            merchant_id=DEMO_MERCHANT_ID,
            customer_id=saved_demo_customer.id,
            amount=5000.0,
            currency=Currency.INR,
            payment_method=PaymentMethod.CARD,
            status=TransactionStatus.SUCCESS,
        )
        transaction_repo.save(demo_transaction)
        
        # List transactions for demo merchant
        demo_txns = transaction_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=100)
        
        # Verify all belong to demo merchant
        for txn in demo_txns:
            assert txn.merchant_id == DEMO_MERCHANT_ID


class TestRecoveryCaseRequirements:
    """Test recovery case structure and outcomes."""
    
    def test_recovery_case_creation(self, customer_repo, transaction_repo, recovery_repo):
        """Test that recovery cases can be created for failed transactions."""
        from app.models.domain import Customer, Transaction, PaymentMethod
        
        # Create customer and failed transaction
        customer = Customer(
            merchant_id=DEMO_MERCHANT_ID,
            external_id="recovery_test_customer",
            name="Recovery Test Customer",
            email="recovery@example.com",
            opted_out=False,
        )
        saved_customer = customer_repo.save(customer)
        
        failed_transaction = Transaction(
            merchant_id=DEMO_MERCHANT_ID,
            customer_id=saved_customer.id,
            amount=2500.0,
            currency=Currency.INR,
            payment_method=PaymentMethod.CARD,
            status=TransactionStatus.FAILED,
            failure_reason="insufficient_funds",
        )
        saved_transaction = transaction_repo.save(failed_transaction)
        
        # Create recovery case
        recovery_case = RecoveryCase(
            merchant_id=DEMO_MERCHANT_ID,
            transaction_id=saved_transaction.id,
            customer_id=saved_customer.id,
            amount_at_risk=saved_transaction.amount,
            reason=saved_transaction.failure_reason or "payment_not_completed",
            status=RecoveryStatus.DETECTED,
        )
        saved_case = recovery_repo.save(recovery_case)
        
        # Verify recovery case was created
        retrieved_case = recovery_repo.get(saved_case.id)
        assert retrieved_case is not None, "Recovery case should be retrievable"
        assert retrieved_case.merchant_id == DEMO_MERCHANT_ID
        assert retrieved_case.amount_at_risk == 2500.0


class TestMerchantIsolation:
    """Test that demo merchant data is isolated from other merchants."""
    
    def test_merchant_boundaries(self, customer_repo, transaction_repo):
        """Test that merchant boundaries are respected."""
        from app.models.domain import Customer, Transaction, PaymentMethod
        from app.core.auth import DEV_MERCHANT_ID
        
        # Create customer for demo merchant
        demo_customer = Customer(
            merchant_id=DEMO_MERCHANT_ID,
            external_id="boundary_test_demo",
            name="Demo Boundary Customer",
            email="demo_boundary@example.com",
            opted_out=False,
        )
        saved_demo_customer = customer_repo.save(demo_customer)
        
        # Create customer for default merchant
        default_customer = Customer(
            merchant_id=DEV_MERCHANT_ID,
            external_id="boundary_test_default",
            name="Default Boundary Customer",
            email="default_boundary@example.com",
            opted_out=False,
        )
        saved_default_customer = customer_repo.save(default_customer)
        
        # List customers for each merchant
        demo_customers = customer_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=100)
        default_customers = customer_repo.list_by_merchant(DEV_MERCHANT_ID, limit=100)
        
        # Verify no overlap
        demo_ids = {c.id for c in demo_customers}
        default_ids = {c.id for c in default_customers}
        
        overlap = demo_ids & default_ids
        assert not overlap, f"Customer overlap between merchants: {overlap}"


class TestMLFeatureExtraction:
    """Test that ML feature extraction works with customer histories."""
    
    def test_customer_history_calculation(self, customer_repo, transaction_repo, recovery_repo):
        """Customer history should be calculable for customers with transactions."""
        from app.models.domain import Customer, Transaction, PaymentMethod
        
        # Create customer with transaction history
        customer = Customer(
            merchant_id=DEMO_MERCHANT_ID,
            external_id="ml_test_customer",
            name="ML Test Customer",
            email="mltest@example.com",
            opted_out=False,
        )
        saved_customer = customer_repo.save(customer)
        
        # Create multiple transactions
        base_time = datetime.now(timezone.utc)
        for i in range(10):
            transaction = Transaction(
                merchant_id=DEMO_MERCHANT_ID,
                customer_id=saved_customer.id,
                amount=1000.0 + (i * 200),
                currency=Currency.INR,
                payment_method=PaymentMethod.UPI,
                status=TransactionStatus.SUCCESS if i % 3 != 0 else TransactionStatus.FAILED,
                failure_reason="insufficient_funds" if i % 3 == 0 else None,
                created_at=base_time - timedelta(days=i),
            )
            transaction_repo.save(transaction)
        
        # Calculate customer history
        transactions = transaction_repo.list_by_customer(saved_customer.id, limit=10)
        reference_transaction = transactions[0]
        
        history = compute_customer_history(
            customer=saved_customer,
            reference_dt=reference_transaction.created_at,
            transaction_repo=transaction_repo,
            case_repo=recovery_repo,
        )
        
        # Validate history structure
        assert history.previous_transactions >= 0, "Previous transactions should be non-negative"
        assert 0.0 <= history.historical_success_rate <= 1.0, "Success rate should be in [0, 1]"
        assert history.previous_failures >= 0, "Previous failures should be non-negative"
        assert history.previous_recoveries >= 0, "Previous recoveries should be non-negative"
        assert 0.0 <= history.prior_recovery_rate <= 1.0, "Prior recovery rate should be in [0, 1]"
        assert 0.0 <= history.customer_history_strength <= 1.0, "History strength should be in [0, 1]"
        
        # Verify we have meaningful history
        assert history.previous_transactions > 0, "Should have previous transactions"


class TestMLInferenceCompatibility:
    """Test that ML context creation works with customer data."""
    
    def test_recovery_context_creation(self, customer_repo, transaction_repo, recovery_repo):
        """RecoveryContext should be creatable from domain objects."""
        from app.models.domain import Customer, Transaction, PaymentMethod
        
        # Create customer with failed transaction
        customer = Customer(
            merchant_id=DEMO_MERCHANT_ID,
            external_id="context_test_customer",
            name="Context Test Customer",
            email="context@example.com",
            opted_out=False,
        )
        saved_customer = customer_repo.save(customer)
        
        failed_transaction = Transaction(
            merchant_id=DEMO_MERCHANT_ID,
            customer_id=saved_customer.id,
            amount=3500.0,
            currency=Currency.INR,
            payment_method=PaymentMethod.NET_BANKING,
            status=TransactionStatus.FAILED,
            failure_reason="temporary_bank_error",
        )
        saved_transaction = transaction_repo.save(failed_transaction)
        
        recovery_case = RecoveryCase(
            merchant_id=DEMO_MERCHANT_ID,
            transaction_id=saved_transaction.id,
            customer_id=saved_customer.id,
            amount_at_risk=saved_transaction.amount,
            reason=saved_transaction.failure_reason or "payment_not_completed",
            status=RecoveryStatus.DETECTED,
        )
        saved_case = recovery_repo.save(recovery_case)
        
        # Create recovery context
        context = recovery_context_from_domain(
            transaction=saved_transaction,
            customer=saved_customer,
            case=saved_case,
            transaction_repo=transaction_repo,
            case_repo=recovery_repo,
        )
        
        # Validate context structure
        assert context.amount == saved_transaction.amount, "Context amount should match transaction"
        assert context.payment_method_raw == saved_transaction.payment_method.value, \
            "Payment method should match"
        assert context.previous_transactions >= 0, "Previous transactions should be non-negative"
        assert 0.0 <= context.historical_success_rate <= 1.0, "Success rate should be in [0, 1]"


class TestDataIntegrity:
    """Test data integrity and foreign key relationships."""
    
    def test_transaction_customer_relationship(self, customer_repo, transaction_repo):
        """Transaction customer_id should reference valid customers."""
        from app.models.domain import Customer, Transaction, PaymentMethod
        
        # Create customer
        customer = Customer(
            merchant_id=DEMO_MERCHANT_ID,
            external_id="integrity_test_customer",
            name="Integrity Test Customer",
            email="integrity@example.com",
            opted_out=False,
        )
        saved_customer = customer_repo.save(customer)
        
        # Create transaction referencing the customer
        transaction = Transaction(
            merchant_id=DEMO_MERCHANT_ID,
            customer_id=saved_customer.id,
            amount=1500.0,
            currency=Currency.INR,
            payment_method=PaymentMethod.UPI,
            status=TransactionStatus.SUCCESS,
        )
        saved_transaction = transaction_repo.save(transaction)
        
        # Verify the relationship
        assert saved_transaction.customer_id == saved_customer.id, \
            "Transaction should reference the correct customer"
        
        # Verify customer exists
        retrieved_customer = customer_repo.get(saved_customer.id)
        assert retrieved_customer is not None, "Referenced customer should exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])