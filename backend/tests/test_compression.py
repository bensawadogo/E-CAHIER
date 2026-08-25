"""Tests de compression GZIP pour TÂCHE 7.

La compression GZIP est activée en mode test via CAHIER_FORCE_GZIP=true
(conftest.py). Le TestClient (httpx) décompresse automatiquement, donc
r.json() fonctionne même sur une réponse compressée.
"""


class TestCompression:
    def test_compression_applied_to_large_response(self, client):
        """Les réponses >500 octets doivent être compressées (Content-Encoding: gzip)."""
        large_data = {"payload": "x" * 2000}
        r = client.post("/api/customers/_echo", json=large_data)
        assert r.status_code == 200
        assert r.headers.get("Content-Encoding") == "gzip"
        assert r.json() == large_data

    def test_no_compression_for_small_response(self, client):
        """Les réponses ≤500 octets ne doivent pas être compressées."""
        small_data = {"id": 1, "name": "Small"}
        r = client.post(
            "/api/customers/_echo",
            json=small_data,
            headers={"Authorization": "Bearer test-token"},
        )
        assert r.status_code == 200
        assert "Content-Encoding" not in r.headers
        assert r.json() == small_data


class TestEchoGuard:
    def test_echo_disabled_outside_debug(self, client, monkeypatch):
        """Garde-fou : /_echo renvoie 404 quand DEBUG=false (production)."""
        from backend.app.config import settings

        monkeypatch.setattr(settings, "DEBUG", False)
        r = client.post("/api/customers/_echo", json={"a": 1})
        assert r.status_code == 404
