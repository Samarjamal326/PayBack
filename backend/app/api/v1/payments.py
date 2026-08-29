from __future__ import annotations

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import CreatePaymentRequest, CreatePaymentResponse, CreatePaymentWithCustomerRequest
from app.config import settings
from app.core.auth import get_current_merchant
from app.models.domain import Currency, Customer, Merchant, PaymentMethod, Transaction, TransactionStatus
from app.repositories.factory import get_repository_bundle
from app.services.actions.razorpay import RazorpayPaymentProvider, LiveKeyForbiddenError
from app.services.actions.stubs import StubPaymentProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])
_repos = get_repository_bundle()


def _get_payment_provider():
    """Get the appropriate payment provider based on configuration."""
    # Check for a flag to force stub provider for testing
    import os
    if os.getenv("USE_STUB_PROVIDER", "").lower() == "true":
        logger.info("Using stub provider (forced by USE_STUB_PROVIDER=true)")
        return StubPaymentProvider()
        
    if settings.is_razorpay_configured() and settings.razorpay_key_id.startswith("rzp_test_"):
        try:
            return RazorpayPaymentProvider(
                key_id=settings.razorpay_key_id,
                key_secret=settings.razorpay_key_secret,
            )
        except LiveKeyForbiddenError:
            logger.warning("Live Razorpay key detected, falling back to stub provider")
            return StubPaymentProvider()
    return StubPaymentProvider()


@router.post("/create", response_model=CreatePaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: CreatePaymentRequest,
    merchant: Merchant = Depends(get_current_merchant),
) -> CreatePaymentResponse:
    """
    Create a new payment link via Razorpay Test Mode.
    
    This endpoint:
    1. Creates an internal transaction record
    2. Creates a Razorpay order/payment link
    3. Returns the payment link URL for the customer to complete payment
    
    The merchant is derived from the authenticated session, not from the request.
    """
    # Validate customer exists and belongs to merchant
    customer = _repos.customers.get(payload.customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{payload.customer_id}' not found"
        )
    
    # Ensure customer belongs to the authenticated merchant
    if customer.merchant_id and customer.merchant_id != merchant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer does not belong to this merchant"
        )
    
    # Create internal transaction record first
    transaction = Transaction(
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=payload.amount,
        currency=payload.currency,
        payment_method="unknown",  # Will be updated by Razorpay
        status=TransactionStatus.PENDING,
        failure_reason=None,
        failure_code=None,
        razorpay_order_id=None,
        razorpay_payment_id=None,
    )
    
    saved_transaction = _repos.transactions.save(transaction)
    
    # Create Razorpay payment link
    payment_provider = _get_payment_provider()
    
    try:
        result = payment_provider.create_payment_link(
            transaction_id=saved_transaction.id,
            amount=payload.amount,
            customer_email=customer.email or "",
            customer_phone=customer.phone,
            customer_name=customer.name,
        )
        
        # Extract Razorpay order ID from the result if available
        razorpay_order_id = result.external_id  # Razorpay order ID from provider
        payment_link_url = result.external_ref
        
        # If the provider is Razorpay, we might get order info from the detail
        if hasattr(result, 'detail') and result.detail:
            logger.info(f"Payment link created: {result.detail}")
        
        # Update transaction with Razorpay order ID
        if razorpay_order_id:
            saved_transaction.razorpay_order_id = razorpay_order_id
            _repos.transactions.save(saved_transaction)
            logger.info(f"Transaction updated with Razorpay order ID: {razorpay_order_id}")
        
        logger.info(
            f"Payment created: transaction_id={saved_transaction.id}, "
            f"merchant_id={merchant.id}, customer_id={customer.id}, "
            f"amount={payload.amount} {payload.currency.value}"
        )
        
        return CreatePaymentResponse(
            transaction_id=saved_transaction.id,
            razorpay_order_id=saved_transaction.razorpay_order_id,
            payment_link_url=payment_link_url,
            amount=payload.amount,
            currency=payload.currency.value,
            status="pending",
            customer_name=customer.name,
            created_at=saved_transaction.created_at,
        )
        
    except Exception as exc:
        logger.error(f"Failed to create payment link: {exc}")
        
        # Clean up the transaction if payment link creation failed
        try:
            if hasattr(_repos.transactions, 'delete'):
                _repos.transactions.delete(saved_transaction.id)
        except Exception as delete_exc:
            logger.warning(f"Failed to clean up transaction after payment link creation failure: {delete_exc}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment link: {str(exc)}"
        )


@router.post("/create-with-customer", response_model=CreatePaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment_with_customer(
    payload: CreatePaymentWithCustomerRequest,
    merchant: Merchant = Depends(get_current_merchant),
) -> CreatePaymentResponse:
    """
    Create a new customer and payment link in one operation.
    This is for testing the complete payment → failure → recovery workflow.
    """
    from app.services.payment_ingestion import resolve_customer_for_payment
    from app.api.schemas import PaymentEventRequest
    
    # Create or find customer using the payment ingestion logic
    customer = resolve_customer_for_payment(
        PaymentEventRequest(
            customer_external_id=f"cus_{payload.customer_name.lower().replace(' ', '_')}",
            customer_name=payload.customer_name,
            customer_email=payload.customer_email,
            customer_phone=payload.customer_phone,
            transaction_amount=payload.amount,
            transaction_currency=payload.currency,
            payment_method=payload.payment_method,
            transaction_status=TransactionStatus.PENDING,
        ),
        merchant,
        _repos.customers
    )
    
    # Save customer
    _repos.customers.save(customer)
    
    # Create internal transaction record
    transaction = Transaction(
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=payload.amount,
        currency=payload.currency,
        payment_method=payload.payment_method.value,
        status=TransactionStatus.PENDING,
        failure_reason=None,
        failure_code=None,
        razorpay_order_id=None,
        razorpay_payment_id=None,
    )
    
    saved_transaction = _repos.transactions.save(transaction)
    
    # Create Razorpay payment link
    payment_provider = _get_payment_provider()
    
    try:
        result = payment_provider.create_payment_link(
            transaction_id=saved_transaction.id,
            amount=payload.amount,
            customer_email=customer.email or "",
            customer_phone=customer.phone,
            customer_name=customer.name,
        )
        
        # Extract Razorpay order ID from the result if available
        razorpay_order_id = result.external_id  # Razorpay order ID from provider
        payment_link_url = result.external_ref
        
        # Update transaction with Razorpay order ID
        if razorpay_order_id:
            saved_transaction.razorpay_order_id = razorpay_order_id
            _repos.transactions.save(saved_transaction)
            logger.info(f"Transaction updated with Razorpay order ID: {razorpay_order_id}")
        
        logger.info(
            f"Payment created with customer: transaction_id={saved_transaction.id}, "
            f"merchant_id={merchant.id}, customer_id={customer.id}, "
            f"amount={payload.amount} {payload.currency.value}"
        )
        
        return CreatePaymentResponse(
            transaction_id=saved_transaction.id,
            razorpay_order_id=saved_transaction.razorpay_order_id,
            payment_link_url=payment_link_url,
            amount=payload.amount,
            currency=payload.currency.value,
            status="pending",
            customer_name=customer.name,
            created_at=saved_transaction.created_at,
        )
        
    except Exception as exc:
        logger.error(f"Failed to create payment link: {exc}")
        
        # Clean up the transaction if payment link creation failed
        try:
            if hasattr(_repos.transactions, 'delete'):
                _repos.transactions.delete(saved_transaction.id)
        except Exception as delete_exc:
            logger.warning(f"Failed to clean up transaction after payment link creation failure: {delete_exc}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment link: {str(exc)}"
        )


@router.get("/transaction/{transaction_id}")
def get_transaction(
    transaction_id: str,
    merchant: Merchant = Depends(get_current_merchant),
) -> Transaction:
    """Get a transaction by ID, ensuring merchant isolation."""
    transaction = _repos.transactions.get(transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found"
        )
    
    # Ensure transaction belongs to the authenticated merchant
    if transaction.merchant_id and transaction.merchant_id != merchant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Transaction does not belong to this merchant"
        )
    
    return transaction


@router.get("/customer/{customer_id}")
def get_customer_payments(
    customer_id: str,
    merchant: Merchant = Depends(get_current_merchant),
) -> list[Transaction]:
    """Get all payments for a customer, ensuring merchant isolation."""
    # First verify customer belongs to merchant
    customer = _repos.customers.get(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found"
        )
    
    if customer.merchant_id and customer.merchant_id != merchant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer does not belong to this merchant"
        )
    
    return _repos.transactions.list_by_customer(customer_id)
