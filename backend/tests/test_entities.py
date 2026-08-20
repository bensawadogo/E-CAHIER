"""Unit tests for the domain entities (Customer, Credit, Payment, Transaction)."""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.app.domain.entities.customer import Customer
from backend.app.domain.entities.credit import Credit
from backend.app.domain.entities.payment import Payment
from backend.app.domain.entities.transaction import Transaction


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------
class TestCustomer:
    def test_create_valid_customer(self):
        c = Customer(name="Awa Ouédraogo", phone="+226 70 12 34 56")
        assert c.name == "Awa Ouédraogo"
        assert c.phone == "+226 70 12 34 56"
        assert c.total_credit == Decimal("0.0")
        assert c.total_paid == Decimal("0.0")
        assert c.is_active is True
        assert c.sync_status == "pending"
        assert c.id  # auto-generated

    @pytest.mark.parametrize("bad_name", ["", "   ", None])
    def test_invalid_name(self, bad_name):
        with pytest.raises(ValueError):
            Customer(name=bad_name)

    @pytest.mark.parametrize("bad_status", ["", "syncing", "foo", "SYNCED"])
    def test_invalid_sync_status(self, bad_status):
        with pytest.raises(ValueError):
            Customer(name="Test", sync_status=bad_status)

    def test_negative_total_credit(self):
        with pytest.raises(ValueError):
            Customer(name="Test", total_credit=Decimal("-1"))

    def test_negative_total_paid(self):
        with pytest.raises(ValueError):
            Customer(name="Test", total_paid=Decimal("-0.01"))

    def test_balance(self):
        c = Customer(name="Test", total_credit=Decimal("100"), total_paid=Decimal("40"))
        assert c.balance == Decimal("60")

    def test_balance_with_no_debt(self):
        c = Customer(name="Test")
        assert c.balance == Decimal("0.0")

    def test_has_outstanding_balance_true(self):
        c = Customer(name="Test", total_credit=Decimal("100"), total_paid=Decimal("0"))
        assert c.has_outstanding_balance is True

    def test_has_outstanding_balance_false_small_amount(self):
        # Balance of 0.01 or less is considered settled.
        c = Customer(name="Test", total_credit=Decimal("0.01"), total_paid=Decimal("0"))
        assert c.has_outstanding_balance is False

    def test_has_outstanding_balance_false_settled(self):
        c = Customer(name="Test", total_credit=Decimal("100"), total_paid=Decimal("100"))
        assert c.has_outstanding_balance is False

    def test_mark_synced(self):
        c = Customer(name="Test")
        old_updated = c.updated_at
        c.mark_synced()
        assert c.sync_status == "synced"
        assert c.updated_at >= old_updated

    def test_repr_contains_balance(self):
        c = Customer(name="Test", total_credit=Decimal("50"))
        assert "balance=Decimal('50.0')" in repr(c)


# ---------------------------------------------------------------------------
# Credit
# ---------------------------------------------------------------------------
class TestCredit:
    def test_create_valid_credit(self):
        cr = Credit(customer_id="c1", amount=Decimal("5000"))
        assert cr.customer_id == "c1"
        assert cr.amount == Decimal("5000")
        assert cr.status == "pending"
        assert cr.sync_status == "pending"

    @pytest.mark.parametrize("bad_customer_id", ["", "   ", None])
    def test_missing_customer_id(self, bad_customer_id):
        with pytest.raises(ValueError):
            Credit(customer_id=bad_customer_id, amount=Decimal("100"))

    @pytest.mark.parametrize("bad_amount", [Decimal("0"), Decimal("-5"), Decimal("-0.01")])
    def test_non_positive_amount(self, bad_amount):
        with pytest.raises(ValueError):
            Credit(customer_id="c1", amount=bad_amount)

    @pytest.mark.parametrize("bad_status", ["", "overdue", "paid!", "Pending"])
    def test_invalid_status(self, bad_status):
        with pytest.raises(ValueError):
            Credit(customer_id="c1", amount=Decimal("100"), status=bad_status)

    def test_is_paid_property(self):
        cr = Credit(customer_id="c1", amount=Decimal("100"), status="paid")
        assert cr.is_paid is True
        assert cr.is_pending is False

    def test_is_pending_property(self):
        cr = Credit(customer_id="c1", amount=Decimal("100"))
        assert cr.is_pending is True
        assert cr.is_paid is False

    def test_is_overdue_false_when_paid(self):
        past = datetime.now(timezone.utc) - timedelta(days=10)
        cr = Credit(customer_id="c1", amount=Decimal("100"), due_date=past, status="paid")
        assert cr.is_overdue is False

    def test_is_overdue_false_when_cancelled(self):
        past = datetime.now(timezone.utc) - timedelta(days=10)
        cr = Credit(customer_id="c1", amount=Decimal("100"), due_date=past, status="cancelled")
        assert cr.is_overdue is False

    def test_is_overdue_true(self):
        past = datetime.now(timezone.utc) - timedelta(days=1)
        cr = Credit(customer_id="c1", amount=Decimal("100"), due_date=past)
        assert cr.is_overdue is True

    def test_is_overdue_false_future(self):
        future = datetime.now(timezone.utc) + timedelta(days=5)
        cr = Credit(customer_id="c1", amount=Decimal("100"), due_date=future)
        assert cr.is_overdue is False

    def test_mark_paid(self):
        cr = Credit(customer_id="c1", amount=Decimal("100"))
        cr.mark_paid()
        assert cr.status == "paid"

    def test_mark_partial(self):
        cr = Credit(customer_id="c1", amount=Decimal("100"))
        cr.mark_partial()
        assert cr.status == "partial"

    def test_mark_cancelled(self):
        cr = Credit(customer_id="c1", amount=Decimal("100"))
        cr.mark_cancelled()
        assert cr.status == "cancelled"

    def test_mark_synced(self):
        cr = Credit(customer_id="c1", amount=Decimal("100"))
        cr.mark_synced()
        assert cr.sync_status == "synced"


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------
class TestPayment:
    def test_create_valid_payment(self):
        p = Payment(
            customer_id="c1",
            credit_id="cr1",
            amount=Decimal("2000"),
            method="mobile_money",
        )
        assert p.customer_id == "c1"
        assert p.credit_id == "cr1"
        assert p.amount == Decimal("2000")
        assert p.method == "mobile_money"

    @pytest.mark.parametrize("bad_customer_id", ["", "  ", None])
    def test_missing_customer_id(self, bad_customer_id):
        with pytest.raises(ValueError):
            Payment(customer_id=bad_customer_id, credit_id="cr1", amount=Decimal("10"))

    @pytest.mark.parametrize("bad_credit_id", ["", "  ", None])
    def test_missing_credit_id(self, bad_credit_id):
        with pytest.raises(ValueError):
            Payment(customer_id="c1", credit_id=bad_credit_id, amount=Decimal("10"))

    @pytest.mark.parametrize("bad_amount", [Decimal("0"), Decimal("-1")])
    def test_non_positive_amount(self, bad_amount):
        with pytest.raises(ValueError):
            Payment(customer_id="c1", credit_id="cr1", amount=bad_amount)

    @pytest.mark.parametrize("bad_method", ["", "card", "cheque", "CASH"])
    def test_invalid_method(self, bad_method):
        with pytest.raises(ValueError):
            Payment(customer_id="c1", credit_id="cr1", amount=Decimal("10"), method=bad_method)

    def test_is_mobile_money(self):
        p = Payment(customer_id="c1", credit_id="cr1", amount=Decimal("10"), method="mobile_money")
        assert p.is_mobile_money is True
        assert p.is_cash is False

    def test_is_cash(self):
        p = Payment(customer_id="c1", credit_id="cr1", amount=Decimal("10"), method="cash")
        assert p.is_cash is True
        assert p.is_mobile_money is False

    def test_mark_synced(self):
        p = Payment(customer_id="c1", credit_id="cr1", amount=Decimal("10"))
        p.mark_synced()
        assert p.sync_status == "synced"


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------
class TestTransaction:
    def test_create_valid_credit_transaction(self):
        t = Transaction(customer_id="c1", type="credit", amount=Decimal("100"))
        assert t.type == "credit"
        assert t.amount == Decimal("100")
        assert t.balance_after == Decimal("0.0")
        assert t.sync_status == "pending"

    @pytest.mark.parametrize("bad_customer_id", ["", " ", None])
    def test_missing_customer_id(self, bad_customer_id):
        with pytest.raises(ValueError):
            Transaction(customer_id=bad_customer_id, type="credit", amount=Decimal("10"))

    @pytest.mark.parametrize("bad_type", ["", "debit", "refund", "CREDIT"])
    def test_invalid_type(self, bad_type):
        with pytest.raises(ValueError):
            Transaction(customer_id="c1", type=bad_type, amount=Decimal("10"))

    @pytest.mark.parametrize("bad_amount", [Decimal("0"), Decimal("-10")])
    def test_non_positive_amount(self, bad_amount):
        with pytest.raises(ValueError):
            Transaction(customer_id="c1", type="credit", amount=bad_amount)

    def test_is_credit(self):
        t = Transaction(customer_id="c1", type="credit", amount=Decimal("10"))
        assert t.is_credit is True
        assert t.is_payment is False

    def test_is_payment(self):
        t = Transaction(customer_id="c1", type="payment", amount=Decimal("10"))
        assert t.is_payment is True
        assert t.is_credit is False

    def test_mark_synced(self):
        t = Transaction(customer_id="c1", type="payment", amount=Decimal("10"))
        t.mark_synced()
        assert t.sync_status == "synced"

