"""Tests unitaires avec des dépôts SIMULÉS (unittest.mock) : aucune base.

On vérifie la logique des services et des règles de solde (ledger) : quelles
lectures/écritures sont faites, dans quel ordre, avec quelle connexion, et
surtout ce qui n'est PAS fait (pas d'écriture inutile, pas de doublon).
"""

from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import MagicMock, Mock, call

import pytest

from backend.app.application.dto.credit_dto import CreateCreditRequest, UpdateCreditRequest
from backend.app.application.dto.payment_dto import RecordPaymentRequest, UpdatePaymentRequest
from backend.app.application.services import CreditService, PaymentService
from backend.app.application.services.errors import ConflictError
from backend.app.application.services.ledger import (
    refresh_after_payment_change,
    sync_credit_status,
    sync_customer_totals,
)
from backend.app.domain.entities.credit import Credit
from backend.app.domain.entities.customer import Customer
from backend.app.domain.entities.payment import Payment
from backend.app.domain.repositories.credit_repository import CreditRepository
from backend.app.domain.repositories.customer_repository import CustomerRepository
from backend.app.domain.repositories.payment_repository import PaymentRepository
from backend.app.domain.repositories.transaction_repository import TransactionRepository


def D(value) -> Decimal:
    return Decimal(str(value))


def make_credit(amount=5000, status="pending", customer_id="c1", id="k1") -> Credit:
    return Credit(id=id, customer_id=customer_id, amount=D(amount), status=status)


def make_customer(total_credit=0, total_paid=0, id="c1") -> Customer:
    return Customer(id=id, name="Awa", total_credit=D(total_credit), total_paid=D(total_paid))


def make_payment(amount=1000, id="p1", customer_id="c1", credit_id="k1") -> Payment:
    return Payment(id=id, customer_id=customer_id, credit_id=credit_id, amount=D(amount))


# `spec=` : un appel à une méthode qui n'existe pas dans le contrat du dépôt
# échoue (attrape les fautes de frappe), sans imposer la signature.
@pytest.fixture
def credits():
    return Mock(spec=CreditRepository)


@pytest.fixture
def customers():
    return Mock(spec=CustomerRepository)


@pytest.fixture
def payments():
    return Mock(spec=PaymentRepository)


@pytest.fixture
def journal():
    return Mock(spec=TransactionRepository)


# ---------------------------------------------------------------------------
# ledger : règles de calcul des soldes
# ---------------------------------------------------------------------------
class TestSyncCreditStatus:
    @pytest.mark.parametrize(
        "paid,amount,current,expected",
        [
            (0, 5000, "paid", "pending"),       # tout supprimé
            (2000, 5000, "pending", "partial"),
            (5000, 5000, "partial", "paid"),
            (7000, 5000, "partial", "paid"),    # trop-perçu accepté
            (0, 5000, "pending", "pending"),    # inchangé
        ],
    )
    def test_status_follows_payments(self, payments, paid, amount, current, expected):
        payments.total_paid_for_credit.return_value = D(paid)
        credit = make_credit(amount, current)

        changed = sync_credit_status(credit, payments, conn="TX")

        assert credit.status == expected
        assert changed is (expected != current)
        payments.total_paid_for_credit.assert_called_once_with("k1", conn="TX")

    def test_cancelled_credit_is_left_alone_without_reading_payments(self, payments):
        credit = make_credit(status="cancelled")

        assert sync_credit_status(credit, payments) is False

        assert credit.status == "cancelled"
        payments.total_paid_for_credit.assert_not_called()


class TestSyncCustomerTotals:
    def test_writes_new_totals_when_they_differ(self, customers, credits, payments):
        customer = make_customer(total_credit=9000, total_paid=100)
        customers.get_by_id.return_value = customer
        credits.total_amount_for_customer.return_value = D(5000)
        payments.total_paid_for_customer.return_value = D(2000)

        assert sync_customer_totals("c1", customers, credits, payments, conn="TX") is True

        assert (customer.total_credit, customer.total_paid) == (D(5000), D(2000))
        customers.update.assert_called_once_with(customer, conn="TX")

    def test_no_write_when_totals_already_right(self, customers, credits, payments):
        customers.get_by_id.return_value = make_customer(5000, 2000)
        credits.total_amount_for_customer.return_value = D(5000)
        payments.total_paid_for_customer.return_value = D(2000)

        assert sync_customer_totals("c1", customers, credits, payments) is False

        customers.update.assert_not_called()

    def test_unknown_customer_is_ignored(self, customers, credits, payments):
        customers.get_by_id.return_value = None

        assert sync_customer_totals("zz", customers, credits, payments) is False

        credits.total_amount_for_customer.assert_not_called()


class TestRefreshAfterPaymentChange:
    def test_credit_saved_only_if_its_status_changed(self, customers, credits, payments):
        credit = make_credit(5000, "paid")
        credits.get_by_id.return_value = credit
        payments.total_paid_for_credit.return_value = D(2000)
        customers.get_by_id.return_value = make_customer(5000, 5000)
        credits.total_amount_for_customer.return_value = D(5000)
        payments.total_paid_for_customer.return_value = D(2000)

        refresh_after_payment_change("c1", "k1", customers, credits, payments, conn="TX")

        assert credit.status == "partial"
        credits.update.assert_called_once_with(credit, conn="TX")
        customers.update.assert_called_once()

    def test_nothing_written_when_nothing_changed(self, customers, credits, payments):
        credits.get_by_id.return_value = make_credit(5000, "partial")
        payments.total_paid_for_credit.return_value = D(2000)
        customers.get_by_id.return_value = make_customer(5000, 2000)
        credits.total_amount_for_customer.return_value = D(5000)
        payments.total_paid_for_customer.return_value = D(2000)

        refresh_after_payment_change("c1", "k1", customers, credits, payments)

        credits.update.assert_not_called()
        customers.update.assert_not_called()

    def test_payment_without_credit_still_fixes_customer(self, customers, credits, payments):
        customers.get_by_id.return_value = make_customer(5000, 9999)
        credits.total_amount_for_customer.return_value = D(5000)
        payments.total_paid_for_customer.return_value = D(0)

        refresh_after_payment_change("c1", None, customers, credits, payments)

        credits.get_by_id.assert_not_called()
        customers.update.assert_called_once()


# ---------------------------------------------------------------------------
# CreditService
# ---------------------------------------------------------------------------
class TestCreditServiceMocked:
    @pytest.fixture
    def svc(self, credits, customers, journal, payments):
        return CreditService(credits, customers, journal, payment_repository=payments)

    def test_create_credit_unknown_customer_writes_nothing(self, svc, credits, customers):
        customers.get_by_id.return_value = None

        with pytest.raises(ValueError, match="Client introuvable"):
            svc.create_credit(CreateCreditRequest(customer_id="zz", amount=D(100)))

        credits.add.assert_not_called()
        customers.update.assert_not_called()

    def test_create_credit_adds_debt_and_journal(self, svc, credits, customers, journal):
        customer = make_customer(1000, 0)
        customers.get_by_id.return_value = customer
        credits.add.side_effect = lambda credit, conn=None: credit

        svc.create_credit(CreateCreditRequest(customer_id="c1", amount=D(500)))

        assert customer.total_credit == D(1500)
        customers.update.assert_called_once()
        entry = journal.add.call_args.args[0]
        assert (entry.type, entry.amount) == ("credit", D(500))

    def test_idempotent_replay_returns_existing_without_any_write(
        self, svc, credits, customers, journal
    ):
        customers.get_by_id.return_value = make_customer()
        existing = make_credit(id="abc-123")
        credits.get_by_id.return_value = existing

        result = svc.create_credit(
            CreateCreditRequest(id="abc-123", customer_id="c1", amount=D(5000))
        )

        assert result is existing
        credits.add.assert_not_called()
        customers.update.assert_not_called()
        journal.add.assert_not_called()

    def test_replay_with_an_id_owned_by_another_customer_is_refused(
        self, svc, credits, customers
    ):
        customers.get_by_id.return_value = make_customer()
        credits.get_by_id.return_value = make_credit(id="abc-123", customer_id="AUTRE")

        with pytest.raises(ValueError, match="Identifiant déjà utilisé"):
            svc.create_credit(
                CreateCreditRequest(id="abc-123", customer_id="c1", amount=D(5000))
            )

        credits.add.assert_not_called()

    def test_update_unknown_credit(self, svc, credits):
        credits.get_by_id.return_value = None

        with pytest.raises(ValueError, match="introuvable"):
            svc.update_credit("zz", UpdateCreditRequest(amount=D(10)))

        credits.update.assert_not_called()

    def test_explicit_status_is_honoured_without_recomputing_it(
        self, svc, credits, customers, payments
    ):
        credit = make_credit(5000, "pending")
        credits.get_by_id.return_value = credit
        credits.update.side_effect = lambda c, conn=None: c
        customers.get_by_id.return_value = make_customer(5000, 0)
        credits.total_amount_for_customer.return_value = D(0)
        payments.total_paid_for_customer.return_value = D(0)

        svc.update_credit("k1", UpdateCreditRequest(status="cancelled"))

        assert credit.status == "cancelled"
        payments.total_paid_for_credit.assert_not_called()
        customers.update.assert_called_once()  # la dette tombe à 0

    def test_delete_with_payments_is_a_conflict_and_deletes_nothing(
        self, svc, credits, payments
    ):
        credits.get_by_id.return_value = make_credit()
        payments.get_by_credit.return_value = [make_payment()]

        with pytest.raises(ConflictError):
            svc.delete_credit("k1")

        credits.delete.assert_not_called()

    def test_delete_without_payments_deletes_then_fixes_totals(
        self, svc, credits, customers, payments
    ):
        credits.get_by_id.return_value = make_credit()
        payments.get_by_credit.return_value = []
        customers.get_by_id.return_value = make_customer(5000, 0)
        credits.total_amount_for_customer.return_value = D(0)
        payments.total_paid_for_customer.return_value = D(0)

        svc.delete_credit("k1")

        credits.delete.assert_called_once_with("k1", conn=None)
        customers.update.assert_called_once()

    def test_delete_unknown_credit_keeps_the_old_message(self, svc, credits):
        credits.get_by_id.return_value = None

        with pytest.raises(ValueError, match="Aucun crédit trouvé"):
            svc.delete_credit("zz")

    def test_without_payment_repository_totals_are_not_recomputed(
        self, credits, customers, journal
    ):
        svc = CreditService(credits, customers, journal)  # pas de payment_repository
        credits.get_by_id.return_value = make_credit()
        credits.update.side_effect = lambda c, conn=None: c

        svc.update_credit("k1", UpdateCreditRequest(description="riz"))

        customers.update.assert_not_called()


# ---------------------------------------------------------------------------
# Transactions : les dépôts reçoivent la MÊME connexion
# ---------------------------------------------------------------------------
class TestTransactionWiring:
    @pytest.fixture
    def manager(self):
        mgr = MagicMock()
        mgr.entered = []
        mgr.exited_with = []

        @contextmanager
        def transaction():
            mgr.entered.append(True)
            try:
                yield "TX-CONN"
            except BaseException as exc:
                mgr.exited_with.append(type(exc))
                raise

        mgr.transaction.side_effect = transaction
        return mgr

    def test_payment_writes_all_share_one_connection(
        self, manager, payments, credits, customers, journal
    ):
        svc = PaymentService(payments, credits, customers, journal, connection_manager=manager)
        customer = make_customer(5000, 0)
        credit = make_credit(5000)
        customers.get_by_id.return_value = customer
        credits.get_by_id.return_value = credit
        payments.get_by_id.return_value = None
        payments.add.side_effect = lambda p, conn=None: p
        payments.total_paid_for_credit.return_value = D(1000)

        svc.record_payment(
            RecordPaymentRequest(customer_id="c1", credit_id="k1", amount=D(1000))
        )

        assert manager.entered == [True]  # une seule transaction
        for repo_call in (
            payments.add, customers.update, credits.update, journal.add
        ):
            assert repo_call.call_args.kwargs["conn"] == "TX-CONN"

    def test_failure_inside_the_transaction_propagates_for_rollback(
        self, manager, payments, credits, customers, journal
    ):
        svc = PaymentService(payments, credits, customers, journal, connection_manager=manager)
        customers.get_by_id.return_value = make_customer(5000, 0)
        credits.get_by_id.return_value = make_credit()
        payments.get_by_id.return_value = None
        payments.add.side_effect = lambda p, conn=None: p
        payments.total_paid_for_credit.return_value = D(1000)
        journal.add.side_effect = RuntimeError("disque plein")

        with pytest.raises(RuntimeError):
            svc.record_payment(
                RecordPaymentRequest(customer_id="c1", credit_id="k1", amount=D(1000))
            )

        # L'exception a traversé le gestionnaire : c'est lui qui annule (ROLLBACK).
        assert manager.exited_with == [RuntimeError]

    def test_credit_update_uses_one_transaction(
        self, manager, credits, customers, journal, payments
    ):
        svc = CreditService(
            credits, customers, journal, connection_manager=manager, payment_repository=payments
        )
        credits.get_by_id.return_value = make_credit()
        credits.update.side_effect = lambda c, conn=None: c
        payments.total_paid_for_credit.return_value = D(0)
        customers.get_by_id.return_value = make_customer(5000, 0)
        credits.total_amount_for_customer.return_value = D(8000)
        payments.total_paid_for_customer.return_value = D(0)

        svc.update_credit("k1", UpdateCreditRequest(amount=D(8000)))

        assert manager.entered == [True]
        assert credits.update.call_args.kwargs["conn"] == "TX-CONN"
        assert customers.update.call_args.kwargs["conn"] == "TX-CONN"

    def test_a_connection_given_by_the_caller_is_reused(
        self, manager, credits, customers, journal, payments
    ):
        svc = CreditService(
            credits, customers, journal, connection_manager=manager, payment_repository=payments
        )
        credits.get_by_id.return_value = make_credit()
        payments.get_by_credit.return_value = []
        customers.get_by_id.return_value = make_customer(0, 0)
        credits.total_amount_for_customer.return_value = D(0)
        payments.total_paid_for_customer.return_value = D(0)

        svc.delete_credit("k1", conn="DEJA-OUVERTE")

        assert manager.entered == []  # pas de seconde transaction imbriquée
        credits.delete.assert_called_once_with("k1", conn="DEJA-OUVERTE")


# ---------------------------------------------------------------------------
# PaymentService
# ---------------------------------------------------------------------------
class TestPaymentServiceMocked:
    @pytest.fixture
    def svc(self, payments, credits, customers, journal):
        return PaymentService(payments, credits, customers, journal)

    def _request(self, **kw):
        base = dict(customer_id="c1", credit_id="k1", amount=D(1000))
        base.update(kw)
        return RecordPaymentRequest(**base)

    def test_unknown_customer(self, svc, customers, payments):
        customers.get_by_id.return_value = None

        with pytest.raises(ValueError, match="Client introuvable"):
            svc.record_payment(self._request())

        payments.add.assert_not_called()

    def test_unknown_credit(self, svc, customers, credits, payments):
        customers.get_by_id.return_value = make_customer()
        credits.get_by_id.return_value = None

        with pytest.raises(ValueError, match="Crédit introuvable"):
            svc.record_payment(self._request())

        payments.add.assert_not_called()

    def test_credit_of_another_customer_is_refused(self, svc, customers, credits, payments):
        customers.get_by_id.return_value = make_customer()
        credits.get_by_id.return_value = make_credit(customer_id="AUTRE")

        with pytest.raises(ValueError, match="n'appartient pas"):
            svc.record_payment(self._request())

        payments.add.assert_not_called()

    def test_replay_of_same_payment_is_a_no_op(
        self, svc, customers, credits, payments, journal
    ):
        customers.get_by_id.return_value = make_customer()
        credits.get_by_id.return_value = make_credit()
        existing = make_payment(id="pay-1")
        payments.get_by_id.return_value = existing

        assert svc.record_payment(self._request(id="pay-1")) is existing

        payments.add.assert_not_called()
        customers.update.assert_not_called()
        journal.add.assert_not_called()

    def test_replay_with_different_credit_is_refused(
        self, svc, customers, credits, payments
    ):
        customers.get_by_id.return_value = make_customer()
        credits.get_by_id.return_value = make_credit()
        payments.get_by_id.return_value = make_payment(id="pay-1", credit_id="AUTRE")

        with pytest.raises(ValueError, match="Identifiant déjà utilisé"):
            svc.record_payment(self._request(id="pay-1"))

    def test_full_payment_marks_the_credit_paid(
        self, svc, customers, credits, payments
    ):
        credit = make_credit(5000)
        customers.get_by_id.return_value = make_customer(5000, 0)
        credits.get_by_id.return_value = credit
        payments.get_by_id.return_value = None
        payments.add.side_effect = lambda p, conn=None: p
        payments.total_paid_for_credit.return_value = D(5000)

        svc.record_payment(self._request(amount=D(5000)))

        assert credit.status == "paid"

    def test_update_payment_refreshes_credit_and_customer(
        self, svc, customers, credits, payments
    ):
        payment = make_payment(1000)
        payments.get_by_id.return_value = payment
        payments.update.side_effect = lambda p, conn=None: p
        credit = make_credit(5000, "partial")
        credits.get_by_id.return_value = credit
        payments.total_paid_for_credit.return_value = D(5000)
        customers.get_by_id.return_value = make_customer(5000, 1000)
        credits.total_amount_for_customer.return_value = D(5000)
        payments.total_paid_for_customer.return_value = D(5000)

        svc.update_payment("p1", UpdatePaymentRequest(amount=D(5000)))

        assert payment.amount == D(5000)
        assert credit.status == "paid"
        credits.update.assert_called_once()
        customers.update.assert_called_once()

    def test_delete_payment_deletes_first_then_recomputes(
        self, svc, customers, credits, payments
    ):
        payments.get_by_id.return_value = make_payment()
        credits.get_by_id.return_value = make_credit(5000, "paid")
        payments.total_paid_for_credit.return_value = D(0)
        customers.get_by_id.return_value = make_customer(5000, 5000)
        credits.total_amount_for_customer.return_value = D(5000)
        payments.total_paid_for_customer.return_value = D(0)
        order = Mock()
        order.attach_mock(payments.delete, "delete")
        order.attach_mock(payments.total_paid_for_credit, "recount")

        svc.delete_payment("p1")

        assert order.mock_calls[0] == call.delete("p1", conn=None)
        assert order.mock_calls[1][0] == "recount"  # recompté APRÈS la suppression

    def test_delete_unknown_payment(self, svc, payments):
        payments.get_by_id.return_value = None

        with pytest.raises(ValueError, match="Aucun paiement trouvé"):
            svc.delete_payment("zz")

        payments.delete.assert_not_called()
