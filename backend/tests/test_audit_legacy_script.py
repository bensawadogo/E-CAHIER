"""Tests du script d'audit/correction des données héritées (centimes, doublons)."""

import importlib.util
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from backend.app.application.dto.credit_dto import CreateCreditRequest
from backend.app.application.dto.customer_dto import CreateCustomerRequest
from backend.app.application.services import CreditService, CustomerService
from backend.app.infrastructure.database.repositories import (
    SQLiteCreditRepository,
    SQLiteCustomerRepository,
    SQLitePaymentRepository,
    SQLiteTransactionRepository,
)
from backend.app.infrastructure.database.sqlite_connection import SQLiteConnectionManager
from backend.app.infrastructure.security.pii_encryptor import ENV_KEY_NAME, PIIEncryptor

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_legacy_data.py"


@pytest.fixture(scope="module")
def audit():
    spec = importlib.util.spec_from_file_location("audit_legacy_data", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def encryptor(monkeypatch):
    """Clé unique partagée avec le script (il lit CAHIER_PII_ENCRYPTION_KEY)."""
    key = Fernet.generate_key()
    monkeypatch.setenv(ENV_KEY_NAME, key.decode())
    return PIIEncryptor(key=key)


@pytest.fixture
def db(tmp_path, encryptor):
    """Base fichier avec : un client en double, un crédit ×100, un crédit normal."""
    path = tmp_path / "legacy.db"
    manager = SQLiteConnectionManager(db_path=str(path))
    customers = SQLiteCustomerRepository(manager, encryptor)
    SQLitePaymentRepository(manager)  # crée la table des paiements
    credits = SQLiteCreditRepository(manager)
    journal = SQLiteTransactionRepository(manager)
    customer_service = CustomerService(customers)
    credit_service = CreditService(credits, customers, journal, connection_manager=manager)

    a1 = customer_service.create_customer(CreateCustomerRequest(name="Awa", phone="70000000"))
    a2 = customer_service.create_customer(CreateCustomerRequest(name="awa ", phone="70000000"))
    other = customer_service.create_customer(CreateCustomerRequest(name="Moussa", phone="71111111"))

    legacy = credit_service.create_credit(
        CreateCreditRequest(customer_id=a1.id, amount=Decimal("500000"))  # 5 000 x100
    )
    normal = credit_service.create_credit(
        CreateCreditRequest(customer_id=other.id, amount=Decimal("2500"))
    )
    manager.close_connection()
    return {
        "path": path, "legacy": legacy, "normal": normal,
        "a1": a1, "a2": a2, "other": other,
    }


def _conn(db):
    return sqlite3.connect(str(db["path"]))


def test_finds_suspect_credits_only(audit, db):
    conn = _conn(db)
    suspects = audit.find_suspect_credits(conn, Decimal("100000"))
    assert [s["id"] for s in suspects] == [db["legacy"].id]


def test_finds_duplicate_customers(audit, db, encryptor):
    customers = SQLiteCustomerRepository(
        SQLiteConnectionManager(db_path=str(db["path"])), encryptor
    ).get_all(limit=200)
    groups = audit.find_duplicate_customers(customers)
    assert len(groups) == 1
    assert {c.id for c in groups[0]} == {db["a1"].id, db["a2"].id}


def test_totals_are_consistent_after_normal_creation(audit, db):
    assert audit.find_total_mismatches(_conn(db)) == []


def test_simulation_changes_nothing(audit, db):
    conn = _conn(db)
    message = audit.divide_credit_by_100(conn, db["legacy"].id, apply=False)
    assert "simulation" in message
    amount = conn.execute(
        "SELECT amount FROM credits WHERE id = ?", (db["legacy"].id,)
    ).fetchone()[0]
    assert Decimal(amount) == Decimal("500000")


def test_apply_fixes_credit_customer_total_and_journal_together(audit, db):
    conn = _conn(db)
    conn.execute("BEGIN IMMEDIATE")
    audit.divide_credit_by_100(conn, db["legacy"].id, apply=True)
    conn.commit()

    credit = conn.execute(
        "SELECT amount, updated_at FROM credits WHERE id = ?", (db["legacy"].id,)
    ).fetchone()
    assert Decimal(credit[0]) == Decimal("5000")
    total = conn.execute(
        "SELECT total_credit FROM customers WHERE id = ?", (db["a1"].id,)
    ).fetchone()[0]
    assert Decimal(total) == Decimal("5000")
    journal = conn.execute(
        "SELECT amount FROM transactions WHERE credit_id = ? AND type = 'credit'",
        (db["legacy"].id,),
    ).fetchone()[0]
    assert Decimal(journal) == Decimal("5000")
    # Les totaux restent cohérents avec les lignes.
    assert audit.find_total_mismatches(conn) == []


def test_refuses_amount_that_is_not_a_multiple_of_100(audit, db):
    conn = _conn(db)
    conn.execute(
        "UPDATE credits SET amount = '2550.50' WHERE id = ?", (db["normal"].id,)
    )
    with pytest.raises(ValueError, match="multiple de 100"):
        audit.divide_credit_by_100(conn, db["normal"].id, apply=True)


def test_unknown_credit_is_refused(audit, db):
    with pytest.raises(ValueError, match="introuvable"):
        audit.divide_credit_by_100(_conn(db), "inconnu", apply=False)


def test_cli_apply_makes_a_backup_and_is_atomic(audit, db, capsys):
    code = audit.main([
        "--db", str(db["path"]),
        "--divide-credit-by-100", db["legacy"].id, "inconnu",
        "--apply",
    ])
    assert code == 1  # le 2e identifiant n'existe pas : TOUT est annulé
    conn = _conn(db)
    amount = conn.execute(
        "SELECT amount FROM credits WHERE id = ?", (db["legacy"].id,)
    ).fetchone()[0]
    assert Decimal(amount) == Decimal("500000")
    # La sauvegarde a bien été faite avant de toucher à quoi que ce soit.
    backups = list(db["path"].parent.glob("legacy.db.avant-correction-*"))
    assert len(backups) == 1


def test_cli_audit_is_read_only(audit, db, capsys):
    code = audit.main(["--db", str(db["path"]), "--threshold", "100000"])
    out = capsys.readouterr().out
    assert code == 0
    assert db["legacy"].id in out
    assert "Aucune écriture" in out
    # L'audit ne crée aucune sauvegarde et ne modifie rien.
    assert not list(db["path"].parent.glob("*.avant-correction-*"))
    assert Decimal(_conn(db).execute(
        "SELECT amount FROM credits WHERE id = ?", (db["legacy"].id,)
    ).fetchone()[0]) == Decimal("500000")
