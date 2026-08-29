"""
Simple script to test production webhook endpoint.
"""
import json
import httpx
import hashlib
import hmac
import os

def test_webhook_with_signature():
    """Test the webhook endpoint with signature verification"""
    
    # Get webhook secret from environment
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "your_secure_webhook_secret_123")
    
    print(f"Webhook secret configured: {bool(webhook_secret)}")
    print(f"Testing with ngrok URL: https://5f61-2401-4900-8855-aeb6-9d0c-f0b8-edbe-6cc2.ngrok-free.app")
    
    # Sample webhook payload (simulating payment_link.paid event)
    webhook_payload = {
        "event": "payment_link.paid",
        "id": "evt_test_123456",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink_test_789",
                    "amount": 200000,  # 2000 INR in paise
                    "currency": "INR",
                    "description": "PayBack payment for transaction test_tx",
                    "notes": {
                        "transaction_id": "test_tx_123",
                        "order_id": "order_test_456",
                        "recovery_source": "payback_ai_recovery",
                    }
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_test_999",
                    "amount": 200000,
                    "currency": "INR",
                    "status": "captured",
                    "notes": {
                        "transaction_id": "test_tx_123",
                        "recovery_source": "payback_ai_recovery",
                    }
                }
            }
        }
    }
    
    # Convert to JSON bytes
    raw_body = json.dumps(webhook_payload).encode("utf-8")
    
    # Generate signature if webhook secret is configured
    headers = {
        "Content-Type": "application/json",
    }
    
    if webhook_secret:
        signature = hmac.new(
            key=webhook_secret.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()
        headers["X-Razorpay-Signature"] = signature
        print(f"Generated signature: {signature[:20]}...")
    else:
        print("No webhook secret configured - cannot test with signature verification")
        return False
    
    # Send webhook to local server
    url = "https://5f61-2401-4900-8855-aeb6-9d0c-f0b8-edbe-6cc2.ngrok-free.app/api/v1/events/webhook/razorpay"
    
    try:
        response = httpx.post(url, content=raw_body, headers=headers, timeout=10.0)
        
        print(f"\nWebhook Test Results:")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("\n[SUCCESS] Webhook endpoint is working with signature!")
            return True
        else:
            print(f"\n[ERROR] Webhook endpoint returned error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] Error sending webhook: {e}")
        return False

def test_webhook_without_signature():
    """Test the webhook endpoint without signature (requires server config change)"""
    
    print("Testing webhook without signature verification...")
    print("Note: This requires temporarily disabling signature verification in the server")
    
    webhook_payload = {
        "event": "payment_link.paid",
        "id": "evt_test_789",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink_test_456",
                    "amount": 200000,
                    "currency": "INR",
                    "description": "PayBack payment for transaction test_tx",
                    "notes": {
                        "transaction_id": "test_tx_789",
                        "order_id": "order_test_123",
                        "recovery_source": "payback_ai_recovery",
                    }
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_test_456",
                    "amount": 200000,
                    "currency": "INR",
                    "status": "captured",
                    "notes": {
                        "transaction_id": "test_tx_789",
                        "recovery_source": "payback_ai_recovery",
                    }
                }
            }
        }
    }
    
    raw_body = json.dumps(webhook_payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    url = "https://5f61-2401-4900-8855-aeb6-9d0c-f0b8-edbe-6cc2.ngrok-free.app/api/v1/events/webhook/razorpay"
    
    try:
        response = httpx.post(url, content=raw_body, headers=headers, timeout=10.0)
        
        print(f"\nWebhook Test Results:")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("\n[SUCCESS] Webhook endpoint is working without signature!")
            return True
        else:
            print(f"\n[INFO] Server requires signature verification (expected)")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] Error sending webhook: {e}")
        return False

if __name__ == "__main__":
    print("=== Production Webhook Testing ===\n")
    
    # Force test with signature
    print("Testing with signature verification...")
    success = test_webhook_with_signature()
    
    if success:
        print("\n=== Webhook testing complete ===")
        print("SUCCESS: Webhook endpoint is working correctly!")
    else:
        print("\n=== Webhook testing complete ===")
        print("FAILED: Webhook endpoint returned error")
        print("\nTroubleshooting:")
        print("1. Check if webhook secret matches between .env and Razorpay dashboard")
        print("2. Verify the server is running with updated code")
        print("3. Check server logs for detailed error information")