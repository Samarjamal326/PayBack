from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(
    title="PayBack — AI Revenue Recovery",
    description="Merchant-focused revenue recovery: identify, decide, act, measure.",
    version="0.1.0",
)

app.include_router(router)
