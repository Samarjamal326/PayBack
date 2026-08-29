from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import setup_exception_handlers
from app.api.middleware import CorrelationIdMiddleware
from app.api.routes import router as legacy_router
from app.api.v1.auth import router as auth_router
from app.api.v1.customers import router as customers_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.events import router as events_router
from app.api.v1.health import router as health_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.payments import router as payments_router
from app.api.v1.policies import router as policies_router
from app.api.v1.recoveries import router as recoveries_router
from app.api.v1.settings import router as settings_router
from app.api.v1.webhooks import router as webhooks_router
from app.config import settings
from app.core.logging_config import setup_logging

# Initialize sanitized structured logging
setup_logging(log_level=settings.log_level)

app = FastAPI(
    title="PayBack — AI Revenue Recovery",
    description="Merchant-focused revenue recovery: identify, decide, act, measure.",
    version="0.1.0",
)

# Exception handlers
setup_exception_handlers(app)

# Middlewares
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root-level health probes (/health, /ready)
app.include_router(health_router)

# Mount legacy router for full backward compatibility
app.include_router(legacy_router)

# Mount all modular v1 routes under /api/v1
app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(customers_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(recoveries_router, prefix="/api/v1/recoveries")
app.include_router(recoveries_router, prefix="/api/v1/recovery")
app.include_router(policies_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")

