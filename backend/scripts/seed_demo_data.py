"""
PayBack Demo Merchant Data Seeder

Creates a realistic, deterministic historical dataset for ONE dedicated demo merchant.
This dataset is designed to be ML-compatible and provide meaningful customer history
for the existing PayBack recovery probability model.

Usage:
    python backend/scripts/seed_demo_data.py              # Create if not exists
    python backend/scripts/seed_demo_data.py --reset      # Delete and recreate
    python backend/scripts/seed_demo_data.py --validate   # Validate existing data

Key Requirements:
- Exactly one demo merchant (merchant_demo)
- 10-15 realistic customers with substantial transaction history
- 15-30 historical transactions per customer
- Varied amounts, payment methods, failure reasons, recovery outcomes
- Customer behavioral profiles (reliable, mixed, difficult, high-value, etc.)
- Complete isolation from existing merchants
- Deterministic generation with fixed seed
- ML-compatible features for existing model
"""

import argparse
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
script_dir = Path(__file__).resolve().parent
backend_root = script_dir.parent
project_root = backend_root.parent
sys.path.insert(0, str(backend_root))

# Set environment to use Supabase
os.environ["DATABASE_MODE"] = "supabase"

from app.config import settings
from app.models.domain import (
    ActionRecord,
    AuditRecord,
    AuditEventType,
    Currency,
    Customer,
    EscalateReason,
    Merchant,
    MerchantSettings,
    MessageDeliveryRecord,
    MessageChannel,
    MessageStatus,
    Notification,
    NotificationType,
    PaymentMethod,
    Policy,
    RecoveryAction,
    RecoveryCase,
    RecoveryDecision,
    RecoveryOutcome,
    RecoveryStatus,
    StopReason,
    Transaction,
    TransactionStatus,
)
from app.repositories.supabase import (
    SupabaseActionRecordRepository,
    SupabaseAuditRecordRepository,
    SupabaseClient,
    SupabaseCustomerRepository,
    SupabaseMerchantRepository,
    SupabaseMessageDeliveryRepository,
    SupabaseNotificationRepository,
    SupabasePolicyRepository,
    SupabaseRecoveryCaseRepository,
    SupabaseTransactionRepository,
)


# ============================================================================
# CONFIGURATION
# ============================================================================

DEMO_MERCHANT_ID = "merchant_demo"
DEMO_MERCHANT_NAME = "PayBack Demo Store"
SEED = 20260830  # Fixed seed for deterministic generation

# Customer configuration
NUM_CUSTOMERS = 12  # Within 10-15 range
MIN_TRANSACTIONS_PER_CUSTOMER = 15
MAX_TRANSACTIONS_PER_CUSTOMER = 30

# Transaction amount ranges (INR)
AMOUNT_RANGES = [
    (10, 500),       # Low-value
    (500, 2000),     # Normal-value
    (2000, 10000),   # Medium-value
    (10000, 25000),  # High-value
    (25000, 50000),  # Very high-value
    (50000, 100000), # Premium-value
]

# ML-compatible failure reasons (mapped to failure_type categories)
FAILURE_REASONS = [
    "insufficient_funds",
    "temporary_bank_error",
    "timeout",
    "expired_instrument",
    "authentication_failure",
    "card_declined",
    "bank_error",
    "network_error",
]

# Payment methods (compatible with ML categories)
PAYMENT_METHODS = [
    PaymentMethod.UPI,
    PaymentMethod.CARD,
    PaymentMethod.NET_BANKING,
    PaymentMethod.WALLET,
]

# Transaction status distribution (weighted)
STATUS_WEIGHTS = {
    TransactionStatus.SUCCESS: 0.70,    # 70% successful
    TransactionStatus.FAILED: 0.25,     # 25% failed
    TransactionStatus.PENDING: 0.03,    # 3% pending
    TransactionStatus.ABANDONED: 0.02, # 2% abandoned
}

# Recovery outcome distribution for failed transactions
RECOVERY_OUTCOME_WEIGHTS = {
    RecoveryOutcome.RECOVERED: 0.50,    # 50% recovered
    RecoveryOutcome.FAILED: 0.25,      # 25% failed recovery
    RecoveryOutcome.ESCALATED: 0.15,   # 15% escalated
    RecoveryOutcome.EXPIRED: 0.10,     # 10% expired
}

# Customer behavioral profiles
CUSTOMER_PROFILES = [
    {
        "name": "Highly Reliable",
        "success_rate": 0.90,
        "recovery_rate": 0.80,
        "avg_transactions": 25,
        "amount_preference": "normal",
    },
    {
        "name": "Mixed Behavior",
        "success_rate": 0.70,
        "recovery_rate": 0.60,
        "avg_transactions": 20,
        "amount_preference": "mixed",
    },
    {
        "name": "Difficult Customer",
        "success_rate": 0.50,
        "recovery_rate": 0.30,
        "avg_transactions": 18,
        "amount_preference": "low",
    },
    {
        "name": "High-Value Customer",
        "success_rate": 0.80,
        "recovery_rate": 0.70,
        "avg_transactions": 15,
        "amount_preference": "high",
    },
    {
        "name": "Repeat Recovery",
        "success_rate": 0.60,
        "recovery_rate": 0.50,
        "avg_transactions": 22,
        "amount_preference": "mixed",
    },
    {
        "name": "Newer Customer",
        "success_rate": 0.75,
        "recovery_rate": 0.65,
        "avg_transactions": 16,
        "amount_preference": "normal",
    },
]

# Realistic customer names
CUSTOMER_NAMES = [
    "Arjun Sharma", "Priya Patel", "Rahul Kumar", "Ananya Singh",
    "Vikram Reddy", "Sneha Gupta", "Karthik Nair", "Divya Menon",
    "Rajesh Iyer", "Kavitha Rao", "Suresh Verma", "Meera Joshi",
]


# ============================================================================
# DATA GENERATION HELPERS
# ============================================================================

def weighted_choice(items: dict[Any, float]) -> Any:
    """Choose an item from a weighted dictionary."""
    items_list = list(items.items())
    choices, weights = zip(*items_list)
    return random.choices(choices, weights=weights, k=1)[0]


def generate_amount(preference: str) -> float:
    """Generate transaction amount based on preference profile."""
    if preference == "low":
        range_idx = random.choice([0, 1])
    elif preference == "high":
        range_idx = random.choice([3, 4, 5])
    elif preference == "normal":
        range_idx = random.choice([1, 2])
    else:  # mixed
        range_idx = random.randint(0, 5)
    
    min_amt, max_amt = AMOUNT_RANGES[range_idx]
    return round(random.uniform(min_amt, max_amt), 2)


def generate_timestamp(base_time: datetime, days_ago_min: int, days_ago_max: int) -> datetime:
    """Generate a random timestamp within a range."""
    days_ago = random.randint(days_ago_min, days_ago_max)
    hours_offset = random.randint(0, 23)
    minutes_offset = random.randint(0, 59)
    return base_time - timedelta(days=days_ago, hours=hours_offset, minutes=minutes_offset)


def generate_customer_email(name: str) -> str:
    """Generate realistic email from customer name."""
    name_parts = name.lower().split()
    if len(name_parts) >= 2:
        return f"{name_parts[0]}.{name_parts[1]}@example.com"
    return f"{name_parts[0]}@example.com"


def generate_customer_phone() -> str:
    """Generate realistic Indian phone number."""
    return f"+91{random.randint(7000000000, 9999999999)}"


# ============================================================================
# SEED DATA GENERATOR
# ============================================================================

class DemoDataGenerator:
    """Generates demo merchant data with deterministic randomness."""
    
    def __init__(self, client: SupabaseClient):
        self.client = client
        random.seed(SEED)
        
        # Initialize repositories
        self.merchant_repo = SupabaseMerchantRepository(client)
        self.customer_repo = SupabaseCustomerRepository(client)
        self.transaction_repo = SupabaseTransactionRepository(client)
        self.recovery_repo = SupabaseRecoveryCaseRepository(client)
        self.action_repo = SupabaseActionRecordRepository(client)
        self.audit_repo = SupabaseAuditRecordRepository(client)
        self.policy_repo = SupabasePolicyRepository(client)
        self.message_repo = SupabaseMessageDeliveryRepository(client)
        self.notification_repo = SupabaseNotificationRepository(client)
        
        # Track generated data
        self.merchant = None
        self.customers = []
        self.transactions = []
        self.recovery_cases = []
        self.action_records = []
        self.audit_records = []
        
    def generate_merchant(self) -> Merchant:
        """Generate or retrieve the demo merchant."""
        existing = self.merchant_repo.get(DEMO_MERCHANT_ID)
        if existing:
            print(f"Demo merchant '{DEMO_MERCHANT_ID}' already exists.")
            self.merchant = existing
            return existing
        
        merchant = Merchant(
            id=DEMO_MERCHANT_ID,
            name=DEMO_MERCHANT_NAME,
            email="demo@payback.io",
            phone="+919876543210",
            timezone="Asia/Kolkata",
        )
        self.merchant = self.merchant_repo.save(merchant)
        
        # Create merchant settings
        settings = MerchantSettings(
            merchant_id=DEMO_MERCHANT_ID,
            notify_recovery_completed=True,
            notify_recovery_escalated=True,
            notify_action_failed=True,
            notify_payment_recovered=True,
        )
        self.merchant_repo.save_settings(settings)
        
        print(f"Created demo merchant: {DEMO_MERCHANT_ID}")
        return merchant
    
    def generate_customers(self) -> list[Customer]:
        """Generate demo customers with varied profiles."""
        if self.merchant is None:
            raise ValueError("Merchant must be generated first")
        
        customers = []
        for i, name in enumerate(CUSTOMER_NAMES[:NUM_CUSTOMERS]):
            profile = CUSTOMER_PROFILES[i % len(CUSTOMER_PROFILES)]
            
            customer = Customer(
                merchant_id=DEMO_MERCHANT_ID,
                external_id=f"demo_cust_{i+1}",
                name=name,
                email=generate_customer_email(name),
                phone=generate_customer_phone(),
                opted_out=False,
            )
            saved_customer = self.customer_repo.save(customer)
            customers.append(saved_customer)
        
        self.customers = customers
        print(f"Generated {len(customers)} customers")
        return customers
    
    def generate_transactions(self) -> list[Transaction]:
        """Generate historical transactions for each customer."""
        if not self.customers:
            raise ValueError("Customers must be generated first")
        
        all_transactions = []
        base_time = datetime.now(timezone.utc)
        
        for idx, customer in enumerate(self.customers):
            profile = CUSTOMER_PROFILES[idx % len(CUSTOMER_PROFILES)]
            num_transactions = random.randint(
                MIN_TRANSACTIONS_PER_CUSTOMER,
                MAX_TRANSACTIONS_PER_CUSTOMER
            )
            
            # Generate transactions with varying timestamps
            for i in range(num_transactions):
                # Determine status based on profile success rate
                if random.random() < profile["success_rate"]:
                    status = TransactionStatus.SUCCESS
                else:
                    status = weighted_choice({
                        TransactionStatus.FAILED: 0.80,
                        TransactionStatus.PENDING: 0.15,
                        TransactionStatus.ABANDONED: 0.05,
                    })
                
                # Generate amount based on profile preference
                amount = generate_amount(profile["amount_preference"])
                
                # Select payment method
                payment_method = random.choice(PAYMENT_METHODS)
                
                # Generate timestamp (spread over last 6 months)
                days_ago = random.randint(1, 180)
                created_at = generate_timestamp(base_time, days_ago, days_ago + 30)
                
                transaction = Transaction(
                    merchant_id=DEMO_MERCHANT_ID,
                    customer_id=customer.id,
                    amount=amount,
                    currency=Currency.INR,
                    payment_method=payment_method,
                    status=status,
                    failure_reason=random.choice(FAILURE_REASONS) if status == TransactionStatus.FAILED else None,
                    created_at=created_at,
                    updated_at=created_at,
                )
                
                saved_transaction = self.transaction_repo.save(transaction)
                all_transactions.append(saved_transaction)
        
        # Sort by creation time for chronological consistency
        all_transactions.sort(key=lambda t: t.created_at)
        self.transactions = all_transactions
        print(f"Generated {len(all_transactions)} transactions")
        return all_transactions
    
    def generate_recovery_cases(self) -> list[RecoveryCase]:
        """Generate recovery cases for failed transactions."""
        if not self.transactions:
            raise ValueError("Transactions must be generated first")
        
        recovery_cases = []
        profile_idx = 0
        
        for transaction in self.transactions:
            # Only create recovery cases for failed transactions
            if transaction.status != TransactionStatus.FAILED:
                continue
            
            # Find the customer and their profile
            customer = next(c for c in self.customers if c.id == transaction.customer_id)
            customer_idx = self.customers.index(customer)
            profile = CUSTOMER_PROFILES[customer_idx % len(CUSTOMER_PROFILES)]
            
            # Determine recovery outcome based on profile recovery rate
            if random.random() < profile["recovery_rate"]:
                outcome = RecoveryOutcome.RECOVERED
                final_status = RecoveryStatus.RECOVERED
                amount_recovered = transaction.amount
            else:
                outcome = weighted_choice(RECOVERY_OUTCOME_WEIGHTS)
                if outcome == RecoveryOutcome.ESCALATED:
                    final_status = RecoveryStatus.ESCALATED
                elif outcome == RecoveryOutcome.EXPIRED:
                    final_status = RecoveryStatus.STOPPED
                else:
                    final_status = RecoveryStatus.STOPPED
                amount_recovered = 0.0
            
            # Create recovery case
            # Handle datetime conversion if created_at is a string
            created_at = transaction.created_at
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            
            recovery_case = RecoveryCase(
                merchant_id=DEMO_MERCHANT_ID,
                transaction_id=transaction.id,
                customer_id=customer.id,
                amount_at_risk=transaction.amount,
                reason=transaction.failure_reason or "payment_not_completed",
                status=final_status,
                outcome=outcome,
                amount_recovered=amount_recovered,
                recovery_probability=random.uniform(0.3, 0.9),  # Simulated ML probability
                retry_count=random.randint(0, 3),
                message_count=random.randint(0, 3),
                created_at=created_at + timedelta(minutes=5),
                updated_at=created_at + timedelta(hours=random.randint(1, 72)),
            )
            
            # Set escalation/stop reasons if applicable
            if final_status == RecoveryStatus.ESCALATED:
                recovery_case.escalate_reason = EscalateReason.HIGH_VALUE if transaction.amount >= 10000 else EscalateReason.REPEATED_FAILURES
                recovery_case.decision = RecoveryDecision.ESCALATE
            elif final_status == RecoveryStatus.STOPPED:
                recovery_case.stop_reason = StopReason.WINDOW_EXPIRED if outcome == RecoveryOutcome.EXPIRED else StopReason.MAX_RETRIES
                recovery_case.decision = RecoveryDecision.STOP
            elif final_status == RecoveryStatus.RECOVERED:
                recovery_case.decision = RecoveryDecision.RECOVER
            
            saved_case = self.recovery_repo.save(recovery_case)
            recovery_cases.append(saved_case)
        
        self.recovery_cases = recovery_cases
        print(f"Generated {len(recovery_cases)} recovery cases")
        return recovery_cases
    
    def generate_action_records(self) -> list[ActionRecord]:
        """Generate action records for recovery cases."""
        if not self.recovery_cases:
            raise ValueError("Recovery cases must be generated first")
        
        action_records = []
        
        for case in self.recovery_cases:
            # Generate action records based on recovery status
            if case.status == RecoveryStatus.RECOVERED:
                actions = [
                    (RecoveryAction.CREATE_PAYMENT_LINK, RecoveryOutcome.RECOVERED, "Payment link created and customer paid"),
                    (RecoveryAction.SEND_EMAIL, RecoveryOutcome.RECOVERED, "Recovery notification sent"),
                ]
            elif case.status == RecoveryStatus.ESCALATED:
                actions = [
                    (RecoveryAction.RETRY_PAYMENT, RecoveryOutcome.FAILED, "Payment retry failed"),
                    (RecoveryAction.SEND_WHATSAPP, RecoveryOutcome.FAILED, "WhatsApp message not delivered"),
                    (RecoveryAction.ESCALATE, RecoveryOutcome.ESCALATED, "Escalated to human review"),
                ]
            elif case.status == RecoveryStatus.STOPPED:
                actions = [
                    (RecoveryAction.CREATE_PAYMENT_LINK, RecoveryOutcome.EXPIRED, "Payment link expired"),
                    (RecoveryAction.STOP, RecoveryOutcome.STOPPED, "Recovery stopped"),
                ]
            else:
                continue
            
            for i, (action, outcome, detail) in enumerate(actions):
                # Handle datetime conversion if case.created_at is a string
                case_created_at = case.created_at
                if isinstance(case_created_at, str):
                    case_created_at = datetime.fromisoformat(case_created_at.replace('Z', '+00:00'))
                
                action_record = ActionRecord(
                    merchant_id=DEMO_MERCHANT_ID,
                    recovery_case_id=case.id,
                    action=action,
                    outcome=outcome,
                    detail=detail,
                    executed_at=case_created_at + timedelta(hours=i+1),
                )
                saved_record = self.action_repo.save(action_record)
                action_records.append(saved_record)
        
        self.action_records = action_records
        print(f"Generated {len(action_records)} action records")
        return action_records
    
    def generate_audit_records(self) -> list[AuditRecord]:
        """Generate audit records for recovery cases."""
        if not self.recovery_cases:
            raise ValueError("Recovery cases must be generated first")
        
        audit_records = []
        
        for case in self.recovery_cases:
            # Generate audit trail based on recovery lifecycle
            events = [
                (AuditEventType.PAYMENT_FAILED, f"Payment failed for transaction {case.transaction_id}"),
                (AuditEventType.RECOVERY_CASE_CREATED, f"Recovery case {case.id} created"),
            ]
            
            if case.status == RecoveryStatus.RECOVERED:
                # Handle enum to string conversion
                decision_str = case.decision.value if hasattr(case.decision, 'value') else str(case.decision) if case.decision else 'recover'
                action_str = case.selected_action.value if hasattr(case.selected_action, 'value') else str(case.selected_action) if case.selected_action else 'create_payment_link'
                
                events.extend([
                    (AuditEventType.ELIGIBILITY_CHECKED, "Customer eligibility verified"),
                    (AuditEventType.DECISION_MADE, f"Decision: {decision_str}"),
                    (AuditEventType.ACTION_SELECTED, f"Action: {action_str}"),
                    (AuditEventType.RECOVERY_COMPLETED, f"Recovery completed, amount: {case.amount_recovered}"),
                ])
            elif case.status == RecoveryStatus.ESCALATED:
                # Handle enum to string conversion
                escalate_str = case.escalate_reason.value if hasattr(case.escalate_reason, 'value') else str(case.escalate_reason) if case.escalate_reason else 'high_value'
                
                events.extend([
                    (AuditEventType.ELIGIBILITY_CHECKED, "Customer eligibility verified"),
                    (AuditEventType.RECOVERY_ESCALATED, f"Case escalated: {escalate_str}"),
                ])
            elif case.status == RecoveryStatus.STOPPED:
                # Handle enum to string conversion
                stop_str = case.stop_reason.value if hasattr(case.stop_reason, 'value') else str(case.stop_reason) if case.stop_reason else 'expired'
                
                events.extend([
                    (AuditEventType.ELIGIBILITY_CHECKED, "Customer eligibility verified"),
                    (AuditEventType.RECOVERY_STOPPED, f"Recovery stopped: {stop_str}"),
                ])
            
            for i, (event_type, detail) in enumerate(events):
                # Handle datetime conversion if case.created_at is a string
                case_created_at = case.created_at
                if isinstance(case_created_at, str):
                    case_created_at = datetime.fromisoformat(case_created_at.replace('Z', '+00:00'))
                
                audit_record = AuditRecord(
                    merchant_id=DEMO_MERCHANT_ID,
                    recovery_case_id=case.id,
                    event_type=event_type,
                    detail=detail,
                    created_at=case_created_at + timedelta(minutes=i*5),
                )
                saved_record = self.audit_repo.save(audit_record)
                audit_records.append(saved_record)
        
        self.audit_records = audit_records
        print(f"Generated {len(audit_records)} audit records")
        return audit_records
    
    def generate_policy(self) -> Policy:
        """Generate a policy for the demo merchant."""
        policy = Policy(
            merchant_id=DEMO_MERCHANT_ID,
            name="Demo Merchant Policy",
            is_active=True,
            maximum_retries=3,
            maximum_messages=3,
            recovery_window_hours=72,
            high_value_threshold=10000.0,
            human_approval_required=False,
            action_costs={
                "retry_payment": 2.0,
                "create_payment_link": 5.0,
                "send_whatsapp": 1.0,
                "send_email": 0.2,
                "escalate": 15.0,
                "stop": 0.0,
            },
        )
        saved_policy = self.policy_repo.save(policy)
        print(f"Generated policy for demo merchant")
        return saved_policy
    
    def generate_all(self) -> dict[str, Any]:
        """Generate all demo data."""
        print("=" * 60)
        print("Generating PayBack Demo Merchant Dataset")
        print("=" * 60)
        
        self.generate_merchant()
        self.generate_customers()
        self.generate_transactions()
        self.generate_recovery_cases()
        self.generate_action_records()
        self.generate_audit_records()
        # self.generate_policy()  # Temporarily disabled due to schema mismatch
        
        summary = {
            "merchant_id": DEMO_MERCHANT_ID,
            "merchant_name": DEMO_MERCHANT_NAME,
            "num_customers": len(self.customers),
            "num_transactions": len(self.transactions),
            "num_recovery_cases": len(self.recovery_cases),
            "num_action_records": len(self.action_records),
            "num_audit_records": len(self.audit_records),
            # "num_policies": 1,  # Temporarily disabled
        }
        
        print("=" * 60)
        print("Demo Data Generation Complete")
        print("=" * 60)
        for key, value in summary.items():
            print(f"{key}: {value}")
        
        return summary


# ============================================================================
# DATA CLEANUP
# ============================================================================

def cleanup_demo_data(client: SupabaseClient) -> None:
    """Remove all demo merchant data in FK-safe order."""
    print("=" * 60)
    print("Cleaning up demo merchant data")
    print("=" * 60)
    
    # Delete in FK-safe order (children before parents)
    tables_to_clean = [
        ("processed_webhook_events", "merchant_id"),
        ("message_delivery_records", "merchant_id"),
        ("notifications", "merchant_id"),
        ("audit_records", "merchant_id"),
        ("action_records", "merchant_id"),
        ("recovery_cases", "merchant_id"),
        ("transactions", "merchant_id"),
        ("customers", "merchant_id"),
        ("policies", "merchant_id"),
        ("merchant_settings", "merchant_id"),
        ("merchants", "id"),
    ]
    
    for table, id_column in tables_to_clean:
        try:
            # Use the delete method with appropriate filter
            if table == "merchants":
                client.delete(table, {"id": f"eq.{DEMO_MERCHANT_ID}"})
            else:
                client.delete(table, {id_column: f"eq.{DEMO_MERCHANT_ID}"})
            print(f"Deleted from {table} where {id_column} = {DEMO_MERCHANT_ID}")
        except Exception as e:
            print(f"Error cleaning {table}: {e}")
    
    print("Cleanup complete")


# ============================================================================
# VALIDATION
# ============================================================================

def validate_demo_data(client: SupabaseClient) -> dict[str, Any]:
    """Validate the demo merchant dataset."""
    print("=" * 60)
    print("Validating Demo Merchant Dataset")
    print("=" * 60)
    
    merchant_repo = SupabaseMerchantRepository(client)
    customer_repo = SupabaseCustomerRepository(client)
    transaction_repo = SupabaseTransactionRepository(client)
    recovery_repo = SupabaseRecoveryCaseRepository(client)
    
    validation_results = {}
    
    # Check merchant exists
    merchant = merchant_repo.get(DEMO_MERCHANT_ID)
    validation_results["merchant_exists"] = merchant is not None
    if merchant:
        validation_results["merchant_name"] = merchant.name
    
    # Check customer count
    customers = customer_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=100)
    validation_results["customer_count"] = len(customers)
    validation_results["customer_count_valid"] = 10 <= len(customers) <= 15
    
    # Check transaction count
    transactions = transaction_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=1000)
    validation_results["transaction_count"] = len(transactions)
    
    # Check transactions per customer
    txn_per_customer = []
    for customer in customers:
        customer_txns = transaction_repo.list_by_customer(customer.id, limit=100)
        txn_per_customer.append(len(customer_txns))
    
    validation_results["min_transactions_per_customer"] = min(txn_per_customer) if txn_per_customer else 0
    validation_results["max_transactions_per_customer"] = max(txn_per_customer) if txn_per_customer else 0
    validation_results["transactions_per_customer_valid"] = all(15 <= count <= 30 for count in txn_per_customer)
    
    # Check recovery cases
    recovery_cases = recovery_repo.list_by_merchant(DEMO_MERCHANT_ID, limit=1000)
    validation_results["recovery_case_count"] = len(recovery_cases)
    
    # Check merchant isolation
    validation_results["merchant_isolation_valid"] = all(
        c.merchant_id == DEMO_MERCHANT_ID for c in customers
    ) and all(
        t.merchant_id == DEMO_MERCHANT_ID for t in transactions
    ) and all(
        rc.merchant_id == DEMO_MERCHANT_ID for rc in recovery_cases
    )
    
    print("Validation Results:")
    for key, value in validation_results.items():
        print(f"  {key}: {value}")
    
    return validation_results


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Seed PayBack demo merchant data")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate demo data")
    parser.add_argument("--validate", action="store_true", help="Validate existing demo data")
    parser.add_argument("--supabase-url", help="Supabase URL (overrides env)")
    parser.add_argument("--supabase-key", help="Supabase service role key (overrides env)")
    
    args = parser.parse_args()
    
    # Get Supabase credentials from settings or command-line overrides
    supabase_url = args.supabase_url or settings.supabase_url
    supabase_key = args.supabase_key or settings.supabase_service_role_key or settings.supabase_anon_key
    
    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) must be set")
        print("Configure these in your .env file or use --supabase-url and --supabase-key arguments")
        sys.exit(1)
    
    # Initialize Supabase client
    client = SupabaseClient(supabase_url, supabase_key)
    
    if args.validate:
        validate_demo_data(client)
        return
    
    if args.reset:
        cleanup_demo_data(client)
    
    # Check if demo merchant already exists
    merchant_repo = SupabaseMerchantRepository(client)
    existing = merchant_repo.get(DEMO_MERCHANT_ID)
    
    if existing and not args.reset:
        print(f"Demo merchant '{DEMO_MERCHANT_ID}' already exists.")
        print("Use --reset to delete and recreate, or --validate to check existing data.")
        validate_demo_data(client)
        return
    
    # Generate demo data
    generator = DemoDataGenerator(client)
    summary = generator.generate_all()
    
    # Validate after generation
    validation_results = validate_demo_data(client)
    
    # Print final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"Demo Merchant ID: {summary['merchant_id']}")
    print(f"Demo Merchant Name: {summary['merchant_name']}")
    print(f"Customers: {summary['num_customers']}")
    print(f"Transactions: {summary['num_transactions']}")
    print(f"Recovery Cases: {summary['num_recovery_cases']}")
    print(f"Action Records: {summary['num_action_records']}")
    print(f"Audit Records: {summary['num_audit_records']}")
    # print(f"Policies: {summary.get('num_policies', 0)}")  # Temporarily disabled
    print(f"Validation Passed: {all(validation_results.values())}")


if __name__ == "__main__":
    main()