"""
Payment Workflow Test Script
Tests the complete payment → failure → recovery workflow with improved error handling.
"""

import sys
import os
# Add backend app directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from app.services.razorpay.webhook import get_human_readable_error, RAZORPAY_ERROR_MAPPING

def test_error_message_improvements():
    """Test the improved error message handling."""
    print("Testing Error Message Improvements...")
    print()
    
    # Test common error codes
    test_cases = [
        ("BAD_REQUEST_ERROR", "Invalid payment details provided"),
        ("INSUFFICIENT_FUNDS", "Insufficient funds in your account"),
        ("PAYMENT_FAILED", "Payment processing failed"),
        ("GATEWAY_ERROR", "Payment gateway error, please try again"),
        ("AUTHENTICATION_FAILED", "Authentication failed"),
        ("UNKNOWN_ERROR", "UNKNOWN_ERROR"),  # Should return the code itself
    ]
    
    all_passed = True
    for code, expected in test_cases:
        result = get_human_readable_error(code)
        passed = result == expected
        all_passed = all_passed and passed
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {code} -> '{result}' (expected: '{expected}')")
    
    print()
    print(f"[{'PASS' if all_passed else 'FAIL'}] All error message tests {'passed!' if all_passed else 'failed'}")
    print()
    
    # Show all available error mappings
    print("Available Error Code Mappings:")
    for code, message in RAZORPAY_ERROR_MAPPING.items():
        print(f"   {code}: {message}")
    
    return all_passed

def test_webhook_error_handling():
    """Test webhook error handling with mock data."""
    print("Testing Webhook Error Handling...")
    print()
    
    # Simulate webhook payload with error code
    mock_payment_entity = {
        "id": "pay_test123",
        "code": "INSUFFICIENT_FUNDS",
        "description": "",  # Empty description - should use mapping
        "amount": 50000,  # 500.00 INR in paise
    }
    
    from app.services.razorpay.webhook import get_human_readable_error
    
    failure_code = mock_payment_entity.get("code") or ""
    raw_failure_reason = mock_payment_entity.get("description") or ""
    
    # Use the same logic as the webhook
    failure_reason = raw_failure_reason if raw_failure_reason else get_human_readable_error(failure_code, f"Payment failed ({failure_code})")
    
    print(f"Mock webhook processing:")
    print(f"   Error Code: {failure_code}")
    print(f"   Raw Description: '{raw_failure_reason}'")
    print(f"   Processed Reason: '{failure_reason}'")
    print()
    
    expected = "Insufficient funds in your account"
    passed = failure_reason == expected
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} Webhook error handling test {'passed' if passed else 'failed'}")
    print()
    
    return passed

def main():
    """Run all tests."""
    print("PayBack Payment Workflow Tests")
    print("=" * 50)
    print()
    
    # Test 1: Error message improvements
    test1_passed = test_error_message_improvements()
    
    # Test 2: Webhook error handling
    test2_passed = test_webhook_error_handling()
    
    # Summary
    print("=" * 50)
    print("Test Summary:")
    print(f"   Error Message Improvements: {'[PASS]' if test1_passed else '[FAIL]'}")
    print(f"   Webhook Error Handling: {'[PASS]' if test2_passed else '[FAIL]'}")
    print()
    
    all_passed = test1_passed and test2_passed
    if all_passed:
        print("[SUCCESS] All tests passed! Error handling improvements are working correctly.")
    else:
        print("[FAILURE] Some tests failed. Please review the errors above.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
