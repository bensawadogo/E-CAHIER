"""
Ecahier - Point d'entrée de l'application FastAPI.

Architecture Clean Architecture / DDD :
  - Domain : entités et interfaces de repositories
  - Application : services et DTOs
  - Infrastructure : SQLite, PostgreSQL, sécurité, sync, OCR
  - Presentation : API REST FastAPI

Contexte Burkina Faso :
  - Offline-first : SQLite local comme source de vérité
  - Sync différée : poussée vers serveur quand connexion disponible
  - Compression et pagination pour connexion faible
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings, setup_logging
from backend.app.infrastructure.database.sqlite_connection import SQLiteConnectionManager
from backend.app.infrastructure.database.repositories import (
    SQLiteCustomerRepository,
    SQLiteCreditRepository,
    SQLitePaymentRepository,
    SQLiteTransactionRepository,
)
from backend.app.infrastructure.security.pii_encryptor import PIIEncryptor
from backend.app.infrastructure.sync.sync_queue import SyncQueue
from backend.app.infrastructure.sync.sync_service import SyncService
from backend.app.application.services import CustomerService, CreditService, PaymentService, TransactionService
from backend.app.presentation.api import (
    customer_router,
    credit_router,
    payment_router,
    sync_router,
    transaction_router,
)
from backend.app.presentation.api.customer_api import set_customer_service
from backend.app.presentation.api.credit_api import set_credit_service
from backend.app.presentation.api.payment_api import set_payment_service
from backend.app.presentation.api.sync_api import set_sync_service
from backend.app.presentation.api.transaction_api import set_transaction_service
from backend.app.presentation.middleware import setup_middleware, AuthMiddleware

# Configuration du logging
setup_logging()
logger = logging.getLogger(__name__)


# Contexte de vie de l'application → TÂCHE 4 : durabilité SQLite
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie : checkpoint WAL à l'arrêt.

    Dans le contexte Burkina Faso (coupures secteur / arrachage câble USB),
    on force un `wal_checkpoint(TRUNCATE)` à l'arrêt du serveur pour pousser
    TOUTES les écritures du WAL-mode fichier DB principal. Cela garantit
    l'intégrité des données même en cas d'arrêt brutal ultérieur.
    """
    logger.info("Démarrage application — SQLite WAL mode actif (synchronous=FULL)")
    try:
        yield
    finally:
        logger.info("Arrêt application — checkpoint WAL (TRUNCATE) sur %s", settings.SQLITE_PATH)
        try:
            sqlite_manager.close_connection()
            sqlite_manager.get_connection()
            sqlite_manager.get_connection().execute("PRAGMA wal_checkpoint(TRUNCATE);")
            sqlite_manager.close_connection()
            logger.info("Checkpoint WAL terminé et connexion fermée")
        except Exception:
            logger.error("Erreur pendant le checkpoint WAL à l'arrêt", exc_info=True)

# Création de l'app FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API de gestion de caisse et de cahier de boutique — optimisée pour le Burkina Faso",
    lifespan=lifespan,
)

# Middleware (CORS, logging, auth)
setup_middleware(app)
app.add_middleware(AuthMiddleware)

# --- Dependency Injection ---

# Créer les répertoires nécessaires
os.makedirs(os.path.dirname(settings.SQLITE_PATH), exist_ok=True)
os.makedirs(settings.PHOTOS_DIR, exist_ok=True)
os.makedirs(settings.STORAGE_DIR, exist_ok=True)

# Infrastructure
sqlite_manager = SQLiteConnectionManager(db_path=settings.SQLITE_PATH)
encryptor = PIIEncryptor()
sync_queue = SyncQueue(queue_file_path=settings.SYNC_QUEUE_PATH)
sync_service = SyncService(
    sync_queue=sync_queue,
    server_url=settings.SERVER_URL or None,
    max_retries=settings.SYNC_MAX_RETRIES,
    base_delay=settings.SYNC_BASE_DELAY,
)

# Repositories
customer_repo = SQLiteCustomerRepository(sqlite_manager, encryptor)
credit_repo = SQLiteCreditRepository(sqlite_manager)
payment_repo = SQLitePaymentRepository(sqlite_manager)
transaction_repo = SQLiteTransactionRepository(sqlite_manager)

# Services
customer_service = CustomerService(customer_repo)
credit_service = CreditService(credit_repo, customer_repo, transaction_repo)
payment_service = PaymentService(payment_repo, credit_repo, customer_repo, transaction_repo)
transaction_service = TransactionService(transaction_repo)

# Injection des services dans les routers
set_customer_service(customer_service)
set_credit_service(credit_service)
set_payment_service(payment_service)
set_sync_service(sync_service)
set_transaction_service(transaction_service)

# --- Routes ---

app.include_router(customer_router)
app.include_router(credit_router)
app.include_router(payment_router)
app.include_router(sync_router)
app.include_router(transaction_router)


@app.get("/health")
def health_check():
    """Endpoint de santé — utilisé pour vérifier la disponibilité de l'API."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "sync_pending": sync_service.pending_count,
    }


@app.get("/status/commits")
def status_commits(limit: int = 20):
    """Endpoint pour le suivi client : renvoie les N derniers commits git."""
    import subprocess
    try:
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        result = subprocess.run(
            ["git", "--no-pager", "log", f"-{limit}", "--pretty=format:%H|%s|%ad",
             "--date=short"],
            capture_output=True, text=True, cwd=repo_root, timeout=5,
        )
        commits = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3:
                commits.append({"hash": parts[0], "message": parts[1], "date": parts[2]})
        return commits
    except Exception:
        return []


@app.get("/")
def root():
    """Endpoint racine — interface web si activée, sinon infos API."""
    if settings.SERVE_FRONTEND:
        from fastapi.responses import FileResponse
        _BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return FileResponse(os.path.join(_BASE_DIR, "web", "index.html"))
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


# --- Frontend (optionnel) ---
# Si CAHIER_SERVE_FRONTEND=true, le frontend statique (web) est servi à la racine.
# Important : les routes /api, /health, /docs et / sont enregistrées AVANT le montage pour rester prioritaires.
if settings.SERVE_FRONTEND:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _FRONTEND_DIR = os.path.join(_BASE_DIR, "web")
    logger.info("Serving frontend from %s", _FRONTEND_DIR)
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )