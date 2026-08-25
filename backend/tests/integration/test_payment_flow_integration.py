"""Tests d'intégration — flux métier complet : client → crédit → paiement → journal.

Stack RÉELLE : services applicatifs + repositories SQLite en mémoire + chiffrement
PII Fernet. Aucune couche interne mockée : on teste la collaboration des couches.
Les dépendances externes (serveur de sync) sont absentes par construction
(server_url=None), ce qui correspond au mode offline-first.

Le flux bout-en-bout via HTTP est couvert dans test_api_flow_integration.py.
"""

from decimal import Decimal

import pytest

from backend.app.application.dto.credit_dto import CreateCreditRequest
from backend.app.application.dto.customer_dto import CreateCustomerRequest
from backend.app.application.dto.payment_dto import RecordPaymentRequest
from backend.app.application.services.credit_service import CreditService
from backend.app.application.services.customer_service import CustomerService
from backend.app.application.services.payment_service import PaymentService


@pytest.fixture
def customer_service(customer_repo):
    return CustomerService(customer_repo)


@pytest.fixture
def credit_service(credit_repo, customer_repo):
    return CreditService(credit_repo, customer_repo)


@pytest.fixture
def payment_service(payment_repo, credit_repo, customer_repo, transaction_repo):
    return PaymentService(payment_repo, credit_repo, customer_repo, transaction_repo)


@pytest.fixture
def awa(customer_service):
    """Client 'Awa' créé via le service réel."""
    return customer_service.create_customer(
        CreateCustomerRequest(
            name="Awa Ouédraogo",
            phone="+226 70 12 34 56",
            address="Ouagadougou, Burkina Faso",
        )
    )


class TestFullPaymentFlow:
    def test_lifecycle_credit_partial_then_paid(self, awa, credit_service, payment_service):
        """Création crédit 5000 → paiement 2000 (partial) → paiement 3000 (paid)."""
        credit = credit_service.create_credit(
            CreateCreditRequest(customer_id=awa.id, amount=Decimal("5000"), description="Marchandises")
        )
        assert credit.status == "pending"

        # Paiement partiel
        p1 = payment_service.record_payment(
            RecordPaymentRequest(customer_id=awa.id, credit_id=credit.id, amount=Decimal("2000"), method="cash")
        )
        credit_after_partial = credit_service.get_credit(credit.id)
        assert credit_after_partial.status == "partial"
        assert p1.amount == Decimal("2000")

        # Solde complet
        p2 = payment_service.record_payment(
            RecordPaymentRequest(customer_id=awa.id, credit_id=credit.id, amount=Decimal("3000"), method="mobile_money")
        )
        credit_final = credit_service.get_credit(credit.id)
        assert credit_final.status == "paid"
        assert credit_final.is_paid
        assert p2.method == "mobile_money"

    def test_customer_totals_updated_across_payments(self, awa, credit_service, payment_service, customer_repo):
        """total_paid du client suit les paiements ; balance = total_credit - total_paid."""
        c1 = credit_service.create_credit(CreateCreditRequest(customer_id=awa.id, amount=Decimal("10000")))
        c2 = credit_service.create_credit(CreateCreditRequest(customer_id=awa.id, amount=Decimal("4000")))

        payment_service.record_payment(
            RecordPaymentRequest(customer_id=awa.id, credit_id=c1.id, amount=Decimal("6000"))
        )
        payment_service.record_payment(
            RecordPaymentRequest(customer_id=awa.id, credit_id=c2.id, amount=Decimal("4000"))
        )

        customer = customer_repo.get_by_id(awa.id)
        assert customer.total_credit == Decimal("14000")
        assert customer.total_paid == Decimal("10000")
        assert customer.balance == Decimal("4000")

    def test_transaction_ledger_one_entry_per_payment(self, awa, credit_service, payment_service, transaction_repo):
        """Chaque paiement génère une entrée type='payment' dans le journal."""
        credit = credit_service.create_credit(CreateCreditRequest(customer_id=awa.id, amount=Decimal("5000")))
        payment_service.record_payment(
            RecordPaymentRequest(customer_id=awa.id, credit_id=credit.id, amount=Decimal("2000"), method="cash", reference="R1")
        )
        payment_service.record_payment(
            RecordPaymentRequest(customer_id=awa.id, credit_id=credit.id, amount=Decimal("3000"), method="cash", reference="R2")
        )

        entries = transaction_repo.get_by_customer(awa.id)
        assert len(entries) == 2
        assert all(t.type == "payment" for t in entries)
        assert {t.description for t in entries} == {
            "Paiement cash - R1",
            "Paiement cash - R2",
        }
        amounts = sorted(t.amount for t in entries)
        assert amounts == [Decimal("2000"), Decimal("3000")]

    def test_overpayment_marks_credit_paid(self, awa, credit_service, payment_service):
        """Un trop-perçu (>= montant du crédit) clôt le crédit sans erreur."""
        credit = credit_service.create_credit(CreateCreditRequest(customer_id=awa.id, amount=Decimal("5000")))
        payment_service.record_payment(
            RecordPaymentRequest(customer_id=awa.id, credit_id=credit.id, amount=Decimal("6000"))
        )
        assert credit_service.get_credit(credit.id).status == "paid"

    @pytest.mark.parametrize(
        "field,value",
        [("customer_id", "client-inconnu"), ("credit_id", "credit-inconnu")],
    )
    def test_payment_with_unknown_reference_raises(self, awa, credit_service, payment_service, field, value):
        """Paiement sur client/crédit inexistant → ValueError avant toute écriture."""
        kwargs = {"customer_id": awa.id, "credit_id": "credit-x", "amount": Decimal("100")}
        kwargs[field] = value
        with pytest.raises(ValueError):
            payment_service.record_payment(RecordPaymentRequest(**kwargs))


class TestPiiEncryptionAtRest:
    def test_phone_encrypted_in_db_but_clear_via_repository(
        self, awa, customer_repo, in_memory_db
    ):
        """Intégration repo ↔ PIIEncryptor : chiffré en base, déchiffré à la lecture."""
        conn = in_memory_db.get_connection()
        row = conn.execute(
            "SELECT phone FROM customers WHERE id = ?", (awa.id,)
        ).fetchone()

        # En base : PAS le numéro en clair
        assert row["phone"] != awa.phone
        assert "+226" not in row["phone"]

        # Via le repository : déchiffré
        reloaded = customer_repo.get_by_id(awa.id)
        assert reloaded.phone == awa.phone

    def test_persistence_roundtrip_survives_new_repository(
        self, awa, in_memory_db, pii_encryptor
    ):
        """Les données restent lisibles avec une NOUVELLE instance de repository
        (même clé) — simule un redémarrage de l'app."""
        from backend.app.infrastructure.database.repositories import (
            SQLiteCustomerRepository,
        )

        fresh_repo = SQLiteCustomerRepository(in_memory_db, pii_encryptor)
        reloaded = fresh_repo.get_by_id(awa.id)
        assert reloaded is not None
        assert reloaded.name == awa.name
        assert reloaded.phone == awa.phone
