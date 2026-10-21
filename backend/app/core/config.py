"""
Application configuration.

All settings are read from environment variables.
Never hardcode secrets here. Values are loaded from `backend/.env`
via python-dotenv (already called in backend/app/db/session.py).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self) -> None:
        self.project_name: str = os.getenv("PROJECT_NAME", "WasteWise AI")
        self.version: str = os.getenv("VERSION", "1.0.0")
        self.debug: bool = os.getenv("DEBUG", "true").lower() == "true"

        # Database URL (used by db/session.py)
        self.database_url: Optional[str] = os.getenv("DATABASE_URL") or None

        # API key for authenticating requests to the backend.
        # Required when DEBUG is false. In development (DEBUG=true)
        # a warning is shown if missing, but the app can still start.
        self.api_key: Optional[str] = os.getenv("API_KEY") or None

        # Secret key used to sign browser session tokens.
        # Required when DEBUG is false.
        self.secret_key: Optional[str] = os.getenv("SECRET_KEY") or None
        self.auth_email: Optional[str] = os.getenv("AUTH_EMAIL") or None
        self.auth_password_hash: Optional[str] = (
            os.getenv("AUTH_PASSWORD_HASH") or None
        )

    def is_configured(self) -> bool:
        """Return True when all production-required secrets are present."""
        if self.debug:
            return True
        return bool(
            self.api_key
            and self.secret_key
            and self.auth_email
            and self.auth_password_hash
            and self.database_url
        )

    def require_production_secrets(self) -> None:
        """Raise a clear error if running in production without secrets."""
        if not self.debug and not self.is_configured():
            missing = []
            if not self.api_key:
                missing.append("API_KEY")
            if not self.secret_key:
                missing.append("SECRET_KEY")
            if not self.auth_email:
                missing.append("AUTH_EMAIL")
            if not self.auth_password_hash:
                missing.append("AUTH_PASSWORD_HASH")
            if not self.database_url:
                missing.append("DATABASE_URL")
            raise RuntimeError(
                "Missing required production secrets: "
                + ", ".join(missing)
                + ". Set them in backend/.env before starting the API."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
