"""
Tests for configuration and security utilities.
Run with: python -m pytest backend/tests/
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.security import (
    generate_api_key,
    generate_secret_key,
    hash_password,
    verify_password,
    verify_login,
    create_session_token,
    verify_session_token,
    verify_api_key,
    api_key_header,
)


class TestSettings:
    def test_defaults_are_development(self):
        settings = Settings()
        assert settings.debug is True
        assert settings.project_name == "WasteWise AI"

    def test_is_configured_true_with_secrets(self):
        with patch.dict(
            os.environ,
            {
                "API_KEY": "test-key",
                "SECRET_KEY": "test-secret",
                "AUTH_EMAIL": "test@example.com",
                "AUTH_PASSWORD_HASH": "hash",
                "DATABASE_URL": "mysql+pymysql://user:pass@db/wastewise",
            },
        ):
            settings = Settings()
            settings.debug = False
            assert settings.is_configured() is True

    def test_is_configured_false_without_secrets_in_production(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            settings.debug = False
            assert settings.is_configured() is False

    def test_require_production_secrets_raises_when_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            settings.debug = False
            with pytest.raises(RuntimeError, match="Missing required production secrets"):
                settings.require_production_secrets()

    def test_require_production_secrets_passes_with_secrets(self):
        with patch.dict(
            os.environ,
            {
                "API_KEY": "k",
                "SECRET_KEY": "s",
                "AUTH_EMAIL": "test@example.com",
                "AUTH_PASSWORD_HASH": "hash",
                "DATABASE_URL": "mysql+pymysql://user:pass@db/wastewise",
            },
        ):
            settings = Settings()
            settings.debug = False
            settings.require_production_secrets()  # should not raise


class TestSecurity:
    def test_generate_api_key_returns_string(self):
        key = generate_api_key()
        assert isinstance(key, str)
        assert len(key) > 0

    def test_generate_secret_key_returns_string(self):
        key = generate_secret_key()
        assert isinstance(key, str)
        assert len(key) > 0

    def test_hash_and_verify_password(self):
        hashed = hash_password("mypassword")
        assert hashed != "mypassword"  # not stored plaintext
        assert verify_password("mypassword", hashed) is True
        assert verify_password("wrongpassword", hashed) is False
        assert verify_password("mypassword", "invalid-hash") is False

    def test_verify_login_uses_configured_credentials(self):
        hashed = hash_password("test-password")
        with patch.dict(
            os.environ,
            {"AUTH_EMAIL": "test@example.com", "AUTH_PASSWORD_HASH": hashed},
        ):
            get_settings.cache_clear()
            assert verify_login("TEST@example.com", "test-password") == "test@example.com"
            with pytest.raises(Exception) as exc_info:
                verify_login("test@example.com", "wrong-password")
            assert exc_info.value.status_code == 401
        get_settings.cache_clear()

    def test_session_token_signature_and_expiration(self):
        with patch.dict(
            os.environ,
            {
                "SECRET_KEY": "session-test-secret",
                "AUTH_EMAIL": "test@example.com",
            },
        ):
            get_settings.cache_clear()
            token = create_session_token("test@example.com")
            assert verify_session_token(token) == "test@example.com"
            assert verify_session_token(f"{token}tampered") is None
            assert verify_session_token(None) is None
        get_settings.cache_clear()

    def test_verify_api_key_valid(self):
        with patch.dict(os.environ, {"API_KEY": "valid-key-123"}):
            get_settings.cache_clear()
            result = verify_api_key("valid-key-123")
            assert result == "valid-key-123"

    def test_verify_api_key_missing(self):
        with patch.dict(os.environ, {"API_KEY": "valid-key-123"}):
            get_settings.cache_clear()
            with pytest.raises(Exception) as exc_info:
                verify_api_key(None)
            assert exc_info.value.status_code == 401

    def test_verify_api_key_invalid(self):
        with patch.dict(os.environ, {"API_KEY": "valid-key-123"}):
            get_settings.cache_clear()
            with pytest.raises(Exception) as exc_info:
                verify_api_key("wrong-key")
            assert exc_info.value.status_code == 401

    def test_verify_api_key_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            get_settings.cache_clear()
            with pytest.raises(Exception) as exc_info:
                verify_api_key("any-key")
            assert exc_info.value.status_code == 503


class TestFastAPIIntegration:
    """Integration tests against the actual FastAPI application."""

    def setup_method(self):
        os.environ["API_KEY"] = "test-key-123"
        os.environ["SECRET_KEY"] = "test-secret-456"
        os.environ["DEBUG"] = "true"
        os.environ["AUTH_EMAIL"] = "manager@example.com"
        os.environ["AUTH_PASSWORD_HASH"] = hash_password("test-password")
        get_settings.cache_clear()
        sys.modules.pop("app.main", None)

    def teardown_method(self):
        for key in [
            "API_KEY",
            "SECRET_KEY",
            "DEBUG",
            "AUTH_EMAIL",
            "AUTH_PASSWORD_HASH",
        ]:
            os.environ.pop(key, None)
        get_settings.cache_clear()
        sys.modules.pop("app.main", None)

    def _make_client(self):
        from app.main import app
        return TestClient(app)

    def test_health_endpoint_public_no_key(self):
        client = self._make_client()
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["service"] == "wastewise-api"
        assert "database" not in data

    def test_health_endpoint_with_key(self):
        client = self._make_client()
        response = client.get("/health", headers={"X-API-KEY": "test-key-123"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"

    def test_login_endpoint_accepts_configured_credentials(self):
        client = self._make_client()
        assert client.get("/api/v1/auth/session").json()["email"] is None
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "manager@example.com", "password": "test-password"},
        )
        assert response.status_code == 200
        assert response.json()["email"] == "manager@example.com"
        assert "httponly" in response.headers["set-cookie"].lower()
        assert client.get("/api/v1/auth/session").status_code == 200
        assert client.get("/api/v1/dashboard").status_code != 401

        logout_response = client.post("/api/v1/auth/logout")
        assert logout_response.status_code == 200
        assert client.get("/api/v1/auth/session").json()["email"] is None
        assert client.get("/api/v1/dashboard").status_code == 401

    def test_login_endpoint_rejects_invalid_credentials(self):
        client = self._make_client()
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "manager@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401

    def test_protected_route_valid_key(self):
        client = self._make_client()
        response = client.get(
            "/api/v1/dashboard", headers={"X-API-KEY": "test-key-123"}
        )
        assert response.status_code != 401

    def test_protected_route_missing_key(self):
        client = self._make_client()
        response = client.get("/api/v1/dashboard")
        assert response.status_code == 401

    def test_protected_route_invalid_key(self):
        client = self._make_client()
        response = client.get(
            "/api/v1/dashboard", headers={"X-API-KEY": "wrong-key"}
        )
        assert response.status_code == 401

    def test_all_api_v1_routes_require_auth(self):
        client = self._make_client()
        routes = [
            "/api/v1/dashboard",
            "/api/v1/monitoring",
            "/api/v1/predictions/food-waste",
            "/api/v1/predictions/expiry-risk",
            "/api/v1/recommendations/discounts",
            "/api/v1/database/status",
        ]
        for route in routes:
            response = client.get(route)
            assert response.status_code == 401, f"Route {route} should require auth"