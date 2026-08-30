"""
Email Configuration Test Script
Run this to verify your email configuration is working correctly.
"""

import os
import sys
# Add backend app directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from app.config import settings
from app.services.messaging.factory import get_delivery_provider

def test_email_configuration():
    """Test email configuration and send a test email."""
    print("Testing Email Configuration...")
    print(f"Message Delivery Provider: {settings.message_delivery_provider}")
    print(f"Resend Configured: {settings.is_resend_configured()}")
    print(f"SMTP Configured: {settings.is_smtp_configured()}")
    print(f"Resend From Email: {settings.resend_from_email}")
    print(f"SMTP From Email: {settings.smtp_from_email}")
    print()
    
    # Get the delivery provider
    try:
        provider = get_delivery_provider(settings)
        print(f"[SUCCESS] Delivery provider loaded: {provider.provider_type}")
        print(f"   Provider configured: {provider.is_configured}")
        print()
    except Exception as e:
        print(f"[ERROR] Failed to load delivery provider: {e}")
        return False
    
    # Test email sending
    test_email = input("Enter your email address for testing: ").strip()
    if not test_email:
        print("[ERROR] No email provided for testing")
        return False
    
    print(f"Sending test email to: {test_email}")
    
    try:
        result = provider.send_email(
            recipient_email=test_email,
            subject="PayBack Email Configuration Test",
            body_html="""
            <h2>Email Configuration Test</h2>
            <p>If you received this email, your PayBack email configuration is working correctly!</p>
            <p>This is a test email from the PayBack recovery system.</p>
            <p><strong>Configuration details:</strong></p>
            <ul>
                <li>Provider: {provider_type}</li>
                <li>From: {from_email}</li>
                <li>To: {to_email}</li>
            </ul>
            """.format(
                provider_type=provider.provider_type,
                from_email=getattr(provider, 'from_email', 'N/A'),
                to_email=test_email
            ),
            merchant_name="PayBack Test"
        )
        
        print(f"[SUCCESS] Email send result:")
        print(f"   Success: {result.success}")
        print(f"   Status: {result.status}")
        print(f"   Provider Message ID: {result.provider_message_id}")
        
        if result.failure_reason:
            print(f"   Failure Reason: {result.failure_reason}")
        
        if result.success:
            print(f"\n[SUCCESS] Test email sent successfully! Check your inbox (and spam folder).")
            return True
        else:
            print(f"\n[ERROR] Test email failed. Check the error above.")
            return False
            
    except Exception as e:
        print(f"[ERROR] Exception during email sending: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_email_configuration()
    sys.exit(0 if success else 1)
