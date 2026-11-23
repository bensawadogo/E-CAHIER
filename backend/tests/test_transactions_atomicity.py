"""Atomicité et concurrence des opérations d'argent (base SQLite FICHIER).

Un crédit ou un paiement touche 3 tables : la ligne elle-même, le total du
client et le journal. Tout doit réussir ou tout échouer, même si deux requêtes
arrivent en même temps. (Base fichier : une base `:memory:` n'est pas partagée
entre les connexions.)
"""

import threading
from decimal import Decimal

import pytest

from backend.app.application.dto.credit_dto import CreateCreditRequest
from backend.app.application.dto.customer_dto import CreateCustomerRequest
from backend.app.application.dto.payment_dto import RecordPaymentRequest
from backend.app.application.services import (
    CreditService,
    CustomerService,
    PaymentService,
)
from backend.app.infrastructure.database.repositories import (
    SQLiteCreditRepository,
    SQLiteCustomerRepository,
    SQLitePaymentRepository,
    SQLiteTransactionRepository,
)
from backend.app.infrastructure.database.sqlite_connection import (
    SQLiteConnectionManager,
)


@pytest.fixture
def world(tmp_path, pii_encryptor):
    manager = SQLiteConnectionManager(db_path=str(tmp_path / "atomic.db"))
    customers = SQLiteCustomerRepository(manager, pii_encryptor)
    credits = SQLiteCreditRepository(manager)
    payments = SQLitePaymentRepository(manager)
    journal = SQLiteTransactionRepository(manager)

    class World:
        pass

    w = World()
    w.manager = manager
    w.customers, w.credits, w.payments, w.journal = customers, credits, payments, journal
    w.customer_service = CustomerService(customers)
    w.credit_service = CreditService(
        credits, customers, journal, connection_manager=manager
    )
    w.payment_service = PaymentService(
        payments, credits, customers, journal, connection_manager=manager
    )
    yield w
    manager.close_connection()


def _seed(w, amount="5000"):
    customer = w.customer_service.create_customer(CreateCustomerRequest(name="Awa"))
    credit = w.credit_service.create_credit(
        CreateCreditRequest(customer_id=customer.id, amount=Decimal(amount))
    )
    return customer, credit


def _pay(w, customer, credit, amount="100"):
    return w.payment_service.record_payment(
        RecordPaymentRequest(
            customer_id=customer.id, credit_id=credit.id, amount=Decimal(amount)
        )
    )


def test_production_services_are_wired_with_a_transaction_manager():
    """main.py doit brancher le gestionnaire, sinon rien n'est atomique."""
    import backend.app.main as main

    assert main.credit_service.connection_manager is main.sqlite_manager
    assert main.payment_service.connection_manager is main.sqlite_manager


def test_credit_creation_commits_all_three_writes(world):
    customer, credit = _seed(world)

    assert world.credits.get_by_id(credit.id) is not None
    assert world.customers.get_by_id(customer.id).total_credit == Decimal("5000")
    assert len(world.journal.get_by_customer(customer.id)) == 1


def test_credit_creation_rolls_back_everything_if_the_journal_fails(world, monkeypatch):
    customer = world.customer_service.create_customer(CreateCustomerRequest(name="Awa"))

    def boom(*args, **kwargs):
        raise RuntimeError("disque plein")

    monkeypatch.setattr(world.journal, "add", boom)
    with pytest.raises(RuntimeError):
        world.credit_service.create_credit(
            CreateCreditRequest(customer_id=customer.id, amount=Decimal("5000"))
        )

    # Ni crédit orphelin, ni dette ajoutée au client.
    assert world.credits.count_all() == 0
    assert world.customers.get_by_id(customer.id).total_credit == Decimal("0")


def test_payment_rolls_back_everything_if_the_journal_fails(world, monkeypatch):
    customer, credit = _seed(world)

    def boom(*args, **kwargs):
        raise RuntimeError("coupure")

    monkeypatch.setattr(world.journal, "add", boom)
    with pytest.raises(RuntimeError):
        _pay(world, customer, credit, "2000")

    assert world.payments.count_all() == 0
    assert world.customers.get_by_id(customer.id).total_paid == Decimal("0")
    assert world.credits.get_by_id(credit.id).status == "pending"


def test_concurrent_payments_lose_nothing(world):
    """20 paiements simultanés de 100 : le total doit faire exactement 2 000.

    Sans transaction/verrou, chaque requête lit le même total_paid puis écrit
    sa propre somme : des paiements « disparaissent » du total du client.
    """
    customer, credit = _seed(world, "5000")
    errors = []

    def pay():
        try:
            _pay(world, customer, credit, "100")
        except Exception as exc:  # pragma: no cover - affiché par l'assert
            errors.append(exc)

    threads = [threading.Thread(target=pay) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert world.payments.count_all() == 20
    assert world.customers.get_by_id(customer.id).total_paid == Decimal("2000")
    assert world.credits.get_by_id(credit.id).status == "partial"


def test_concurrent_idempotent_resend_counts_once(world):
    """Le même paiement (même id) envoyé 8 fois en parallèle n'est compté qu'une fois."""
    customer, credit = _seed(world, "5000")
    request = RecordPaymentRequest(
        id="pay-unique",
        customer_id=customer.id,
        credit_id=credit.id,
        amount=Decimal("500"),
    )
    errors = []

    def send():
        try:
            world.payment_service.record_payment(request)
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=send) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert world.payments.count_all() == 1
    assert world.customers.get_by_id(customer.id).total_paid == Decimal("500")


def test_nested_transaction_inner_failure_keeps_outer_work(world):
    manager = world.manager
    customer = world.customer_service.create_customer(CreateCustomerRequest(name="Awa"))

    with manager.transaction() as outer:
        outer.execute(
            "UPDATE customers SET is_active = 0 WHERE id = ?", (customer.id,)
        )
        with pytest.raises(ValueError):
            with manager.transaction() as inner:
                inner.execute(
                    "UPDATE customers SET is_active = 1 WHERE id = ?", (customer.id,)
                )
                raise ValueError("annulé")

    # Le travail du bloc extérieur est validé, celui de l'intérieur annulé.
    assert world.customers.get_by_id(customer.id).is_active is False


def test_connection_is_reused_between_transactions(world):
    manager = world.manager
    with manager.transaction() as first:
        pass
    with manager.transaction() as second:
        pass
    assert first is second


def test_concurrent_plain_requests_share_the_connection_safely(world):
    """Créations + lectures simultanées (sans transaction explicite).

    FastAPI exécute les routes dans un pool de threads ; sans verrou autour de
    la connexion partagée, sqlite3 lève InterfaceError/SystemError.
    """
    errors = []

    def create(i):
        try:
            world.customer_service.create_customer(
                CreateCustomerRequest(name=f"Client {i}")
            )
            world.customer_service.get_all_customers(offset=0, limit=50)
        except Exception as exc:  # pragma: no cover
            errors.append(type(exc).__name__)

    threads = [threading.Thread(target=create, args=(i,)) for i in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert world.customers.count_all() == 30
