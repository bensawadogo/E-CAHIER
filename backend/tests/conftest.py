"""Pytest configuration and shared fixtures for the backend test suite.

Sets up a hermetic test environment:
  - repository root on sys.path so ``backend.app.*`` imports resolve
  - all database / sync / photos / storage paths point to a temporary dir
  - a deterministic PII encryption key (no dev-key file writes)
  - in-memory SQLite repositories shared across tests
  - a FastAPI TestClient with every service bound to the in-memory database
"""

import os
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Path setup — make the repository root importable.
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# 2. Environment setup — MUST happen before any ``backend.app.*`` import so
#    that ``Settings`` reads the temporary paths.
# ---------------------------------------------------------------------------
_TMP_ROOT = tempfile.mkdtemp(prefix="cahier_test_")

from cryptography.fernet import Fernet  # noqa: E402

os.environ["CAHIER_SQLITE_PATH"] = os.path.join(_TMP_ROOT, "test.db")
os.environ["CAHIER_SYNC_QUEUE_PATH"] = os.path.join(_TMP_ROOT, "sync_queue.json")
os.environ["CAHIER_PHOTOS_DIR"] = os.path.join(_TMP_ROOT, "photos")
os.environ["CAHIER_STORAGE_DIR"] = os.path.join(_TMP_ROOT, "storage")
os.environ["CAHIER_PII_ENCRYPTION_KEY"] = Fernet.generate_key().decode("utf-8")
os.environ["CAHIER_SERVER_URL"] = ""
os.environ["CAHIER_DEBUG"] = "false"

import pytest  # noqa: E402


# ---------------------------------------------------------------------------
# Infrastructure fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def in_memory_db():
    """SQLite connection manager bound to a fresh in-memory database."""
    from backend.app.infrastructure.database.sqlite_connection import (
        SQLiteConnectionManager,
    )

    manager = SQLiteConnectionManager(db_path=":memory:")
    manager.get_connection()
    yield manager
    manager.close_connection()


@pytest.fixture
def pii_encryptor():
    """PIIEncryptor with a fresh random key (no dev-key file writes)."""
    from backend.app.infrastructure.security.pii_encryptor import PIIEncryptor

    return PIIEncryptor(key=Fernet.generate_key())


@pytest.fixture
def customer_repo(in_memory_db, pii_encryptor):
    from backend.app.infrastructure.database.repositories.customer_repository_impl import (
        SQLiteCustomerRepository,
    )

    return SQLiteCustomerRepository(in_memory_db, pii_encryptor)


@pytest.fixture
def credit_repo(in_memory_db):
    from backend.app.infrastructure.database.repositories.credit_repository_impl import (
        SQLiteCreditRepository,
    )

    return SQLiteCreditRepository(in_memory_db)


@pytest.fixture
def payment_repo(in_memory_db):
    from backend.app.infrastructure.database.repositories.payment_repository_impl import (
        SQLitePaymentRepository,
    )

    return SQLitePaymentRepository(in_memory_db)


@pytest.fixture
def transaction_repo(in_memory_db):
    from backend.app.infrastructure.database.repositories.transaction_repository_impl import (
        SQLiteTransactionRepository,
    )

    return SQLiteTransactionRepository(in_memory_db)


@pytest.fixture
def sync_queue(tmp_path):
    """SyncQueue persisted to a temp file."""
    from backend.app.infrastructure.sync.sync_queue import SyncQueue

    return SyncQueue(queue_file_path=str(tmp_path / "sync_queue.json"))


@pytest.fixture
def sync_service(sync_queue):
    """SyncService with no server configured (offline mode)."""
    from backend.app.infrastructure.sync.sync_service import SyncService

    return SyncService(
        sync_queue=sync_queue,
        server_url=None,
        max_retries=1,
        base_delay=0.01,
    )


# ---------------------------------------------------------------------------
# Service fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def customer_service(customer_repo):
    from backend.app.application.services.customer_service import CustomerService

    return CustomerService(customer_repo)


@pytest.fixture
def credit_service(credit_repo, customer_repo):
    from backend.app.application.services.credit_service import CreditService

    return CreditService(credit_repo, customer_repo)


@pytest.fixture
def payment_service(payment_repo, credit_repo, customer_repo, transaction_repo):
    from backend.app.application.services.payment_service import PaymentService

    return PaymentService(payment_repo, credit_repo, customer_repo, transaction_repo)


# ---------------------------------------------------------------------------
# Sample domain entities
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_customer():
    from backend.app.domain.entities.customer import Customer

    return Customer(name="Awa Ouédraogo", phone="+226 70 12 34 56")


@pytest.fixture
def sample_credit():
    from backend.app.domain.entities.credit import Credit

    return Credit(
        customer_id="customer-1",
        amount=Decimal("5000"),
        description="Marchandises",
    )


@pytest.fixture
def sample_payment():
    from backend.app.domain.entities.payment import Payment

    return Payment(
        customer_id="customer-1",
        credit_id="credit-1",
        amount=Decimal("2000"),
        method="cash",
    )


# ---------------------------------------------------------------------------
# API test client — everything wired to the in-memory database
# ---------------------------------------------------------------------------
@pytest.fixture
def client(in_memory_db, pii_encryptor):
    """FastAPI TestClient with all services bound to a fresh in-memory DB."""
    from fastapi.testclient import TestClient

    import backend.app.main as main_module
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
    from backend.app.infrastructure.sync.sync_queue import SyncQueue
    from backend.app.infrastructure.sync.sync_service import SyncService
    from backend.app.presentation.api.credit_api import set_credit_service
    from backend.app.presentation.api.customer_api import set_customer_service
    from backend.app.presentation.api.payment_api import set_payment_service
    from backend.app.presentation.api.sync_api import set_sync_service

    customer_repo = SQLiteCustomerRepository(in_memory_db, pii_encryptor)
    credit_repo = SQLiteCreditRepository(in_memory_db)
    payment_repo = SQLitePaymentRepository(in_memory_db)
    transaction_repo = SQLiteTransactionRepository(in_memory_db)

    sync_queue = SyncQueue(
        queue_file_path=os.path.join(_TMP_ROOT, "sync_queue_client.json")
    )
    sync_service = SyncService(
        sync_queue=sync_queue,
        server_url=None,
        max_retries=1,
        base_delay=0.01,
    )

    set_customer_service(CustomerService(customer_repo))
    set_credit_service(CreditService(credit_repo, customer_repo))
    set_payment_service(
        PaymentService(payment_repo, credit_repo, customer_repo, transaction_repo)
    )
    set_sync_service(sync_service)
    # /health reads this module-level global.
    main_module.sync_service = sync_service

    with TestClient(main_module.app) as c:
        yield c

