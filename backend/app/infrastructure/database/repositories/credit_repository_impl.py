"""
Ecahier - Implémentation SQLite du Credit Repository
Adaptateur concret pour le port CreditRepository.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from backend.app.domain.entities.credit import Credit
from backend.app.domain.repositories.credit_repository import CreditRepository
from backend.app.infrastructure.database.sqlite_connection import SQLiteConnectionManager


class SQLiteCreditRepository(CreditRepository):
    """Implémentation concrète du CreditRepository utilisant SQLite."""

    # Pagination limits to prevent memory issues on low-end devices
    MAX_PAGE_SIZE = 200
    DEFAULT_PAGE_SIZE = 50

    def __init__(self, connection_manager: SQLiteConnectionManager):
        self.connection_manager = connection_manager
        self._create_table()

    def _create_table(self) -> None:
        """Crée la table 'credits' et ses index si elle n'existe pas."""
        with self.connection_manager.connection() as conn:
            # Create table with all constraints if not exists
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS credits (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    due_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    sync_status TEXT NOT NULL DEFAULT 'pending',
                    FOREIGN KEY (customer_id) REFERENCES customers(id),
                    CHECK(status IN ('pending', 'partial', 'paid', 'cancelled')),
                    CHECK(sync_status IN ('pending', 'synced', 'conflict'))
                )
                """
            )
            # Index pour accélérer les filtres et tris fréquents
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_credits_customer ON credits(customer_id)"
            )
            # Composite index for overdue query (status, due_date) - SQLite can only use one index per query
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_credits_status_due_date ON credits(status, due_date)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_credits_sync ON credits(sync_status)"
            )
            # Schema version tracking for future migrations
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version < 1:
                conn.execute("PRAGMA user_version = 1")

    @staticmethod
    def _pagination_sql(offset: int, limit: Optional[int]) -> tuple:
        """Construit la clause LIMIT/OFFSET et ses paramètres (SQLite)."""
        if limit is None:
            return " LIMIT -1 OFFSET ?", (offset,)
        return " LIMIT ? OFFSET ?", (limit, offset)

    @staticmethod
    def _row_to_credit(row: tuple) -> Credit:
        """Convertit une ligne SQLite en entité Credit.
        
        Utilise `sqlite3.Row` pour accéder aux colonnes par nom (TÂCHE 6).
        """
        return Credit(
            id=row["id"],
            customer_id=row["customer_id"],
            amount=Decimal(row["amount"]),
            description=row["description"],
            due_date=datetime.fromisoformat(row["due_date"]),
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            sync_status=row["sync_status"],
        )

    def add(self, credit: Credit, conn=None) -> Credit:
        """Ajoute un nouveau crédit à la base de données."""
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO credits
                    (id, customer_id, amount, description, due_date,
                     status, created_at, updated_at, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    credit.id, credit.customer_id, str(credit.amount),
                    credit.description, credit.due_date.isoformat(),
                    credit.status, credit.created_at.isoformat(),
                    credit.updated_at.isoformat(), credit.sync_status,
                ),
            )
        return credit

    def get_by_id(self, credit_id: str, conn=None) -> Optional[Credit]:
        """Récupère un crédit par son ID."""
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(
                """
                SELECT id, customer_id, amount, description, due_date,
                       status, created_at, updated_at, sync_status
                FROM credits WHERE id = ?
                """,
                (credit_id,),
            )
            row = cur.fetchone()
            return self._row_to_credit(row) if row else None

    def get_by_customer(
        self,
        customer_id: str,
        offset: int = 0,
        limit: Optional[int] = None,
        conn=None,
    ) -> List[Credit]:
        """Retourne tous les crédits d'un client (paginé)."""
        # Enforce max page size to prevent memory issues on low-end devices
        if limit is None or limit > self.MAX_PAGE_SIZE:
            limit = self.DEFAULT_PAGE_SIZE
        pagination, params = self._pagination_sql(offset, limit)
        sql = (
            "SELECT id, customer_id, amount, description, due_date, "
            "status, created_at, updated_at, sync_status "
            "FROM credits WHERE customer_id = ? ORDER BY created_at DESC"
            + pagination
        )
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(sql, (customer_id,) + params)
            return [self._row_to_credit(row) for row in cur.fetchall()]

    def get_all(self, offset: int = 0, limit: Optional[int] = None, conn=None) -> List[Credit]:
        """Récupère tous les crédits (paginé)."""
        # Enforce max page size to prevent memory issues on low-end devices
        if limit is None or limit > self.MAX_PAGE_SIZE:
            limit = self.DEFAULT_PAGE_SIZE
        pagination, params = self._pagination_sql(offset, limit)
        sql = (
            "SELECT id, customer_id, amount, description, due_date, "
            "status, created_at, updated_at, sync_status "
            "FROM credits ORDER BY created_at DESC"
            + pagination
        )
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(sql, params)
            return [self._row_to_credit(row) for row in cur.fetchall()]

    def get_pending(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
        conn=None,
    ) -> List[Credit]:
        """Retourne les crédits non payés (pending ou partial) — paginé."""
        # Enforce max page size to prevent memory issues on low-end devices
        if limit is None or limit > self.MAX_PAGE_SIZE:
            limit = self.DEFAULT_PAGE_SIZE
        pagination, params = self._pagination_sql(offset, limit)
        sql = (
            "SELECT id, customer_id, amount, description, due_date, "
            "status, created_at, updated_at, sync_status "
            "FROM credits WHERE status IN ('pending', 'partial') "
            "ORDER BY due_date ASC"
            + pagination
        )
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(sql, params)
            return [self._row_to_credit(row) for row in cur.fetchall()]

    def get_overdue(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
        conn=None,
    ) -> List[Credit]:
        """Retourne les crédits en retard (échéance dépassée et non payé) — paginé."""
        now = datetime.now(timezone.utc).isoformat()
        # Enforce max page size to prevent memory issues on low-end devices
        if limit is None or limit > self.MAX_PAGE_SIZE:
            limit = self.DEFAULT_PAGE_SIZE
        pagination, params = self._pagination_sql(offset, limit)
        sql = (
            "SELECT id, customer_id, amount, description, due_date, "
            "status, created_at, updated_at, sync_status "
            "FROM credits WHERE status IN ('pending', 'partial') AND due_date < ? "
            "ORDER BY due_date ASC"
            + pagination
        )
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(sql, (now,) + params)
            return [self._row_to_credit(row) for row in cur.fetchall()]

    def count_all(self, conn=None) -> int:
        """Retourne le nombre total de crédits."""
        with self.connection_manager.cursor(conn) as cur:
            cur.execute("SELECT COUNT(*) FROM credits")
            return int(cur.fetchone()[0])

    def count_pending(self, conn=None) -> int:
        """Retourne le nombre de crédits non payés (pending ou partial)."""
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(
                "SELECT COUNT(*) FROM credits WHERE status IN ('pending', 'partial')"
            )
            return int(cur.fetchone()[0])

    def count_overdue(self, conn=None) -> int:
        """Retourne le nombre de crédits en retard (échéance dépassée)."""
        now = datetime.now(timezone.utc).isoformat()
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(
                "SELECT COUNT(*) FROM credits "
                "WHERE status IN ('pending', 'partial') AND due_date < ?",
                (now,),
            )
            return int(cur.fetchone()[0])

    def update(self, credit: Credit, conn=None) -> Credit:
        """Met à jour un crédit existant."""
        if not credit.id:
            raise ValueError("L'ID du crédit est requis pour la mise à jour.")
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(
                """
                UPDATE credits SET
                    customer_id = ?, amount = ?, description = ?,
                    due_date = ?, status = ?, updated_at = ?, sync_status = ?
                WHERE id = ?
                """,
                (
                    credit.customer_id, str(credit.amount), credit.description,
                    credit.due_date.isoformat(), credit.status,
                    credit.updated_at.isoformat(), credit.sync_status, credit.id,
                ),
            )
            if cur.rowcount == 0:
                raise ValueError(f"Aucun crédit trouvé avec l'ID {credit.id}.")
        return credit

    def delete(self, credit_id: str, conn=None) -> None:
        """Supprime un crédit par son ID."""
        with self.connection_manager.cursor(conn) as cur:
            cur.execute("DELETE FROM credits WHERE id = ?", (credit_id,))
            if cur.rowcount == 0:
                raise ValueError(f"Aucun crédit trouvé avec l'ID {credit_id}.")
