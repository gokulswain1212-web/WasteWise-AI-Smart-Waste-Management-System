from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE,
    create_session_token,
    verify_login,
    verify_session_token,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


@router.post("/login")
def login(credentials: LoginRequest, response: Response) -> dict[str, str]:
    """Authenticate the configured WasteWise user."""
    email = verify_login(credentials.email, credentials.password)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_token(email),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=not get_settings().debug,
        samesite="strict",
        path="/api/v1",
    )
    return {"email": email}


@router.get("/session")
def session(request: Request) -> dict[str, str | None]:
    """Return the signed-in user for a valid browser session."""
    email = verify_session_token(request.cookies.get(SESSION_COOKIE_NAME))
    return {"email": email}


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    """Clear the browser's sign-in session cookie."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=not get_settings().debug,
        samesite="strict",
        path="/api/v1",
    )
    return {"status": "signed_out"}