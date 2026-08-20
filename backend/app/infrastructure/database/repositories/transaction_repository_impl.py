"""
Ecahier - Implémentation SQLite du Transaction Repository
Adaptateur concret pour le port TransactionRepository.
Journal des opérations (crédits et paiements) par client.
"""

from collections import namedtuple
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from backend.app.domain.entities.transaction import Transaction
from backend.app.domain.repositories.transaction_repository import TransactionRepository
from backend.app.infrastructure.database.sqlite_connection import SQLiteConnectionManager

# ---------------------------------------------------------------------------
# Constantes partagées entre les méthodes du repository.
# ---------------------------------------------------------------------------

# Colonnes dans l'ordre exact du SELECT, correspondant à _Row et à la table.
_COLUMNS = (
    "id", "customer_id", "credit_id", "payment_id", "type",
    "amount", "balance_after", "description", "created_at", "sync_status",
)

_SELECT_SQL = (
    "SELECT id, customer_id, credit_id, payment_id, type, "
    "amount, balance_after, description, created_at, sync_status "
    "FROM transactions"
)

# Named tuple pour éviter les index positionnels fragiles dans _row_to_transaction.
_TransactionRow = namedtuple("_TransactionRow", _COLUMNS)


class SQLiteTransactionRepository(TransactionRepository):
    """Implémentation concrète du TransactionRepository utilisant SQLite."""

    def __init__(self, connection_manager: SQLiteConnectionManager):
        self.connection_manager = connection_manager
        self._create_table()

    def _create_table(self) -> None:
        """Crée la table 'transactions' et ses index si elle n'existe pas."""
        with self.connection_manager.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    credit_id TEXT NOT NULL DEFAULT '',
                    payment_id TEXT NOT NULL DEFAULT '',
                    type TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    balance_after TEXT NOT NULL DEFAULT '0.0',
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    sync_status TEXT NOT NULL DEFAULT 'pending',
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                )
                """
            )
            # Index pour accélérer les filtres et tris fréquents
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_transactions_customer "
                "ON transactions(customer_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_transactions_created "
                "ON transactions(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_transactions_sync "
                "ON transactions(sync_status)"
            )

    @staticmethod
    def _pagination_sql(offset: int, limit: Optional[int]) -> tuple:
        """Construit la clause LIMIT/OFFSET et ses paramètres (SQLite)."""
        if limit is None:
            return " LIMIT -1 OFFSET ?", (offset,)
        return " LIMIT ? OFFSET ?", (limit, offset)

    # ------------------------------------------------------------------
    # Helpers de conversion ligne <-> entité
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_transaction(row: tuple) -> Transaction:
        """Convertit une ligne SQLite en entité Transaction (via named tuple)."""
        r = _TransactionRow(*row)
        return Transaction(
            id=r.id,
            customer_id=r.customer_id,
            credit_id=r.credit_id,
            payment_id=r.payment_id,
            type=r.type,
            amount=Decimal(r.amount),
            balance_after=Decimal(r.balance_after),
            description=r.description,
            created_at=datetime.fromisoformat(r.created_at),
            sync_status=r.sync_status,
        )

    @staticmethod
    def _transaction_to_row(transaction: Transaction) -> tuple:
        """Convertit une entité Transaction en tuple pour INSERT."""
        return (
            transaction.id,
            transaction.customer_id,
            transaction.credit_id,
            transaction.payment_id,
            transaction.type,
            str(transaction.amount),
            str(transaction.balance_after),
            transaction.description,
            transaction.created_at.isoformat(),
            transaction.sync_status,
        )

    # ------------------------------------------------------------------
    # Opérations CRUD
    # ------------------------------------------------------------------

    def add(self, transaction: Transaction) -> Transaction:
        """Ajoute une nouvelle transaction au journal."""
        with self.connection_manager.cursor() as cur:
            cur.execute(
                """
                INSERT INTO transactions
                    (id, customer_id, credit_id, payment_id, type, amount,
                     balance_after, description, created_at, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._transaction_to_row(transaction),
            )
        return transaction

    def get_by_id(self, transaction_id: str) -> Optional[Transaction]:
        """Récupère une transaction par son ID."""
        with self.connection_manager.cursor() as cur:
            cur.execute(f"{_SELECT_SQL} WHERE id = ?", (transaction_id,))
            row = cur.fetchone()
            return self._row_to_transaction(row) if row else None

    def get_by_customer(
        self,
        customer_id: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Transaction]:
        """Retourne l'historique des transactions d'un client (paginé)."""
        pagination, params = self._pagination_sql(offset, limit)
        sql = (
            f"{_SELECT_SQL} WHERE customer_id = ? ORDER BY created_at DESC"
            + pagination
        )
        with self.connection_manager.cursor() as cur:
            cur.execute(sql, (customer_id,) + params)
            return [self._row_to_transaction(row) for row in cur.fetchall()]

    def get_all(self, offset: int = 0, limit: Optional[int] = None) -> List[Transaction]:
        """Retourne la liste de toutes les transactions (paginé)."""
        pagination, params = self._pagination_sql(offset, limit)
        sql = f"{_SELECT_SQL} ORDER BY created_at DESC" + pagination
        with self.connection_manager.cursor() as cur:
            cur.execute(sql, params)
            return [self._row_to_transaction(row) for row in cur.fetchall()]

    def count_all(self) -> int:
        """Retourne le nombre total de transactions."""
        with self.connection_manager.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM transactions")
            return int(cur.fetchone()[0])

    def get_pending_sync(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Transaction]:
        """Retourne les transactions en attente de synchronisation (paginé)."""
        pagination, params = self._pagination_sql(offset, limit)
        sql = (
            f"{_SELECT_SQL} WHERE sync_status = 'pending' ORDER BY created_at ASC"
            + pagination
        )
        with self.connection_manager.cursor() as cur:
            cur.execute(sql, params)
            return [self._row_to_transaction(row) for row in cur.fetchall()]

    def delete(self, transaction_id: str) -> None:
        """Supprime une transaction par son ID."""
        with self.connection_manager.cursor() as cur:
            cur.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
            if cur.rowcount == 0:
                raise ValueError(
                    f"Aucune transaction trouvée avec l'ID {transaction_id}."
                )
