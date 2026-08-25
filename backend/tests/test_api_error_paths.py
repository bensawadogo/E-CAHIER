"""Tests des chemins d'erreur HTTP (404) et des gardes d'injection de service."""

import pytest

from backend.app.presentation.api import credit_api, customer_api, payment_api
from backend.app.presentation.api import transaction_api


class TestNotFoundPaths:
    def test_get_credit_not_found(self, client):
        assert client.get("/api/credits/inconnu").status_code == 404

    def test_update_credit_not_found(self, client):
        r = client.put("/api/credits/inconnu", json={"amount": "100"})
        assert r.status_code == 404

    def test_delete_credit_not_found(self, client):
        assert client.delete("/api/credits/inconnu").status_code == 404

    def test_update_payment_not_found(self, client):
        r = client.put("/api/payments/inconnu", json={"amount": "100"})
        assert r.status_code == 404

    def test_delete_payment_not_found(self, client):
        assert client.delete("/api/payments/inconnu").status_code == 404

    def test_update_customer_not_found(self, client):
        r = client.put("/api/customers/inconnu", json={"name": "X"})
        assert r.status_code == 404


class TestOverdueFilter:
    def test_list_credits_overdue_only_branch(self, client):
        """Le filtre overdue_only passe par get_overdue_credits (aucun retard ici)."""
        r = client.get("/api/credits/", params={"overdue_only": "true"})
        assert r.status_code == 200
        assert r.json()["credits"] == []


class TestServiceNotInitializedGuards:
    """Chaque module API lève RuntimeError si le service n'a pas été injecté."""

    @pytest.mark.parametrize(
        "module,getter,attr",
        [
            (credit_api, "get_credit_service", "_credit_service"),
            (customer_api, "get_customer_service", "_customer_service"),
            (payment_api, "get_payment_service", "_payment_service"),
            (transaction_api, "get_transaction_service", "_transaction_service"),
        ],
        ids=["credit", "customer", "payment", "transaction"],
    )
    def test_get_service_raises_when_not_set(self, module, getter, attr, monkeypatch):
        monkeypatch.setattr(module, attr, None)
        with pytest.raises(RuntimeError, match="non initialisé"):
            getattr(module, getter)()
