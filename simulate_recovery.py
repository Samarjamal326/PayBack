"""
End-to-End Simulation Script for PayBack AI Revenue Recovery
Demonstrates:
1. Failed payment event ingestion via POST /api/v1/events/payment
2. Real-time ML likelihood scoring & Expected Value calculation
3. Intelligent Action selection (Smart Retry, WhatsApp / Email payment link)
4. AI message generation & dispatch
5. Webhook event (payment.captured / payment.recovered) closing the loop
6. Verification across Dashboard, Recoveries Queue, and Audit trail
"""
import json
import httpx

BASE_URL = "http://localhost:8000"

def run_simulation():
    client = httpx.Client(base_url=BASE_URL, timeout=15.0)

    print("=" * 60)
    print("STARTING PAYBACK LIVE REVENUE RECOVERY SIMULATION")
    print("=" * 60)

    # 1. Check Backend Health
    print("\n[Step 1] Checking API & Engine Health...")
    health_resp = client.get("/api/v1/health")
    print(f"Status: {health_resp.status_code} -> {health_resp.json()}")

    # 2. Login as Merchant
    print("\n[Step 2] Authenticating as Merchant Admin...")
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "admin@payback.io",
        "password": "password123"
    })
    auth_data = login_resp.json()
    token = auth_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[OK] Authenticated! Merchant ID: {auth_data['merchant_id']}")

    # 3. Simulate a Real Failed Payment Event
    print("\n[Step 3] Simulating User Payment Failure from Checkout...")
    failed_payment_payload = {
        "customer_external_id": "cust_rahul_99",
        "customer_name": "Rahul Verma",
        "customer_email": "rahul.verma@example.com",
        "customer_phone": "+919876501234",
        "transaction_amount": 3499.0,
        "transaction_currency": "INR",
        "payment_method": "upi",
        "transaction_status": "failed",
        "failure_reason": "Insufficient funds at issuing bank (UPI timeout)"
    }
    
    event_resp = client.post("/api/v1/events/payment", json=failed_payment_payload, headers=headers)
    event_data = event_resp.json()
    print(f"[Event Ingested] Response: {json.dumps(event_data, indent=2)}")

    # 4. Fetch Recoveries Queue to see the AI diagnosis & ML Score
    print("\n[Step 4] Inspecting AI Decision Engine & ML Score...")
    recs_resp = client.get("/api/v1/recoveries", headers=headers)
    recs = recs_resp.json()
    latest_case = recs[0] if recs else None
    
    if latest_case:
        case_id = latest_case["id"]
        print(f"[Case Created] ID: {case_id}")
        print(f"   * Customer: {latest_case['customer_id']}")
        print(f"   * Amount at Risk: INR {latest_case['amount_at_risk']}")
        print(f"   * ML Recovery Likelihood: {round(latest_case['recovery_probability'] * 100, 1)}%")
        print(f"   * Expected Value (EV): INR {latest_case['expected_value']}")
        print(f"   * Selected Intervention: {latest_case.get('selected_action')}")
        print(f"   * AI Reason: {latest_case.get('decision_reason')}")

        # 5. Trigger Recovery Orchestration Workflow
        print(f"\n[Step 5] Executing Recovery Workflow & Dispatching Message for Case {case_id}...")
        start_resp = client.post("/api/v1/recoveries", json={
            "case_id": case_id,
            "maximum_retries": 3,
            "maximum_messages": 2,
            "recovery_window_hours": 72
        }, headers=headers)
        print(f"Workflow Execution Result: Status {start_resp.status_code}")

        # 6. Check Audit Trail & Dispatched Messages
        print("\n[Step 6] Inspecting Audit Trail & Message Deliveries...")
        timeline_resp = client.get(f"/api/v1/recoveries/{case_id}/timeline", headers=headers)
        for t in timeline_resp.json():
            print(f"   [{t['created_at'][:19]}] {t['event_type'].upper()}: {t['detail']}")

        # 7. Simulate Customer Paying through the Recovery Link (Webhook)
        print("\n[Step 7] Simulating Customer Paying via Recovery Payment Link...")
        webhook_payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_recovered_{case_id[:8]}",
                        "amount": int(latest_case['amount_at_risk'] * 100),
                        "currency": "INR",
                        "status": "captured",
                        "method": "upi",
                        "notes": {
                            "recovery_case_id": case_id,
                            "transaction_id": latest_case["transaction_id"]
                        }
                    }
                }
            }
        }
        
        # Calculate webhook signature if configured
        import hmac
        import hashlib
        webhook_body_bytes = json.dumps(webhook_payload).encode("utf-8")
        secret = "PayBack_webhook_2026_x7K9mP2q"
        sig = hmac.new(secret.encode("utf-8"), webhook_body_bytes, hashlib.sha256).hexdigest()
        
        wb_resp = client.post(
            "/api/v1/events/webhook/razorpay",
            content=webhook_body_bytes,
            headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"}
        )
        print(f"Webhook Result: Status {wb_resp.status_code} -> {wb_resp.json()}")


    # 8. Check Updated Dashboard Metrics
    print("\n[Step 8] Fetching Updated Dashboard ROI & Summary...")
    dash_resp = client.get("/api/v1/dashboard/summary", headers=headers)
    dash = dash_resp.json()
    print(f"   * Total Recovered Revenue: INR {dash['total_recovered_revenue']}")
    print(f"   * Total Revenue at Risk:   INR {dash['total_revenue_at_risk']}")
    print(f"   * Overall Recovery Rate:   {round(dash['overall_recovery_rate'] * 100, 1)}%")
    print(f"   * Successful Recoveries:   {dash['successful_recoveries']}")
    print(f"   * Active Recovery Cases:   {dash['active_recovery_cases']}")

    print("\n" + "=" * 60)
    print("FULL REVENUE RECOVERY SIMULATION COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_simulation()
