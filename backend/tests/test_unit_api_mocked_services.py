"""Couche HTTP isolée : routes FastAPI + services SIMULÉS (unittest.mock).

Aucune base de données. On vérifie ce que la couche présentation décide seule :
codes de réponse selon l'erreur du service, validation des paramètres, calcul
de la pagination, et ce qui est transmis aux services.
"""

from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.application.services import (
    CreditService,
    CustomerService,
    PaymentService,
    TransactionService,
)
from backend.app.application.services.errors import ConflictError
from backend.app.domain.entities.credit import Credit
from backend.app.domain.entities.customer import Customer
from backend.app.domain.entities.payment import Payment
from backend.app.infrastructure.sync.sync_service import SyncService
from backend.app.presentation.api import (
    credit_router,
    customer_router,
    payment_router,
    sync_router,
    transaction_router,
)


@pytest.fixture
def services():
    return {
        "customer_service": Mock(spec=CustomerService),
        "credit_service": Mock(spec=CreditService),
        "payment_service": Mock(spec=PaymentService),
        "transaction_service": Mock(spec=TransactionService),
        "sync_service": Mock(spec=SyncService),
    }


@pytest.fixture
def http(services):
    app = FastAPI()
    for router in (customer_router, credit_router, payment_router, sync_router,
                   transaction_router):
        app.include_router(router)
    for name, service in services.items():
        setattr(app.state, name, service)
    return TestClient(app)


def a_customer(**kw) -> Customer:
    return Customer(id=kw.pop("id", "c1"), name=kw.pop("name", "Awa"), **kw)


def a_credit(**kw) -> Credit:
    return Credit(id=kw.pop("id", "k1"), customer_id="c1", amount=Decimal("5000"), **kw)


def a_payment(**kw) -> Payment:
    return Payment(id=kw.pop("id", "p1"), customer_id="c1", credit_id="k1",
                   amount=Decimal("1000"), **kw)


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------
class TestCustomersApi:
    def test_create_returns_201_and_the_service_receives_the_request(self, http, services):
        services["customer_service"].create_customer.return_value = a_customer(phone="70")

        r = http.post("/api/customers/", json={"id": "abc-1", "name": "Awa", "phone": "70"})

        assert r.status_code == 201
        assert r.json()["id"] == "c1" and r.json()["phone"] == "70"
        sent = services["customer_service"].create_customer.call_args.args[0]
        assert (sent.id, sent.name) == ("abc-1", "Awa")

    def test_service_value_error_is_400(self, http, services):
        services["customer_service"].create_customer.side_effect = ValueError("Nom invalide")

        r = http.post("/api/customers/", json={"name": "Awa"})

        assert r.status_code == 400
        assert r.json()["detail"] == "Nom invalide"

    @pytest.mark.parametrize("bad_id", ["a b", "a/b", "é", "x" * 65, ""])
    def test_unsafe_id_is_rejected_before_reaching_the_service(self, http, services, bad_id):
        r = http.post("/api/customers/", json={"id": bad_id, "name": "Awa"})

        assert r.status_code == 422
        services["customer_service"].create_customer.assert_not_called()

    def test_list_computes_the_offset_from_page_and_size(self, http, services):
        services["customer_service"].get_all_customers.return_value = ([a_customer()], 41)

        r = http.get("/api/customers/", params={"page": 3, "page_size": 20})

        assert r.status_code == 200
        body = r.json()
        assert (body["total"], body["page"], body["page_size"]) == (41, 3, 20)
        services["customer_service"].get_all_customers.assert_called_once_with(
            offset=40, limit=20, updated_since=None
        )

    def test_active_only_uses_the_active_query(self, http, services):
        services["customer_service"].get_active_customers.return_value = ([], 0)

        http.get("/api/customers/", params={"active_only": "true"})

        services["customer_service"].get_active_customers.assert_called_once_with(
            offset=0, limit=50
        )
        services["customer_service"].get_all_customers.assert_not_called()

    def test_updated_since_is_normalised_to_utc_and_forwarded(self, http, services):
        services["customer_service"].get_all_customers.return_value = ([], 0)

        http.get("/api/customers/", params={"updated_since": "2026-11-11T12:00:00+02:00"})

        services["customer_service"].get_all_customers.assert_called_once_with(
            offset=0, limit=50, updated_since="2026-11-11T10:00:00+00:00"
        )

    def test_updated_since_wins_over_active_only(self, http, services):
        services["customer_service"].get_all_customers.return_value = ([], 0)

        http.get("/api/customers/",
                 params={"active_only": "true", "updated_since": "2026-01-01"})

        services["customer_service"].get_active_customers.assert_not_called()
        services["customer_service"].get_all_customers.assert_called_once()

    def test_invalid_updated_since_is_422_and_service_untouched(self, http, services):
        r = http.get("/api/customers/", params={"updated_since": "hier"})

        assert r.status_code == 422
        services["customer_service"].get_all_customers.assert_not_called()

    @pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 201}])
    def test_pagination_bounds(self, http, params):
        assert http.get("/api/customers/", params=params).status_code == 422

    def test_get_unknown_is_404(self, http, services):
        services["customer_service"].get_customer.return_value = None

        assert http.get("/api/customers/zz").status_code == 404

    def test_update_unknown_is_404(self, http, services):
        services["customer_service"].update_customer.side_effect = ValueError("introuvable")

        assert http.put("/api/customers/zz", json={"name": "X"}).status_code == 404

    def test_delete_returns_204(self, http, services):
        r = http.delete("/api/customers/c1")

        assert r.status_code == 204
        services["customer_service"].delete_customer.assert_called_once_with("c1")

    def test_search_goes_through_the_service(self, http, services):
        services["customer_service"].search_customers.return_value = [a_customer()]

        r = http.get("/api/customers/search/aw")

        assert [c["id"] for c in r.json()] == ["c1"]
        services["customer_service"].search_customers.assert_called_once_with("aw")


# ---------------------------------------------------------------------------
# Crédits
# ---------------------------------------------------------------------------
class TestCreditsApi:
    def test_create_201(self, http, services):
        services["credit_service"].create_credit.return_value = a_credit()

        r = http.post("/api/credits/", json={"customer_id": "c1", "amount": 5000})

        assert r.status_code == 201
        assert r.json()["status"] == "pending"

    def test_create_with_unknown_customer_is_400(self, http, services):
        services["credit_service"].create_credit.side_effect = ValueError("Client introuvable")

        r = http.post("/api/credits/", json={"customer_id": "zz", "amount": 5000})

        assert r.status_code == 400

    @pytest.mark.parametrize("amount", [0, -5])
    def test_non_positive_amount_is_422(self, http, services, amount):
        r = http.post("/api/credits/", json={"customer_id": "c1", "amount": amount})

        assert r.status_code == 422
        services["credit_service"].create_credit.assert_not_called()

    @pytest.mark.parametrize(
        "params,method",
        [
            ({"overdue_only": "true"}, "get_overdue_credits"),
            ({"pending_only": "true"}, "get_pending_credits"),
            ({}, "get_all_credits"),
        ],
    )
    def test_filters_pick_the_right_query(self, http, services, params, method):
        getattr(services["credit_service"], method).return_value = ([], 0)

        assert http.get("/api/credits/", params=params).status_code == 200

        getattr(services["credit_service"], method).assert_called_once()

    def test_updated_since_overrides_the_filters(self, http, services):
        services["credit_service"].get_all_credits.return_value = ([], 0)

        http.get("/api/credits/",
                 params={"overdue_only": "true", "updated_since": "2026-11-11T10:00:00Z"})

        services["credit_service"].get_overdue_credits.assert_not_called()
        services["credit_service"].get_all_credits.assert_called_once_with(
            offset=0, limit=50, updated_since="2026-11-11T10:00:00+00:00"
        )

    def test_delete_with_payments_is_409(self, http, services):
        services["credit_service"].delete_credit.side_effect = ConflictError("a des paiements")

        r = http.delete("/api/credits/k1")

        assert r.status_code == 409
        assert r.json()["detail"] == "a des paiements"

    def test_delete_unknown_is_404(self, http, services):
        services["credit_service"].delete_credit.side_effect = ValueError("introuvable")

        assert http.delete("/api/credits/zz").status_code == 404

    def test_delete_ok_is_204(self, http, services):
        assert http.delete("/api/credits/k1").status_code == 204

    def test_customer_credits_route(self, http, services):
        services["credit_service"].get_customer_credits.return_value = [a_credit()]

        r = http.get("/api/credits/customer/c1")

        assert [c["id"] for c in r.json()] == ["k1"]

    def test_invalid_status_in_update_is_422(self, http, services):
        r = http.put("/api/credits/k1", json={"status": "n'importe quoi"})

        assert r.status_code == 422
        services["credit_service"].update_credit.assert_not_called()


# ---------------------------------------------------------------------------
# Paiements
# ---------------------------------------------------------------------------
class TestPaymentsApi:
    def test_record_201(self, http, services):
        services["payment_service"].record_payment.return_value = a_payment()

        r = http.post("/api/payments/",
                      json={"customer_id": "c1", "credit_id": "k1", "amount": 1000})

        assert r.status_code == 201
        assert r.json()["credit_id"] == "k1"

    def test_wrong_customer_for_credit_is_400(self, http, services):
        services["payment_service"].record_payment.side_effect = ValueError(
            "Ce crédit n'appartient pas à ce client."
        )

        r = http.post("/api/payments/",
                      json={"customer_id": "c1", "credit_id": "k1", "amount": 1000})

        assert r.status_code == 400

    def test_credit_id_is_required(self, http, services):
        r = http.post("/api/payments/", json={"customer_id": "c1", "amount": 1000})

        assert r.status_code == 422
        services["payment_service"].record_payment.assert_not_called()

    def test_unknown_method_is_422(self, http, services):
        r = http.post("/api/payments/", json={
            "customer_id": "c1", "credit_id": "k1", "amount": 10, "method": "bitcoin"})

        assert r.status_code == 422

    def test_list_forwards_updated_since(self, http, services):
        services["payment_service"].get_all_payments.return_value = ([a_payment()], 1)

        r = http.get("/api/payments/", params={"updated_since": "2026-11-11"})

        assert r.json()["total"] == 1
        services["payment_service"].get_all_payments.assert_called_once_with(
            offset=0, limit=50, updated_since="2026-11-11T00:00:00+00:00"
        )

    def test_list_without_filter_sends_no_cursor(self, http, services):
        services["payment_service"].get_all_payments.return_value = ([], 0)

        http.get("/api/payments/")

        services["payment_service"].get_all_payments.assert_called_once_with(
            offset=0, limit=50, updated_since=None
        )

    def test_delete_unknown_is_404(self, http, services):
        services["payment_service"].delete_payment.side_effect = ValueError("introuvable")

        assert http.delete("/api/payments/zz").status_code == 404

    def test_credit_payments_route(self, http, services):
        services["payment_service"].get_credit_payments.return_value = [a_payment()]

        assert len(http.get("/api/payments/credit/k1").json()) == 1


# ---------------------------------------------------------------------------
# Transactions et synchro serveur
# ---------------------------------------------------------------------------
class TestOtherRoutes:
    def test_sync_status(self, http, services):
        services["sync_service"].get_status.return_value = {
            "is_syncing": False, "pending_count": 4, "server_url": None,
            "server_available": False,
        }

        r = http.get("/api/sync/status")

        assert r.status_code == 200 and r.json()["pending_count"] == 4

    def test_pending_limit_is_validated(self, http):
        assert http.get("/api/sync/pending", params={"limit": 0}).status_code == 422
        assert http.get("/api/sync/pending", params={"limit": 1001}).status_code == 422

    def test_transactions_list_pagination(self, http, services):
        services["transaction_service"].get_all_transactions.return_value = ([], 0)

        http.get("/api/transactions/", params={"page": 2, "page_size": 10})

        services["transaction_service"].get_all_transactions.assert_called_once_with(
            offset=10, limit=10
        )


class TestMissingWiring:
    def test_a_route_without_its_service_fails_loudly_not_silently(self):
        app = FastAPI()
        app.include_router(customer_router)  # aucun service posé sur app.state
        client = TestClient(app, raise_server_exceptions=True)

        with pytest.raises(RuntimeError, match="non initialisé"):
            client.get("/api/customers/")
