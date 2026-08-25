"""Tests de validation des entités du domaine (gardes __post_init__)."""

from decimal import Decimal
from uuid import uuid4

import pytest

from backend.app.domain.entities.credit import Credit
from backend.app.domain.entities.payment import Payment
from backend.app.domain.entities.transaction import Transaction


def _valid_credit_kwargs():
    return {"customer_id": "c1", "amount": Decimal("100")}


def _valid_payment_kwargs():
    return {
        "customer_id": "c1",
        "credit_id": "cr1",
        "amount": Decimal("50"),
        "method": "cash",
    }


def _valid_transaction_kwargs():
    return {
        "customer_id": "c1",
        "type": "payment",
        "amount": Decimal("50"),
        "balance_after": Decimal("0"),
    }


class TestCreditValidation:
    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            Credit(status="bogus", **_valid_credit_kwargs())

    def test_invalid_sync_status_rejected(self):
        with pytest.raises(ValueError, match="sync_status"):
            Credit(sync_status="bogus", **_valid_credit_kwargs())


class TestPaymentValidation:
    def test_invalid_sync_status_rejected(self):
        with pytest.raises(ValueError, match="sync_status"):
            Payment(sync_status="bogus", **_valid_payment_kwargs())

    def test_invalid_method_rejected(self):
        kwargs = _valid_payment_kwargs()
        kwargs["method"] = "crypto"
        with pytest.raises(ValueError, match="method"):
            Payment(**kwargs)


class TestTransactionValidation:
    def test_invalid_type_rejected(self):
        kwargs = _valid_transaction_kwargs()
        kwargs["type"] = "remboursement"
        with pytest.raises(ValueError, match="type"):
            Transaction(**kwargs)

    def test_invalid_sync_status_rejected(self):
        kwargs = _valid_transaction_kwargs()
        kwargs["sync_status"] = "bogus"
        with pytest.raises(ValueError, match="sync_status"):
            Transaction(**kwargs)

    def test_negative_amount_rejected(self):
        kwargs = _valid_transaction_kwargs()
        kwargs["amount"] = Decimal("-1")
        with pytest.raises(ValueError, match="positif"):
            Transaction(**kwargs)

    def test_repr_contains_key_fields(self):
        t = Transaction(id=str(uuid4()), **_valid_transaction_kwargs())
        r = repr(t)
        assert "Transaction" in r and t.type in r
