# PayBack — Architecture Overview (Phase 2)

## System Components

```
PayBack
├── API layer          FastAPI routes — thin, webhook verification & route dispatch
├── Service layer      RecoveryService — application orchestration & audit trail
├── Repositories       Clean repository abstraction (InMemory & Supabase REST)
├── Agent layer        LangGraph workflow — state transitions
├── Core layer         Decision engine + state machine — deterministic rules
├── Models layer       Domain models, enums & audit records — Pydantic v2
└── Services layer
    ├── Actions        Razorpay Test Mode provider + stubs + executor
    ├── Razorpay       Webhook signature verification & event processing
    └── LLM            HuggingFaceMessageGenerator + Mock fallback
```

## Complete Recovery Loop

```
Razorpay Test Payment Failed
        │
        ▼
POST /api/v1/events/payment
        │
        ▼
RecoveryService.ingest_payment_event()  ──► AuditRecord(PAYMENT_FAILED)
        │                               ──► AuditRecord(RECOVERY_CASE_CREATED)
        ▼
RecoveryCase (status: DETECTED)
        │
        ▼
POST /api/v1/recovery ──► RecoveryService.run_recovery()
        │
        ▼
LangGraph graph.invoke(RecoveryState)
        │
analyze ──► check_eligibility ──► decide (Decision Engine)
                                    │
                              [RECOVER action]
                                    │
                                    ▼
                      Razorpay Test Payment Link created
                                    │
                        Status: MONITORING
                                    │
         Customer completes test payment on simulated link
                                    │
                                    ▼
POST /api/v1/events/webhook/razorpay (verified with HMAC-SHA256)
        │
        ▼
process_razorpay_webhook_event() (event: payment_link.paid)
        │
        ▼
RecoveryService.mark_case_recovered()
        │
        ├──► RecoveryCase.status = RECOVERED
        ├──► RecoveryCase.outcome = RECOVERED
        ├──► RecoveryCase.amount_recovered = exact amount (INR)
        ├──► AuditRecord(PAYMENT_SUCCEEDED)
        └──► AuditRecord(RECOVERY_COMPLETED)
```

## Zero-Cost Safety Guarantees

1. **Razorpay Test Mode Only**:
   - `rzp_test_` keys allowed only.
   - `rzp_live_` keys are strictly rejected at startup and execution time (`LiveKeyForbiddenError`).
   - No real transactions, cards, or accounts are charged.
2. **Supabase Free Tier / In-Memory Flexibility**:
   - Free PostgreSQL REST PostgREST client without heavy external SDK overhead.
   - Defaults to in-memory repositories for local dev/testing without database credentials.
3. **Hugging Face Free Tier / Mock Fallback**:
   - Prompt-based message generation using free/open models (`mistralai/Mistral-7B-Instruct-v0.2`).
   - Cleanly falls back to `MockMessageGenerator` when no API key is supplied.
   - The LLM never makes financial or recovery decisions.

## Domain Model

| Model         | Purpose                                                 |
|---------------|---------------------------------------------------------|
| Customer      | Merchant's customer with opt-out flag                   |
| Transaction   | Commercial payment event with status and failure reason |
| RecoveryCase  | Recovery opportunity with status, outcome, amount       |
| ActionRecord  | Record of executed actions with external link refs      |
| AuditRecord   | Complete chronological audit trail for every case       |
| Policy        | Merchant limits (retries, window, thresholds)           |

## API Boundaries

```
GET  /api/v1/health                    Health & Test Mode status check
POST /api/v1/events/payment            Ingest a payment failure event
POST /api/v1/events/webhook/razorpay   Verified Razorpay webhook receiver
POST /api/v1/recovery                  Start recovery workflow
GET  /api/v1/recovery/{id}             Get case state & outcome
GET  /api/v1/recovery/{id}/actions     Get executed action history
GET  /api/v1/recovery/{id}/audit       Get full chronological audit trail
```

## Intentionally Deferred to Phase 3

- Production WhatsApp API (Meta Cloud / Twilio)
- Production Email API (Amazon SES / SendGrid)
- ML recovery probability scoring model
- Authentication / merchant login
- Frontend user interface
- Analytics & merchant reporting dashboard
