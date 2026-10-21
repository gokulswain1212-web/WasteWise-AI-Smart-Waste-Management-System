"""Password hashing, signed browser sessions, and API-key verification."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as Base64Error
from typing import Optional

from fastapi import HTTPException, status
from fastapi.security import APIKeyHeader

from app.core.config import get_settings

# Header name clients must send: X-API-KEY: <your-key>
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)
SESSION_COOKIE_NAME = "wastewise_session"
SESSION_MAX_AGE = 8 * 60 * 60


def generate_api_key() -> str:
    """Generate a new secure API key. Print this once and store it safely."""
    return secrets.token_urlsafe(32)


def generate_secret_key() -> str:
    """Generate a secret key for signing browser sessions."""
    return secrets.token_urlsafe(32)


def hash_password(password: str) -> str:
    """Hash a plaintext password using PBKDF2-SHA256."""
    iterations = 600_000
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${password_hash}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a PBKDF2-SHA256 password hash created by hash_password."""
    try:
        algorithm, iterations, salt, expected_hash = hashed_password.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(derived, expected_hash)


def verify_login(email: str, password: str) -> str:
    """Validate the configured login and return its email."""
    settings = get_settings()
    if not settings.auth_email or not settings.auth_password_hash:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email and password sign-in is not configured on the server.",
        )

    password_valid = verify_password(password, settings.auth_password_hash)
    email_valid = secrets.compare_digest(
        email.strip().casefold(), settings.auth_email.strip().casefold()
    )
    if not (email_valid and password_valid):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    return settings.auth_email


def create_session_token(email: str) -> str:
    """Create a signed, expiring session token for the HttpOnly session cookie."""
    secret_key = get_settings().secret_key
    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session signing is not configured on the server.",
        )

    payload = json.dumps(
        {"sub": email, "exp": int(time.time()) + SESSION_MAX_AGE},
        separators=(",", ":"),
    ).encode("utf-8")
    encoded_payload = urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    signature = hmac.new(
        secret_key.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256
    ).digest()
    encoded_signature = urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{encoded_payload}.{encoded_signature}"


def verify_session_token(token: str | None) -> str | None:
    """Return the session email when a token is valid and unexpired."""
    settings = get_settings()
    if not token or not settings.secret_key or len(token) > 4096:
        return None

    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        signature = urlsafe_b64decode(
            encoded_signature + "=" * (-len(encoded_signature) % 4)
        )
        payload = urlsafe_b64decode(
            encoded_payload + "=" * (-len(encoded_payload) % 4)
        )
        claims = json.loads(payload)
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError, Base64Error):
        return None

    expected_signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    email = claims.get("sub") if isinstance(claims, dict) else None
    expires_at = claims.get("exp") if isinstance(claims, dict) else None
    if (
        not isinstance(email, str)
        or type(expires_at) is not int
        or expires_at <= int(time.time())
        or not settings.auth_email
        or not secrets.compare_digest(email.casefold(), settings.auth_email.casefold())
    ):
        return None
    return email


def verify_api_key(
    api_key: Optional[str] = None,
) -> str:
    """
    Validate the API key sent in the X-API-KEY header.

    Returns the key if valid. Raises HTTP 401 if missing or invalid.
    Uses constant-time comparison to prevent timing attacks.
    """
    settings = get_settings()

    # If no API key is configured at all, authentication is unavailable.
    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured on the server.",
        )

    # Missing header
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Send it in the X-API-KEY header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Constant-time comparison prevents attackers from guessing the key
    # by measuring how long the check takes.
    if not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key
