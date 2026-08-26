# Phase 4 Architecture — Backend Productionization

## Overview

PayBack Phase 4 transforms the Phase 3 ML recovery prototype into an enterprise-ready, multi-tenant revenue recovery engine. It enforces tenant data isolation, introduces provider-independent messaging delivery adapters, implements deterministic webhook and background task idempotency, provides structured merchant APIs for dashboard/customers/recoveries/policies/settings/notifications, and maintains complete zero-cost development principles.

---

## Key Subsystems

### 1. Authentication & Multi-Tenancy
- **Standard RFC 7519 JWT & Supabase Auth:** Tokens decoded using zero-dependency HMAC SHA256.
- **Tenant Scoping:** All resources (`Customer`, `Transaction`, `RecoveryCase`, `Policy`, `ActionRecord`, `AuditRecord`, `Notification`, `MessageDeliveryRecord`) carry an optional `merchant_id`.
- **Enforcement Layers:**
  1. FastAPI dependency injection (`get_current_merchant`)
  2. Repository method filters (`list_by_merchant`, `list_by_customer`)
  3. Supabase Row Level Security (RLS) policies

### 2. Messaging Architecture: Generation vs Delivery Split
- **Generation:** Handled deterministically by `MessageGenerator` (Ollama / Hugging Face / Mock) + `MessageValidator` (strict opt-out & financial integrity checks).
- **Delivery:** Provider-independent `DeliveryProviderAdapter` interface:
  - `MockDeliveryProvider`: Default, offline-safe, simulated delivery.
  - `EmailDeliveryProvider`: SMTP adapter with simulation fallback when credentials absent.
  - `WhatsAppDeliveryProvider`: WhatsApp API adapter with simulation fallback.
- **Message Records:** Every delivery attempt is tracked in `MessageDeliveryRecord`.

### 3. Idempotency & Webhook Hardening
- **`IdempotencyGuard`:** Verifies incoming `provider_event_id` against `ProcessedWebhookEventRepository`.
- **Deduplication:** Duplicate webhook deliveries are acknowledged with `200 OK` and marked `is_duplicate: True` without executing repeated recovery transitions.
- **Signature Verification:** Razorpay HMAC SHA256 signature verification enforced.

### 4. Background Execution
- **`BackgroundExecutor`:** Pluggable task execution interface.
- **`InMemoryBackgroundExecutor`:** Deterministic thread-pool based executor with retry policies and idempotency keys.
- **Zero Cost:** No paid queues (RabbitMQ/Kafka) required during development.

### 5. API Surface
- **Health:** `/health` (liveness), `/ready` (dependency readiness probe)
- **Auth:** `/api/v1/auth/register`, `/api/v1/auth/login`, `/api/v1/auth/me`
- **Dashboard:** `/api/v1/dashboard/summary`, `/api/v1/dashboard/trends`, `/api/v1/dashboard/breakdown`
- **Customers:** `/api/v1/customers`, `/api/v1/customers/{id}`, `/api/v1/customers/{id}/payments`, `/api/v1/customers/{id}/recoveries`
- **Recoveries:** `/api/v1/recoveries`, `/api/v1/recoveries/{id}`, `/api/v1/recoveries/{id}/timeline`, `/api/v1/recoveries/{id}/actions`, `/api/v1/recoveries/{id}/messages`
- **Policies:** `/api/v1/policies`, `/api/v1/policies/active`, `/api/v1/policies/{id}`
- **Settings:** `/api/v1/settings/profile`, `/api/v1/settings/notifications`
- **Notifications:** `/api/v1/notifications`, `/api/v1/notifications/unread-count`, `/api/v1/notifications/{id}/read`
- **Events & Webhooks:** `/api/v1/events/payment`, `/api/v1/events/webhook/razorpay`

---

## Zero-Cost Local Development

The system operates 100% locally with zero external paid services:
- **In-Memory Repositories** for local testing
- **Mock Messaging Provider** for message delivery simulation
- **Razorpay Test Mode** keys (`rzp_test_`) only — live keys strictly rejected
