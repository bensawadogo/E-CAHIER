"""Modifier ou supprimer un crédit/paiement garde les soldes justes.

Avant : PUT/DELETE changeaient la ligne mais pas le total du client ni le
statut du crédit, et supprimer un crédit déjà payé donnait une erreur 500
(clé étrangère). Règles : dette = crédits non annulés ; payé = paiements ;
statut du crédit d'après ses paiements.
"""

import time
from decimal import Decimal

import pytest

from backend.app.application.dto.credit_dto import CreateCreditRequest, UpdateCreditRequest
from backend.app.application.dto.customer_dto import CreateCustomerRequest
from backend.app.application.dto.payment_dto import RecordPaymentRequest, UpdatePaymentRequest
from backend.app.application.services import CreditService, CustomerService, PaymentService
from backend.app.application.services.errors import ConflictError
from backend.app.infrastructure.database.repositories import (
    SQLiteCreditRepository,
    SQLiteCustomerRepository,
    SQLitePaymentRepository,
    SQLiteTransactionRepository,
)
from backend.app.infrastructure.database.sqlite_connection import SQLiteConnectionManager


@pytest.fixture
def w(tmp_path, pii_encryptor):
    manager = SQLiteConnectionManager(db_path=str(tmp_path / "ledger.db"))

    class World:
        pass

    x = World()
    x.customers = SQLiteCustomerRepository(manager, pii_encryptor)
    x.credits = SQLiteCreditRepository(manager)
    x.payments = SQLitePaymentRepository(manager)
    journal = SQLiteTransactionRepository(manager)
    x.customer_service = CustomerService(x.customers)
    x.credit_service = CreditService(
        x.credits, x.customers, journal,
        connection_manager=manager, payment_repository=x.payments,
    )
    x.payment_service = PaymentService(
        x.payments, x.credits, x.customers, journal, connection_manager=manager
    )
    x.manager = manager
    yield x
    manager.close_connection()


def _credit(w, amount="5000"):
    customer = w.customer_service.create_customer(CreateCustomerRequest(name="Awa"))
    credit = w.credit_service.create_credit(
        CreateCreditRequest(customer_id=customer.id, amount=Decimal(amount))
    )
    return customer, credit


def _pay(w, customer, credit, amount):
    return w.payment_service.record_payment(
        RecordPaymentRequest(
            customer_id=customer.id, credit_id=credit.id, amount=Decimal(amount)
        )
    )


def _totals(w, customer):
    c = w.customers.get_by_id(customer.id)
    return c.total_credit, c.total_paid


def test_changing_the_amount_updates_customer_debt_and_status(w):
    customer, credit = _credit(w, "5000")
    _pay(w, customer, credit, "2000")
    assert w.credits.get_by_id(credit.id).status == "partial"

    w.credit_service.update_credit(credit.id, UpdateCreditRequest(amount=Decimal("2000")))
    assert _totals(w, customer) == (Decimal("2000"), Decimal("2000"))
    assert w.credits.get_by_id(credit.id).status == "paid"  # 2000 payés sur 2000

    w.credit_service.update_credit(credit.id, UpdateCreditRequest(amount=Decimal("8000")))
    assert _totals(w, customer) == (Decimal("8000"), Decimal("2000"))
    assert w.credits.get_by_id(credit.id).status == "partial"


def test_cancelling_a_credit_removes_it_from_the_debt(w):
    customer, credit = _credit(w, "5000")
    w.credit_service.update_credit(credit.id, UpdateCreditRequest(status="cancelled"))
    assert _totals(w, customer)[0] == Decimal("0")
    assert w.credits.get_by_id(credit.id).status == "cancelled"


def test_cancelled_credit_stays_cancelled_when_edited(w):
    customer, credit = _credit(w, "5000")
    w.credit_service.update_credit(credit.id, UpdateCreditRequest(status="cancelled"))
    w.credit_service.update_credit(credit.id, UpdateCreditRequest(description="oups"))
    assert w.credits.get_by_id(credit.id).status == "cancelled"


def test_deleting_an_unpaid_credit_removes_its_debt(w):
    customer, credit = _credit(w, "5000")
    w.credit_service.delete_credit(credit.id)
    assert _totals(w, customer) == (Decimal("0"), Decimal("0"))
    assert w.credits.get_by_id(credit.id) is None


def test_cannot_delete_a_credit_that_has_payments(w):
    customer, credit = _credit(w, "5000")
    _pay(w, customer, credit, "1000")
    with pytest.raises(ConflictError):
        w.credit_service.delete_credit(credit.id)
    # Rien n'a bougé.
    assert w.credits.get_by_id(credit.id) is not None
    assert _totals(w, customer) == (Decimal("5000"), Decimal("1000"))


def test_deleting_a_payment_reopens_the_credit(w):
    customer, credit = _credit(w, "5000")
    p1 = _pay(w, customer, credit, "2000")
    p2 = _pay(w, customer, credit, "3000")
    assert w.credits.get_by_id(credit.id).status == "paid"

    w.payment_service.delete_payment(p2.id)
    assert w.credits.get_by_id(credit.id).status == "partial"
    assert _totals(w, customer) == (Decimal("5000"), Decimal("2000"))

    w.payment_service.delete_payment(p1.id)
    assert w.credits.get_by_id(credit.id).status == "pending"
    assert _totals(w, customer) == (Decimal("5000"), Decimal("0"))


def test_changing_a_payment_amount_updates_totals_and_status(w):
    customer, credit = _credit(w, "5000")
    payment = _pay(w, customer, credit, "1000")

    w.payment_service.update_payment(payment.id, UpdatePaymentRequest(amount=Decimal("5000")))
    assert w.credits.get_by_id(credit.id).status == "paid"
    assert _totals(w, customer) == (Decimal("5000"), Decimal("5000"))

    w.payment_service.update_payment(payment.id, UpdatePaymentRequest(amount=Decimal("500")))
    assert w.credits.get_by_id(credit.id).status == "partial"
    assert _totals(w, customer) == (Decimal("5000"), Decimal("500"))


def test_a_failure_midway_rolls_everything_back(w, monkeypatch):
    customer, credit = _credit(w, "5000")
    payment = _pay(w, customer, credit, "5000")

    def boom(*args, **kwargs):
        raise RuntimeError("coupure pendant la mise à jour du crédit")

    monkeypatch.setattr(w.credits, "update", boom)
    with pytest.raises(RuntimeError):
        w.payment_service.delete_payment(payment.id)

    # Le paiement n'a pas été supprimé à moitié.
    assert w.payments.get_by_id(payment.id) is not None
    assert _totals(w, customer) == (Decimal("5000"), Decimal("5000"))


# --- updated_at : condition de la lecture incrémentale ----------------------
def test_every_edit_is_stamped_so_phones_receive_it(client):
    customer = client.post("/api/customers/", json={"name": "Awa"}).json()
    time.sleep(0.02)
    cursor = customer["updated_at"]

    edited = client.put(
        f"/api/customers/{customer['id']}", json={"name": "Awa Ouédraogo"}
    ).json()
    assert edited["updated_at"] > cursor

    changed = client.get(
        "/api/customers/", params={"updated_since": edited["updated_at"]}
    ).json()
    assert customer["id"] in [c["id"] for c in changed["customers"]]


def test_credit_and_payment_edits_are_stamped_too(client):
    cid = client.post("/api/customers/", json={"name": "Awa"}).json()["id"]
    credit = client.post("/api/credits/", json={"customer_id": cid, "amount": 5000}).json()
    payment = client.post(
        "/api/payments/",
        json={"customer_id": cid, "credit_id": credit["id"], "amount": 100},
    ).json()
    time.sleep(0.02)

    credit2 = client.put(f"/api/credits/{credit['id']}", json={"description": "riz"}).json()
    payment2 = client.put(f"/api/payments/{payment['id']}", json={"note": "ok"}).json()

    assert credit2["updated_at"] > credit["updated_at"]
    assert payment2["updated_at"] > payment["updated_at"]


# --- API -------------------------------------------------------------------
def test_api_deleting_a_paid_credit_is_409_not_500(client):
    cid = client.post("/api/customers/", json={"name": "Awa"}).json()["id"]
    credit_id = client.post("/api/credits/", json={"customer_id": cid, "amount": 5000}).json()["id"]
    client.post(
        "/api/payments/",
        json={"customer_id": cid, "credit_id": credit_id, "amount": 100},
    )

    r = client.delete(f"/api/credits/{credit_id}")

    assert r.status_code == 409
    assert "paiements" in r.json()["detail"]
    assert client.get(f"/api/credits/{credit_id}").status_code == 200


def test_api_customer_totals_follow_payment_deletion(client):
    cid = client.post("/api/customers/", json={"name": "Awa"}).json()["id"]
    credit_id = client.post("/api/credits/", json={"customer_id": cid, "amount": 5000}).json()["id"]
    pid = client.post(
        "/api/payments/",
        json={"customer_id": cid, "credit_id": credit_id, "amount": 2000},
    ).json()["id"]
    assert Decimal(client.get(f"/api/customers/{cid}").json()["total_paid"]) == 2000

    assert client.delete(f"/api/payments/{pid}").status_code == 204

    customer = client.get(f"/api/customers/{cid}").json()
    assert Decimal(customer["total_paid"]) == 0
    assert client.get(f"/api/credits/{credit_id}").json()["status"] == "pending"


def test_production_wiring_recalculates_balances():
    import backend.app.main as main

    assert main.credit_service.payment_repository is main.payment_repo
