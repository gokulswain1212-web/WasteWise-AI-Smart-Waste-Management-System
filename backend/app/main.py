from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request, Security, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.analytics import router as analytics_router
from app.core.config import get_settings
from app.core.security import (
    SESSION_COOKIE_NAME,
    api_key_header,
    verify_api_key,
    verify_session_token,
)
from app.db.session import database_status


settings = get_settings()

# In production mode, refuse to start without required secrets.
# In development mode (DEBUG=true), a warning is shown but the app starts.
if not settings.debug:
    settings.require_production_secrets()


def get_api_identity(
    request: Request,
    api_key: str | None = Security(api_key_header),
) -> str:
    """
    Accept a valid browser session or an explicitly supplied API key.

    Used on business and database routes; /health remains public.
    """
    email = verify_session_token(request.cookies.get(SESSION_COOKIE_NAME))
    if email:
        return email

    return verify_api_key(api_key)


# Router-level dependency: every business API route requires a session or API key.
# /health is registered directly on the app, so it stays public.
app = FastAPI(
    title="WasteWise AI API",
    description=(
        "Grocery demand, inventory expiry-risk, food-waste, and discount "
        "scenario analytics for WasteWise AI clients."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(
    analytics_router,
    dependencies=[Depends(get_api_identity)],
)


@app.get("/health", tags=["system"])
def health() -> dict:
    """
    Public health endpoint.

    Returns only basic service status. No database credentials,
    internal configuration, or secrets are exposed.
    """
    database = database_status()
    ready = database["connected"] and database["schema_ready"]
    if not settings.debug and not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Production database connection or schema is not ready.",
        )

    return {
        "status": "ok" if ready else "degraded",
        "service": "wastewise-api",
        "version": settings.version,
        "database_connected": database["connected"],
        "database_schema_ready": database["schema_ready"],
    }