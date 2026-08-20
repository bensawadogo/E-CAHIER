"""Unit tests for the SQLite repository implementations (credit, payment, transaction).

These tests exercise the concrete SQLite adapters directly against a fresh
in-memory database, so the OnDisk ``data/`` database is never touched.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.domain.entities.customer import Customer
from backend.app.domain.entities.credit import Credit
from backend.app.domain.entities.payment import Payment
from backend.app.domain.entities.transaction import Transaction
from backend.app.infrastructure.database.repositories.credit_repository_impl import (
    SQLiteCreditRepository,
)
from backend.app.infrastructure.database.repositories.payment_repository_impl import (
    SQLitePaymentRepository,
)
from backend.app.infrastructure.database.repositories.transaction_repository_impl import (
    SQLiteTransactionRepository,
)


def _make_customer(customer_repo, name="Awa OUEDRAOGO") -> Customer:
    return customer_repo.add(Customer(name=name))


class TestSQLiteCreditRepository:
    """CRUD and query filters for the SQLite credit repository."""

    def test_add_and_get_by_id(self, in_memory_db, customer_repo):
        customer = _make_customer(customer_repo)
        repo = SQLiteCreditRepository(in_memory_db)
        credit = Credit(customer_id=customer.id, amount=Decimal("5000"), description="Marchandises")

        saved = repo.add(credit)
        assert saved.id == credit.id

        fetched = repo.get_by_id(credit.id)
        assert fetched is not None
        assert fetched.amount == Decimal("5000")
        assert fetched.description == "Marchandises"
        assert fetched.status == "pending"
        assert fetched.customer_id == customer.id

    def test_get_by_customer_filters(self, in_memory_db, customer_repo):
        c1 = _make_customer(customer_repo, "Awa")
        c2 = _make_customer(customer_repo, "Alima")
        repo = SQLiteCreditRepository(in_memory_db)
        repo.add(Credit(customer_id=c1.id, amount=Decimal("1000")))
        repo.add(Credit(customer_id=c1.id, amount=Decimal("2000")))
        repo.add(Credit(customer_id=c2.id, amount=Decimal("3000")))

        result = repo.get_by_customer(c1.id)
        assert len(result) == 2
        assert all(c.customer_id == c1.id for c in result)

    def test_pending_excludes_paid_and_cancelled(self, in_memory_db, customer_repo):
        customer = _make_customer(customer_repo)
        repo = SQLiteCreditRepository(in_memory_db)
        repo.add(Credit(customer_id=customer.id, amount=Decimal("1000")))
        paid = repo.add(Credit(customer_id=customer.id, amount=Decimal("2000")))
        paid.mark_paid()
        repo.update(paid)

        pending, total = repo.get_pending(), repo.count_pending()
        assert total == 1
        assert len(pending) == 1
        assert pending[0].id != paid.id

    def test_overdue_only_returns_past_due_unpaid(self, in_memory_db, customer_repo):
        customer = _make_customer(customer_repo)
        repo = SQLiteCreditRepository(in_memory_db)
        now = datetime.now(timezone.utc)
        overdue = repo.add(
            Credit(
                customer_id=customer.id,
                amount=Decimal("1000"),
                due_date=now - timedelta(days=5),
            )
        )
        repo.add(
            Credit(
                customer_id=customer.id,
                amount=Decimal("1000"),
                due_date=now + timedelta(days=5),
            )
        )

        result, total = repo.get_overdue(), repo.count_overdue()
        assert total == 1
        assert len(result) == 1
        assert result[0].id == overdue.id

    def test_count_all(self, in_memory_db, customer_repo):
        customer = _make_customer(customer_repo)
        repo = SQLiteCreditRepository(in_memory_db)
        repo.add(Credit(customer_id=customer.id, amount=Decimal("1000")))
        repo.add(Credit(customer_id=customer.id, amount=Decimal("2000")))
        assert repo.count_all() == 2

    def test_pagination_limit_offset(self, in_memory_db, customer_repo):
        customer = _make_customer(customer_repo)
        repo = SQLiteCreditRepository(in_memory_db)
        for i in range(5):
            repo.add(Credit(customer_id=customer.id, amount=Decimal(str((i + 1) * 100))))

        page = repo.get_all(offset=0, limit=2)
        assert len(page) == 2
        second_page = repo.get_all(offset=2, limit=2)
        assert len(second_page) == 2

    def test_update_and_delete(self, in_memory_db, customer_repo):
        customer = _make_customer(customer_repo)
        repo = SQLiteCreditRepository(in_memory_db)
        credit = repo.add(Credit(customer_id=customer.id, amount=Decimal("1000")))
        credit.mark_paid()
        repo.update(credit)
        assert repo.get_by_id(credit.id).status == "paid"

        repo.delete(credit.id)
        assert repo.get_by_id(credit.id) is None

    def test_update_missing_raises(self, in_memory_db, customer_repo):
        _make_customer(customer_repo)  # Crée la table customers (contrainte FK).
        repo = SQLiteCreditRepository(in_memory_db)
        credit = Credit(customer_id="nobody", amount=Decimal("1000"))
        credit.id = "not-stored"
        with pytest.raises(ValueError):
            repo.update(credit)

    def test_delete_missing_raises(self, in_memory_db, customer_repo):
        _make_customer(customer_repo)  # Crée la table customers (contrainte FK).
        repo = SQLiteCreditRepository(in_memory_db)
        with pytest.raises(ValueError):
            repo.delete("missing-id")


class TestSQLitePaymentRepository:
    """CRUD and aggregation logic for the SQLite payment repository."""

    def _seed(self, in_memory_db, customer_repo):
        customer = _make_customer(customer_repo)
        credit_repo = SQLiteCreditRepository(in_memory_db)
        credit = credit_repo.add(
            Credit(customer_id=customer.id, amount=Decimal("5000"))
        )
        payment_repo = SQLitePaymentRepository(in_memory_db)
        return customer, credit, payment_repo

    def test_add_and_get_by_id(self, in_memory_db, customer_repo):
        customer, credit, repo = self._seed(in_memory_db, customer_repo)
        payment = repo.add(
            Payment(
                customer_id=customer.id,
                credit_id=credit.id,
                amount=Decimal("1000"),
                method="cash",
            )
        )
        fetched = repo.get_by_id(payment.id)
        assert fetched is not None
        assert fetched.amount == Decimal("1000")
        assert fetched.method == "cash"

    def test_total_paid_for_credit_sums(self, in_memory_db, customer_repo):
        customer, credit, repo = self._seed(in_memory_db, customer_repo)
        repo.add(
            Payment(
                customer_id=customer.id,
                credit_id=credit.id,
                amount=Decimal("1000"),
                method="cash",
            )
        )
        repo.add(
            Payment(
                customer_id=customer.id,
                credit_id=credit.id,
                amount=Decimal("2000"),
                method="mobile_money",
            )
        )
        assert repo.total_paid_for_credit(credit.id) == Decimal("3000")

    def test_total_paid_for_credit_ignores_other_credits(self, in_memory_db, customer_repo):
        customer, credit, repo = self._seed(in_memory_db, customer_repo)
        repo.add(
            Payment(
                customer_id=customer.id,
                credit_id=credit.id,
                amount=Decimal("1000"),
                method="cash",
            )
        )
        assert repo.total_paid_for_credit("some-other-credit") == Decimal("0")

    def test_get_by_credit(self, in_memory_db, customer_repo):
        customer, credit, repo = self._seed(in_memory_db, customer_repo)
        repo.add(
            Payment(
                customer_id=customer.id,
                credit_id=credit.id,
                amount=Decimal("1000"),
                method="cash",
            )
        )
        assert len(repo.get_by_credit(credit.id)) == 1

    def test_get_by_customer(self, in_memory_db, customer_repo):
        customer, credit, repo = self._seed(in_memory_db, customer_repo)
        repo.add(
            Payment(
                customer_id=customer.id,
                credit_id=credit.id,
                amount=Decimal("1000"),
                method="cash",
            )
        )
        assert len(repo.get_by_customer(customer.id)) == 1

    def test_update_and_delete(self, in_memory_db, customer_repo):
        customer, credit, repo = self._seed(in_memory_db, customer_repo)
        payment = repo.add(
            Payment(
                customer_id=customer.id,
                credit_id=credit.id,
                amount=Decimal("1000"),
                method="cash",
            )
        )
        payment.method = "mobile_money"
        repo.update(payment)
        assert repo.get_by_id(payment.id).method == "mobile_money"

        repo.delete(payment.id)
        assert repo.get_by_id(payment.id) is None

    def test_delete_missing_raises(self, in_memory_db, customer_repo):
        _, _, repo = self._seed(in_memory_db, customer_repo)
        with pytest.raises(ValueError):
            repo.delete("missing-id")


class TestSQLiteTransactionRepository:
    """CRUD and pending-sync filtering for the SQLite transaction repository."""

    def test_add_and_get_by_id(self, in_memory_db, customer_repo):
        customer = _make_customer(customer_repo)
        repo = SQLiteTransactionRepository(in_memory_db)
        tx = repo.add(
            Transaction(
                customer_id=customer.id,
                type="credit",
                amount=Decimal("1000"),
                balance_after=Decimal("1000"),
            )
        )
        fetched = repo.get_by_id(tx.id)
        assert fetched is not None
        assert fetched.is_credit
        assert fetched.amount == Decimal("1000")

    def test_get_by_customer_and_count(self, in_memory_db, customer_repo):
        c1 = _make_customer(customer_repo, "Awa")
        c2 = _make_customer(customer_repo, "Alima")
        repo = SQLiteTransactionRepository(in_memory_db)
        repo.add(
            Transaction(customer_id=c1.id, type="credit", amount=Decimal("1000"))
        )
        repo.add(
            Transaction(customer_id=c1.id, type="payment", amount=Decimal("500"))
        )
        repo.add(
            Transaction(customer_id=c2.id, type="credit", amount=Decimal("2000"))
        )

        assert len(repo.get_by_customer(c1.id)) == 2
        assert repo.count_all() == 3

    def test_get_pending_sync(self, in_memory_db, customer_repo):
        customer = _make_customer(customer_repo)
        repo = SQLiteTransactionRepository(in_memory_db)
        pending = repo.add(
            Transaction(customer_id=customer.id, type="credit", amount=Decimal("1000"))
        )
        repo.add(
            Transaction(
                customer_id=customer.id,
                type="payment",
                amount=Decimal("500"),
                sync_status="synced",
            )
        )

        result = repo.get_pending_sync()
        assert [t.id for t in result] == [pending.id]

    def test_delete(self, in_memory_db, customer_repo):
        customer = _make_customer(customer_repo)
        repo = SQLiteTransactionRepository(in_memory_db)
        tx = repo.add(
            Transaction(customer_id=customer.id, type="credit", amount=Decimal("1000"))
        )
        repo.delete(tx.id)
        assert repo.get_by_id(tx.id) is None

    def test_delete_missing_raises(self, in_memory_db, customer_repo):
        _make_customer(customer_repo)
        repo = SQLiteTransactionRepository(in_memory_db)
        with pytest.raises(ValueError):
            repo.delete("missing-id")