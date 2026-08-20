"""Unit tests for the application services using in-memory fake repositories.

These tests exercise the service orchestration logic without touching a real
database: fake repositories implement the port interfaces in-memory.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

import pytest

from backend.app.application.dto.customer_dto import (
    CreateCustomerRequest,
    UpdateCustomerRequest,
)
from backend.app.application.dto.credit_dto import CreateCreditRequest, UpdateCreditRequest
from backend.app.application.dto.payment_dto import RecordPaymentRequest, UpdatePaymentRequest
from backend.app.domain.entities.customer import Customer
from backend.app.domain.entities.credit import Credit
from backend.app.domain.entities.payment import Payment
from backend.app.domain.entities.transaction import Transaction


# ---------------------------------------------------------------------------
# In-memory fake repositories
# ---------------------------------------------------------------------------
class FakeCustomerRepository:
    def __init__(self):
        self._store = {}

    def add(self, customer: Customer) -> Customer:
        self._store[customer.id] = customer
        return customer

    def get_by_id(self, customer_id: str) -> Optional[Customer]:
        return self._store.get(customer_id)

    def get_all(self, offset: int = 0, limit: Optional[int] = None) -> List[Customer]:
        items = list(self._store.values())
        if limit is None:
            return items[offset:]
        return items[offset:offset + limit]

    def get_active(self, offset: int = 0, limit: Optional[int] = None) -> List[Customer]:
        items = [c for c in self._store.values() if c.is_active]
        if limit is None:
            return items[offset:]
        return items[offset:offset + limit]

    def count_all(self) -> int:
        return len(self._store)

    def count_active(self) -> int:
        return sum(1 for c in self._store.values() if c.is_active)

    def update(self, customer: Customer) -> Customer:
        if customer.id not in self._store:
            raise ValueError(f"Aucun client trouvé avec l'ID {customer.id}.")
        self._store[customer.id] = customer
        return customer

    def delete(self, customer_id: str) -> None:
        if customer_id not in self._store:
            raise ValueError(f"Aucun client trouvé avec l'ID {customer_id}.")
        del self._store[customer_id]

    def search_by_name(
        self, query: str, offset: int = 0, limit: Optional[int] = None
    ) -> List[Customer]:
        q = query.lower()
        items = [c for c in self._store.values() if q in c.name.lower()]
        if limit is None:
            return items[offset:]
        return items[offset:offset + limit]


class FakeCreditRepository:
    def __init__(self):
        self._store = {}

    def add(self, credit: Credit) -> Credit:
        self._store[credit.id] = credit
        return credit

    def get_by_id(self, credit_id: str) -> Optional[Credit]:
        return self._store.get(credit_id)

    def get_by_customer(
        self, customer_id: str, offset: int = 0, limit: Optional[int] = None
    ) -> List[Credit]:
        items = [c for c in self._store.values() if c.customer_id == customer_id]
        if limit is None:
            return items[offset:]
        return items[offset:offset + limit]

    def get_all(self, offset: int = 0, limit: Optional[int] = None) -> List[Credit]:
        items = list(self._store.values())
        if limit is None:
            return items[offset:]
        return items[offset:offset + limit]

    def get_pending(
        self, offset: int = 0, limit: Optional[int] = None
    ) -> List[Credit]:
        items = [c for c in self._store.values() if c.status in ("pending", "partial")]
        if limit is None:
            return items[offset:]
        return items[offset:offset + limit]

    def get_overdue(
        self, offset: int = 0, limit: Optional[int] = None
    ) -> List[Credit]:
        now = datetime.now(timezone.utc)
        items = [
            c for c in self._store.values()
            if c.status in ("pending", "partial") and c.due_date < now
        ]
        if limit is None:
            return items[offset:]
        return items[offset:offset + limit]

    def count_all(self) -> int:
        return len(self._store)

    def count_pending(self) -> int:
        return sum(1 for c in self._store.values() if c.status in ("pending", "partial"))

    def count_overdue(self) -> int:
        now = datetime.now(timezone.utc)
        return sum(
            1 for c in self._store.values()
            if c.status in ("pending", "partial") and c.due_date < now
        )

    def update(self, credit: Credit) -> Credit:
        if credit.id not in self._store:
            raise ValueError(f"Aucun crédit trouvé avec l'ID {credit.id}.")
        self._store[credit.id] = credit
        return credit

    def delete(self, credit_id: str) -> None:
        if credit_id not in self._store:
            raise ValueError(f"Aucun crédit trouvé avec l'ID {credit_id}.")
        del self._store[credit_id]


class FakePaymentRepository:
    def __init__(self):
        self._store = {}

    def add(self, payment: Payment) -> Payment:
        self._store[payment.id] = payment
        return payment

    def get_by_id(self, payment_id: str) -> Optional[Payment]:
        return self._store.get(payment_id)

    def get_by_customer(
        self, customer_id: str, offset: int = 0, limit: Optional[int] = None
    ) -> List[Payment]:
        items = [p for p in self._store.values() if p.customer_id == customer_id]
        if limit is None:
            return items[offset:]
        return items[offset:offset + limit]

    def get_by_credit(
        self, credit_id: str, offset: int = 0, limit: Optional[int] = None
    ) -> List[Payment]:
        items = [p for p in self._store.values() if p.credit_id == credit_id]
        if limit is None:
            return items[offset:]
        return items[offset:offset + limit]

    def get_all(self, offset: int = 0, limit: Optional[int] = None) -> List[Payment]:
        items = list(self._store.values())
        if limit is None:
            return items[offset:]
        return items[offset:offset + limit]

    def count_all(self) -> int:
        return len(self._store)

    def total_paid_for_credit(self, credit_id: str) -> Decimal:
        return sum(
            (p.amount for p in self._store.values() if p.credit_id == credit_id),
            Decimal("0"),
        )

    def update(self, payment: Payment) -> Payment:
        if payment.id not in self._store:
            raise ValueError(f"Aucun paiement trouvé avec l'ID {payment.id}.")
        self._store[payment.id] = payment
        return payment

    def delete(self, payment_id: str) -> None:
        if payment_id not in self._store:
            raise ValueError(f"Aucun paiement trouvé avec l'ID {payment_id}.")
        del self._store[payment_id]


class FakeTransactionRepository:
    def __init__(self):
        self._store = {}

    def add(self, transaction: Transaction) -> Transaction:
        self._store[transaction.id] = transaction
        return transaction

    def get_by_id(self, transaction_id: str) -> Optional[Transaction]:
        return self._store.get(transaction_id)

    def get_by_customer(
        self, customer_id: str, offset: int = 0, limit: Optional[int] = None
    ) -> List[Transaction]:
        items = [t for t in self._store.values() if t.customer_id == customer_id]
        if limit is None:
            return items[offset:]
        return items[offset:offset + limit]

    def get_all(self, offset: int = 0, limit: Optional[int] = None) -> List[Transaction]:
        items = list(self._store.values())
        if limit is None:
            return items[offset:]
        return items[offset:offset + limit]

    def count_all(self) -> int:
        return len(self._store)

    def get_pending_sync(
        self, offset: int = 0, limit: Optional[int] = None
    ) -> List[Transaction]:
        items = [t for t in self._store.values() if t.sync_status == "pending"]
        if limit is None:
            return items[offset:]
        return items[offset:offset + limit]

    def delete(self, transaction_id: str) -> None:
        if transaction_id not in self._store:
            raise ValueError(f"Aucune transaction trouvée avec l'ID {transaction_id}.")
        del self._store[transaction_id]


# ---------------------------------------------------------------------------
# CustomerService
# ---------------------------------------------------------------------------
class TestCustomerService:
    def _make(self):
        from backend.app.application.services.customer_service import CustomerService

        return CustomerService(FakeCustomerRepository())

    def test_create_customer(self):
        svc = self._make()
        req = CreateCustomerRequest(name="Awa Ouédraogo", phone="+226 70 00 00 00")
        customer = svc.create_customer(req)
        assert customer.id
        assert customer.name == "Awa Ouédraogo"
        assert customer.phone == "+226 70 00 00 00"
        assert svc.get_customer(customer.id) is customer

    def test_get_customer_not_found(self):
        svc = self._make()
        assert svc.get_customer("missing") is None

    def test_get_all_customers(self):
        svc = self._make()
        svc.create_customer(CreateCustomerRequest(name="A"))
        svc.create_customer(CreateCustomerRequest(name="B"))
        assert len(svc.get_all_customers()) == 2

    def test_get_active_customers(self):
        svc = self._make()
        c1 = svc.create_customer(CreateCustomerRequest(name="A"))
        svc.create_customer(CreateCustomerRequest(name="B"))
        svc.update_customer(c1.id, UpdateCustomerRequest(is_active=False))
        actives, total = svc.get_active_customers()
        assert len(actives) == 1
        assert total == 1
        assert actives[0].name == "B"

    def test_update_customer(self):
        svc = self._make()
        c = svc.create_customer(CreateCustomerRequest(name="A"))
        updated = svc.update_customer(c.id, UpdateCustomerRequest(name="B"))
        assert updated.name == "B"
        assert svc.get_customer(c.id).name == "B"

    def test_update_customer_not_found(self):
        svc = self._make()
        with pytest.raises(ValueError):
            svc.update_customer("missing", UpdateCustomerRequest(name="B"))

    def test_delete_customer(self):
        svc = self._make()
        c = svc.create_customer(CreateCustomerRequest(name="A"))
        svc.delete_customer(c.id)
        assert svc.get_customer(c.id) is None

    def test_delete_customer_not_found(self):
        svc = self._make()
        with pytest.raises(ValueError):
            svc.delete_customer("missing")

    def test_search_customers(self):
        svc = self._make()
        svc.create_customer(CreateCustomerRequest(name="Awa Ouédraogo"))
        svc.create_customer(CreateCustomerRequest(name="Alima Sawadogo"))
        results = svc.search_customers("alima")
        assert len(results) == 1
        assert results[0].name == "Alima Sawadogo"


# ---------------------------------------------------------------------------
# CreditService
# ---------------------------------------------------------------------------
class TestCreditService:
    def _make(self):
        from backend.app.application.services.credit_service import CreditService

        customer_repo = FakeCustomerRepository()
        credit_repo = FakeCreditRepository()
        return CreditService(credit_repo, customer_repo), customer_repo, credit_repo

    def _add_customer(self, customer_repo, name="Client"):
        c = Customer(name=name)
        return customer_repo.add(c)

    def test_create_credit_updates_customer_total(self):
        svc, customer_repo, credit_repo = self._make()
        customer = self._add_customer(customer_repo)
        req = CreateCreditRequest(customer_id=customer.id, amount=Decimal("5000"))
        credit = svc.create_credit(req)
        assert credit.id
        assert credit.amount == Decimal("5000")
        assert credit.status == "pending"
        assert credit.due_date is not None
        # customer total_credit updated
        assert customer.total_credit == Decimal("5000")

    def test_create_credit_invalid_customer(self):
        svc, _, _ = self._make()
        req = CreateCreditRequest(customer_id="missing", amount=Decimal("5000"))
        with pytest.raises(ValueError):
            svc.create_credit(req)

    def test_default_due_date_is_about_30_days(self):
        svc, customer_repo, _ = self._make()
        customer = self._add_customer(customer_repo)
        before = datetime.now(timezone.utc)
        credit = svc.create_credit(
            CreateCreditRequest(customer_id=customer.id, amount=Decimal("100"))
        )
        after = datetime.now(timezone.utc)
        expected_min = before + timedelta(days=30)
        expected_max = after + timedelta(days=30)
        assert expected_min <= credit.due_date <= expected_max

    def test_get_credit(self):
        svc, customer_repo, _ = self._make()
        customer = self._add_customer(customer_repo)
        credit = svc.create_credit(
            CreateCreditRequest(customer_id=customer.id, amount=Decimal("100"))
        )
        assert svc.get_credit(credit.id) is credit

    def test_get_customer_credits(self):
        svc, customer_repo, _ = self._make()
        customer = self._add_customer(customer_repo)
        svc.create_credit(CreateCreditRequest(customer_id=customer.id, amount=Decimal("100")))
        svc.create_credit(CreateCreditRequest(customer_id=customer.id, amount=Decimal("200")))
        assert len(svc.get_customer_credits(customer.id)) == 2

    def test_get_all_credits(self):
        svc, customer_repo, _ = self._make()
        customer = self._add_customer(customer_repo)
        svc.create_credit(CreateCreditRequest(customer_id=customer.id, amount=Decimal("100")))
        credits, total = svc.get_all_credits()
        assert len(credits) == 1
        assert total == 1

    def test_get_pending_credits(self):
        svc, customer_repo, credit_repo = self._make()
        customer = self._add_customer(customer_repo)
        credit = svc.create_credit(
            CreateCreditRequest(customer_id=customer.id, amount=Decimal("100"))
        )
        credit.mark_paid()
        credit_repo.update(credit)
        pending, total = svc.get_pending_credits()
        assert pending == []
        assert total == 0

    def test_get_overdue_credits(self):
        svc, customer_repo, _ = self._make()
        customer = self._add_customer(customer_repo)
        past = datetime.now(timezone.utc) - timedelta(days=5)
        overdue = Credit(
            customer_id=customer.id, amount=Decimal("100"), due_date=past
        )
        svc.credit_repository.add(overdue)
        overdue, total = svc.get_overdue_credits()
        assert len(overdue) == 1
        assert total == 1

    def test_update_credit(self):
        svc, customer_repo, _ = self._make()
        customer = self._add_customer(customer_repo)
        credit = svc.create_credit(
            CreateCreditRequest(customer_id=customer.id, amount=Decimal("100"))
        )
        updated = svc.update_credit(credit.id, UpdateCreditRequest(status="cancelled"))
        assert updated.status == "cancelled"

    def test_update_credit_not_found(self):
        svc, _, _ = self._make()
        with pytest.raises(ValueError):
            svc.update_credit("missing", UpdateCreditRequest(status="paid"))

    def test_delete_credit(self):
        svc, customer_repo, _ = self._make()
        customer = self._add_customer(customer_repo)
        credit = svc.create_credit(
            CreateCreditRequest(customer_id=customer.id, amount=Decimal("100"))
        )
        svc.delete_credit(credit.id)
        assert svc.get_credit(credit.id) is None


# ---------------------------------------------------------------------------
# PaymentService
# ---------------------------------------------------------------------------
class TestPaymentService:
    def _make(self):
        from backend.app.application.services.payment_service import PaymentService

        payment_repo = FakePaymentRepository()
        credit_repo = FakeCreditRepository()
        customer_repo = FakeCustomerRepository()
        transaction_repo = FakeTransactionRepository()
        svc = PaymentService(payment_repo, credit_repo, customer_repo, transaction_repo)
        return svc, payment_repo, credit_repo, customer_repo, transaction_repo

    def _add_customer(self, customer_repo, name="Client"):
        c = Customer(name=name)
        return customer_repo.add(c)

    def _add_credit(self, credit_repo, customer_id, amount="5000"):
        cr = Credit(customer_id=customer_id, amount=Decimal(amount))
        return credit_repo.add(cr)

    def test_record_payment_updates_customer_and_credit(self):
        svc, payment_repo, credit_repo, customer_repo, transaction_repo = self._make()
        customer = self._add_customer(customer_repo)
        credit = self._add_credit(credit_repo, customer.id, "5000")
        # In the real flow, CreditService.create_credit increments the customer's
        # total_credit; mirror that here so balance calculations are realistic.
        customer.total_credit = Decimal("5000")

        req = RecordPaymentRequest(
            customer_id=customer.id,
            credit_id=credit.id,
            amount=Decimal("2000"),
            method="cash",
        )
        payment = svc.record_payment(req)
        assert payment.id
        assert payment.amount == Decimal("2000")

        # Customer total_paid updated
        assert customer.total_paid == Decimal("2000")
        # Credit marked partial
        assert credit.status == "partial"
        # Transaction journal entry created
        assert len(transaction_repo.get_all()) == 1
        tx = transaction_repo.get_all()[0]
        assert tx.type == "payment"
        assert tx.amount == Decimal("2000")
        assert tx.balance_after == Decimal("3000")

    def test_record_payment_full_amount_marks_credit_paid(self):
        svc, _, credit_repo, customer_repo, _ = self._make()
        customer = self._add_customer(customer_repo)
        credit = self._add_credit(credit_repo, customer.id, "5000")

        svc.record_payment(
            RecordPaymentRequest(
                customer_id=customer.id,
                credit_id=credit.id,
                amount=Decimal("5000"),
                method="cash",
            )
        )
        assert credit.status == "paid"
        assert customer.total_paid == Decimal("5000")

    def test_record_payment_customer_not_found(self):
        svc, _, credit_repo, _, _ = self._make()
        credit = self._add_credit(credit_repo, "cust-1", "5000")
        req = RecordPaymentRequest(
            customer_id="missing", credit_id=credit.id, amount=Decimal("100"), method="cash"
        )
        with pytest.raises(ValueError):
            svc.record_payment(req)

    def test_record_payment_credit_not_found(self):
        svc, _, _, customer_repo, _ = self._make()
        customer = self._add_customer(customer_repo)
        req = RecordPaymentRequest(
            customer_id=customer.id, credit_id="missing", amount=Decimal("100"), method="cash"
        )
        with pytest.raises(ValueError):
            svc.record_payment(req)

    def test_get_payment(self):
        svc, _, credit_repo, customer_repo, _ = self._make()
        customer = self._add_customer(customer_repo)
        credit = self._add_credit(credit_repo, customer.id, "5000")
        payment = svc.record_payment(
            RecordPaymentRequest(
                customer_id=customer.id,
                credit_id=credit.id,
                amount=Decimal("100"),
                method="cash",
            )
        )
        assert svc.get_payment(payment.id) is payment

    def test_get_customer_payments(self):
        svc, _, credit_repo, customer_repo, _ = self._make()
        customer = self._add_customer(customer_repo)
        credit = self._add_credit(credit_repo, customer.id, "5000")
        svc.record_payment(
            RecordPaymentRequest(
                customer_id=customer.id,
                credit_id=credit.id,
                amount=Decimal("100"),
                method="cash",
            )
        )
        svc.record_payment(
            RecordPaymentRequest(
                customer_id=customer.id,
                credit_id=credit.id,
                amount=Decimal("100"),
                method="cash",
            )
        )
        assert len(svc.get_customer_payments(customer.id)) == 2

    def test_get_credit_payments(self):
        svc, _, credit_repo, customer_repo, _ = self._make()
        customer = self._add_customer(customer_repo)
        credit = self._add_credit(credit_repo, customer.id, "5000")
        svc.record_payment(
            RecordPaymentRequest(
                customer_id=customer.id,
                credit_id=credit.id,
                amount=Decimal("100"),
                method="cash",
            )
        )
        assert len(svc.get_credit_payments(credit.id)) == 1

    def test_get_all_payments(self):
        svc, _, credit_repo, customer_repo, _ = self._make()
        customer = self._add_customer(customer_repo)
        credit = self._add_credit(credit_repo, customer.id, "5000")
        svc.record_payment(
            RecordPaymentRequest(
                customer_id=customer.id,
                credit_id=credit.id,
                amount=Decimal("100"),
                method="cash",
            )
        )
        payments, total = svc.get_all_payments()
        assert len(payments) == 1
        assert total == 1

    def test_update_payment(self):
        svc, _, credit_repo, customer_repo, _ = self._make()
        customer = self._add_customer(customer_repo)
        credit = self._add_credit(credit_repo, customer.id, "5000")
        payment = svc.record_payment(
            RecordPaymentRequest(
                customer_id=customer.id,
                credit_id=credit.id,
                amount=Decimal("100"),
                method="cash",
            )
        )
        updated = svc.update_payment(payment.id, UpdatePaymentRequest(reference="REF-1"))
        assert updated.reference == "REF-1"

    def test_update_payment_not_found(self):
        svc, _, _, _, _ = self._make()
        with pytest.raises(ValueError):
            svc.update_payment("missing", UpdatePaymentRequest(reference="x"))

    def test_delete_payment(self):
        svc, _, credit_repo, customer_repo, _ = self._make()
        customer = self._add_customer(customer_repo)
        credit = self._add_credit(credit_repo, customer.id, "5000")
        payment = svc.record_payment(
            RecordPaymentRequest(
                customer_id=customer.id,
                credit_id=credit.id,
                amount=Decimal("100"),
                method="cash",
            )
        )
        svc.delete_payment(payment.id)
        assert svc.get_payment(payment.id) is None

