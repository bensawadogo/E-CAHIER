"""Tests complémentaires des services : branches non couvertes.

- CreditService avec transaction_repository (journal type='credit') + update complet
- CustomerService : update tous champs, attach_photo (OK / introuvable)
"""

from datetime import datetime
from decimal import Decimal

import pytest

from backend.app.application.dto.credit_dto import CreateCreditRequest, UpdateCreditRequest
from backend.app.application.dto.customer_dto import CreateCustomerRequest, UpdateCustomerRequest
from backend.app.application.services.credit_service import CreditService
from backend.app.application.services.customer_service import CustomerService


@pytest.fixture
def customer_service(customer_repo):
    return CustomerService(customer_repo)


@pytest.fixture
def full_credit_service(credit_repo, customer_repo, transaction_repo):
    """CreditService AVEC journal des transactions branché."""
    return CreditService(credit_repo, customer_repo, transaction_repo)


class TestCreditServiceJournal:
    def test_create_credit_writes_journal_entry(self, full_credit_service, customer_service, transaction_repo):
        """Créer un crédit avec repo de transactions → entrée type='credit'."""
        customer = customer_service.create_customer(CreateCustomerRequest(name="Client A"))
        credit = full_credit_service.create_credit(
            CreateCreditRequest(customer_id=customer.id, amount=Decimal("2500"))
        )

        entries = transaction_repo.get_by_customer(customer.id)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.type == "credit"
        assert entry.credit_id == credit.id
        assert entry.amount == Decimal("2500")
        # Description par défaut quand le crédit n'en a pas
        assert entry.description == "Crédit octroyé"

    def test_update_credit_all_fields(self, full_credit_service, customer_service):
        """update_credit applique montant, description, échéance et statut."""
        customer = customer_service.create_customer(CreateCustomerRequest(name="Client B"))
        credit = full_credit_service.create_credit(
            CreateCreditRequest(customer_id=customer.id, amount=Decimal("1000"), description="Avant")
        )
        new_due = datetime(2027, 1, 15, 12, 0, 0)

        updated = full_credit_service.update_credit(
            credit.id,
            UpdateCreditRequest(
                amount=Decimal("1500"),
                description="Après",
                due_date=new_due,
                status="cancelled",
            ),
        )

        assert updated.amount == Decimal("1500")
        assert updated.description == "Après"
        assert updated.due_date == new_due
        assert updated.status == "cancelled"


class TestCustomerServiceExtended:
    def test_update_customer_all_fields(self, customer_service, customer_repo):
        customer = customer_service.create_customer(
            CreateCustomerRequest(name="Initial", phone="70000000", address="Adresse 1", notes="Note 1")
        )

        updated = customer_service.update_customer(
            customer.id,
            UpdateCustomerRequest(
                name="Modifié",
                phone="76000000",
                address="Adresse 2",
                notes="Note 2",
                photo_path="photos/abc.jpg",
                is_active=False,
            ),
        )

        reloaded = customer_repo.get_by_id(customer.id)
        assert updated.name == "Modifié"
        assert updated.phone == "76000000"
        assert updated.address == "Adresse 2"
        assert updated.notes == "Note 2"
        assert updated.photo_path == "photos/abc.jpg"
        assert updated.is_active is False
        assert reloaded == updated

    def test_attach_photo_success(self, customer_service, customer_repo):
        customer = customer_service.create_customer(CreateCustomerRequest(name="Photo Client"))

        updated = customer_service.attach_photo(customer.id, "photos/client.jpg")

        assert updated.photo_path == "photos/client.jpg"
        assert customer_repo.get_by_id(customer.id).photo_path == "photos/client.jpg"

    def test_attach_photo_unknown_customer(self, customer_service):
        with pytest.raises(ValueError, match="introuvable"):
            customer_service.attach_photo("inconnu", "photos/x.jpg")
