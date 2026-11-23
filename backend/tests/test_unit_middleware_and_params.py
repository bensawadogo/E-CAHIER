"""Tests unitaires : jeton Bearer (middleware) et paramètre ?updated_since=."""

from unittest.mock import patch

import hmac
import pytest
from fastapi import FastAPI, HTTPException

from fastapi.testclient import TestClient

from backend.app.presentation.dependencies import updated_since_param
from backend.app.presentation.middleware.auth import AuthMiddleware


# ---------------------------------------------------------------------------
# updated_since_param
# ---------------------------------------------------------------------------
class TestUpdatedSinceParam:
    @pytest.mark.parametrize("empty", [None, ""])
    def test_absent_means_no_filter(self, empty):
        assert updated_since_param(empty) is None

    @pytest.mark.parametrize(
        "given,expected",
        [
            ("2026-11-11T10:00:00+00:00", "2026-11-11T10:00:00+00:00"),
            ("2026-11-11T10:00:00Z", "2026-11-11T10:00:00+00:00"),
            ("2026-11-11T10:00:00", "2026-11-11T10:00:00+00:00"),  # naïf = UTC
            ("2026-11-11", "2026-11-11T00:00:00+00:00"),
            ("2026-11-11T12:00:00+02:00", "2026-11-11T10:00:00+00:00"),
            ("2026-11-11T10:00:00.250000+00:00", "2026-11-11T10:00:00.250000+00:00"),
        ],
    )
    def test_normalised_to_utc(self, given, expected):
        assert updated_since_param(given) == expected

    @pytest.mark.parametrize("bad", ["hier", "2026-13-45", "12", "null"])
    def test_invalid_raises_422(self, bad):
        with pytest.raises(HTTPException) as err:
            updated_since_param(bad)
        assert err.value.status_code == 422

    def test_normalised_value_sorts_like_stored_timestamps(self):
        # Les dates stockées sont des isoformat() UTC : la comparaison de
        # texte du SQL doit donner le même ordre que les dates.
        earlier = updated_since_param("2026-11-11T09:59:59Z")
        later = updated_since_param("2026-11-11T10:00:00Z")
        assert earlier < later


# ---------------------------------------------------------------------------
# AuthMiddleware
# ---------------------------------------------------------------------------
def app_with(token):
    app = FastAPI()
    app.add_middleware(AuthMiddleware, auth_token=token)

    @app.get("/api/ping")
    def api_ping():
        return {"ok": True}

    @app.get("/status/commits")
    def status():
        return []

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/apix")
    def not_api():
        return {"ok": True}

    return TestClient(app)


class TestAuthMiddleware:
    @pytest.mark.parametrize("path", ["/api/ping", "/status/commits"])
    def test_protected_paths_need_the_token(self, path):
        client = app_with("secret")

        assert client.get(path).status_code == 401
        assert client.get(path, headers={"Authorization": "Bearer faux"}).status_code == 401
        assert client.get(path, headers={"Authorization": "secret"}).status_code == 401
        assert client.get(path, headers={"Authorization": "Bearer secret"}).status_code == 200

    @pytest.mark.parametrize("path", ["/health", "/apix"])
    def test_other_paths_stay_open(self, path):
        assert app_with("secret").get(path).status_code == 200

    @pytest.mark.parametrize("token", ["", None])
    def test_disabled_without_token(self, token):
        with patch("backend.app.presentation.middleware.auth.settings") as settings:
            settings.AUTH_TOKEN = ""
            client = app_with(token)

            assert client.get("/api/ping").status_code == 200
            assert client.get("/status/commits").status_code == 200

    def test_comparison_is_constant_time(self):
        client = app_with("secret")
        with patch(
            "backend.app.presentation.middleware.auth.hmac.compare_digest",
            wraps=hmac.compare_digest,
        ) as compare:
            client.get("/api/ping", headers={"Authorization": "Bearer secret"})

        compare.assert_called_once_with("Bearer secret", "Bearer secret")

    def test_401_body_does_not_leak_the_expected_token(self):
        body = app_with("secret").get("/api/ping").json()

        assert "secret" not in str(body)
        assert "detail" in body
