"""Unit tests for the Pydantic DTOs (application/application/dto)."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from backend.app.application.dto.customer_dto import (
    CreateCustomerRequest,
    UpdateCustomerRequest,
)
from backend.app.application.dto.credit_dto import (
    CreateCreditRequest,
    UpdateCreditRequest,
)
from backend.app.application.dto.payment_dto import (
    RecordPaymentRequest,
    UpdatePaymentRequest,
)


# ---------------------------------------------------------------------------
# CreateCustomerRequest
# ---------------------------------------------------------------------------
class TestCreateCustomerRequest:
    def test_valid(self):
        req = CreateCustomerRequest(name="Awa Ouédraogo", phone="+226 70 00 00 00")
        assert req.name == "Awa Ouédraogo"
        assert req.phone == "+226 70 00 00 00"
        assert req.address == ""
        assert req.notes == ""

    @pytest.mark.parametrize("bad_name", ["", "   ", "  "])
    def test_empty_name_rejected(self, bad_name):
        with pytest.raises(ValueError):
            CreateCustomerRequest(name=bad_name)

    def test_whitespace_name_is_stripped(self):
        req = CreateCustomerRequest(name="  Alima  ")
        assert req.name == "Alima"

    def test_missing_name_rejected(self):
        with pytest.raises(ValueError):
            CreateCustomerRequest()

    def test_phone_length_limit(self):
        with pytest.raises(ValueError):
            CreateCustomerRequest(name="Test", phone="x" * 21)


# ---------------------------------------------------------------------------
# UpdateCustomerRequest
# ---------------------------------------------------------------------------
class TestUpdateCustomerRequest:
    def test_empty_update_is_valid(self):
        req = UpdateCustomerRequest()
        assert req.name is None
        assert req.is_active is None

    def test_partial_update(self):
        req = UpdateCustomerRequest(name="Nouveau Nom", is_active=False)
        assert req.name == "Nouveau Nom"
        assert req.is_active is False

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError):
            UpdateCustomerRequest(name="")

    def test_whitespace_name_passes(self):
        # Current behaviour: whitespace-only passes min_length (no custom
        # validator on UpdateCustomerRequest).
        req = UpdateCustomerRequest(name="   ")
        assert req.name == "   "


# ---------------------------------------------------------------------------
# CreateCreditRequest
# ---------------------------------------------------------------------------
class TestCreateCreditRequest:
    def test_valid(self):
        req = CreateCreditRequest(customer_id="c1", amount=Decimal("5000"))
        assert req.customer_id == "c1"
        assert req.amount == Decimal("5000")
        assert req.due_date is None

    def test_missing_customer_id(self):
        with pytest.raises(ValueError):
            CreateCreditRequest(amount=Decimal("5000"))

    @pytest.mark.parametrize("bad_amount", [Decimal("0"), Decimal("-10")])
    def test_non_positive_amount(self, bad_amount):
        with pytest.raises(ValueError):
            CreateCreditRequest(customer_id="c1", amount=bad_amount)

    def test_with_due_date(self):
        due = datetime(2025, 12, 31, tzinfo=timezone.utc)
        req = CreateCreditRequest(customer_id="c1", amount=Decimal("100"), due_date=due)
        assert req.due_date == due


# ---------------------------------------------------------------------------
# UpdateCreditRequest
# ---------------------------------------------------------------------------
class TestUpdateCreditRequest:
    def test_empty_update(self):
        req = UpdateCreditRequest()
        assert req.amount is None
        assert req.status is None

    def test_valid_status(self):
        req = UpdateCreditRequest(status="paid")
        assert req.status == "paid"

    @pytest.mark.parametrize("bad_status", ["", "overdue", "PAID", "foo"])
    def test_invalid_status(self, bad_status):
        with pytest.raises(ValueError):
            UpdateCreditRequest(status=bad_status)

    def test_non_positive_amount(self):
        with pytest.raises(ValueError):
            UpdateCreditRequest(amount=Decimal("0"))


# ---------------------------------------------------------------------------
# RecordPaymentRequest
# ---------------------------------------------------------------------------
class TestRecordPaymentRequest:
    def test_valid_cash(self):
        req = RecordPaymentRequest(
            customer_id="c1", credit_id="cr1", amount=Decimal("2000"), method="cash"
        )
        assert req.customer_id == "c1"
        assert req.credit_id == "cr1"
        assert req.amount == Decimal("2000")
        assert req.method == "cash"
        assert req.reference == ""
        assert req.note == ""

    def test_valid_mobile_money_with_reference(self):
        req = RecordPaymentRequest(
            customer_id="c1",
            credit_id="cr1",
            amount=Decimal("1000"),
            method="mobile_money",
            reference="REF-123",
        )
        assert req.method == "mobile_money"
        assert req.reference == "REF-123"

    @pytest.mark.parametrize("bad_method", ["", "cash!", "MobileMoney", "bank"])
    def test_invalid_method(self, bad_method):
        with pytest.raises(ValueError):
            RecordPaymentRequest(
                customer_id="c1", credit_id="cr1", amount=Decimal("10"), method=bad_method
            )

    def test_missing_ids(self):
        with pytest.raises(ValueError):
            RecordPaymentRequest(customer_id="", credit_id="cr1", amount=Decimal("10"))


# ---------------------------------------------------------------------------
# UpdatePaymentRequest
# ---------------------------------------------------------------------------
class TestUpdatePaymentRequest:
    def test_empty_update(self):
        req = UpdatePaymentRequest()
        assert req.method is None

    @pytest.mark.parametrize("bad_method", ["card", "CHQ", ""])
    def test_invalid_method(self, bad_method):
        with pytest.raises(ValueError):
            UpdatePaymentRequest(method=bad_method)

    def test_non_positive_amount(self):
        with pytest.raises(ValueError):
            UpdatePaymentRequest(amount=Decimal("-1"))

