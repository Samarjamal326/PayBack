from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import HealthResponse, ReadinessResponse
from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Liveness probe: verifies that the FastAPI application is alive and accepting requests."""
    return HealthResponse(
        status="ok",
        app_env=settings.app_env,
        razorpay_mode=settings.razorpay_mode,
    )


@router.get("/ready", response_model=ReadinessResponse)
def readiness_check() -> ReadinessResponse:
    """Readiness probe: distinguishes application running from dependencies ready/unavailable."""
    deps = {
        "supabase": "configured" if settings.is_supabase_configured() else "in_memory_fallback",
        "razorpay": settings.razorpay_mode,
        "llm_provider": settings.llm_provider,
        "messaging_provider": settings.message_delivery_provider,
    }
    return ReadinessResponse(
        status="ready",
        app_env=settings.app_env,
        database="supabase" if settings.is_supabase_configured() else "in_memory",
        razorpay=settings.razorpay_mode,
        llm=settings.llm_provider,
        messaging=settings.message_delivery_provider,
        dependencies=deps,
    )
