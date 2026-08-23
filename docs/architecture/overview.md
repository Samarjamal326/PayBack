# PayBack — Architecture Overview (Phase 1)

## System Components

```
PayBack
├── API layer          FastAPI routes — thin, no business logic
├── Service layer      RecoveryService — application orchestration
├── Agent layer        LangGraph workflow — node-based state transitions
├── Core layer         Decision engine + state machine — deterministic rules
├── Models layer       Domain models and enums — Pydantic v2
└── Services layer
    ├── Actions        Provider interfaces + stubs + executor
    └── LLM            MessageGenerator interface + mock
```

## Recovery Flow

```
POST /events/payment
        │
        ▼
RecoveryService.ingest_payment_event()
        │
        ▼
RecoveryCase created (status: DETECTED)

POST /recovery
        │
        ▼
RecoveryService.run_recovery()
        │
        ▼
LangGraph graph.invoke(RecoveryState)
        │
  ┌─────┴────────────────────────────────────────┐
  │                                              │
  ▼                                              │
analyze → check_eligibility → decide            │
                    │                            │
          ┌─────────┼──────────┐                 │
          ▼         ▼          ▼                 │
       recover   escalate    stop                │
          │                                      │
          ▼                                      │
   execute_action → monitor → stop/escalate ─────┘
```

## Domain Model

| Model         | Purpose                                               |
|---------------|-------------------------------------------------------|
| Customer      | Merchant's customer with opt-out flag                 |
| Transaction   | Payment event with status and failure reason          |
| RecoveryCase  | Recovery opportunity linked to a transaction          |
| ActionRecord  | Audit trail of every executed action                  |
| Policy        | Merchant-defined limits (retries, window, thresholds) |

All statuses and decisions are typed enums — no raw strings in business logic.

## Decision Engine Responsibility

`app/core/decision.py` — fully deterministic, no LLM.

Evaluates in this priority order:
1. Customer opt-out → STOP
2. Recovery window expired → STOP
3. Max retries reached → STOP
4. Max messages sent → STOP
5. Transaction already succeeded → STOP
6. High-value threshold exceeded → ESCALATE
7. Policy requires human approval → ESCALATE
8. Transaction not in recoverable status → STOP
9. All conditions clear → RECOVER

## LangGraph Responsibility

`app/agent/` — workflow orchestration only.

Nodes are thin: they call the decision engine and action executor.
No business rules live inside nodes.

## API Boundaries

```
POST /api/v1/events/payment     Ingest a payment event
POST /api/v1/recovery           Start recovery for a case
GET  /api/v1/recovery/{id}      Get current case state
GET  /api/v1/recovery/{id}/actions  Get action history
```

## External Integration Boundaries

### Razorpay (Phase 2)
- `PaymentActionProvider` interface in `app/services/actions/interfaces.py`
- Will receive: Razorpay webhook → `POST /events/payment`
- Will call: Razorpay API for payment links and retries

### Messaging — WhatsApp / Email (Phase 2)
- `MessagingProvider` interface in `app/services/actions/interfaces.py`
- Providers are injected into `ActionExecutor`

### LLM — Hugging Face (Phase 2)
- `MessageGenerator` interface in `app/services/llm/interface.py`
- `MockMessageGenerator` used in Phase 1 tests

### Database — Supabase (Phase 2)
- `RecoveryService` currently uses in-memory dicts
- Replace with repository classes that implement the same read/write interface
- Domain models are already persistence-independent (plain Pydantic)

## Intentionally Deferred

- Real Razorpay API integration
- WhatsApp (Twilio / Meta) integration
- Email (SES / SendGrid) integration
- Real Hugging Face API calls
- ML recovery probability model
- Supabase PostgreSQL persistence
- Authentication / authorization
- Frontend
- RAG / vector database
- Deployment / containerization
- Analytics
