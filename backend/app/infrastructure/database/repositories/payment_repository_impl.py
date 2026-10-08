"""
Ecahier - Implémentation SQLite du Payment Repository
Adaptateur concret pour le port PaymentRepository.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from backend.app.domain.entities.payment import Payment
from backend.app.domain.repositories.payment_repository import PaymentRepository
from backend.app.infrastructure.database.sqlite_connection import SQLiteConnectionManager


class SQLitePaymentRepository(PaymentRepository):
    """Implémentation concrète du PaymentRepository utilisant SQLite."""

    # Pagination limits to prevent memory issues on low-end devices
    MAX_PAGE_SIZE = 200
    DEFAULT_PAGE_SIZE = 50

    def __init__(self, connection_manager: SQLiteConnectionManager):
        self.connection_manager = connection_manager
        self._create_table()

    def _create_table(self) -> None:
        """Crée la table 'payments' et ses index si elle n'existe pas."""
        with self.connection_manager.connection() as conn:
            # Create table with all constraints if not exists
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS payments (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    credit_id TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    method TEXT NOT NULL DEFAULT 'cash',
                    reference TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    payment_date TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    sync_status TEXT NOT NULL DEFAULT 'pending',
                    FOREIGN KEY (customer_id) REFERENCES customers(id),
                    FOREIGN KEY (credit_id) REFERENCES credits(id),
                    CHECK(method IN ('cash', 'mobile_money', 'bank_transfer', 'other')),
                    CHECK(sync_status IN ('pending', 'synced', 'conflict'))
                )
                """
            )
            # Index pour accélérer les filtres et tris fréquents
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_payments_credit ON payments(credit_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_payments_sync ON payments(sync_status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_payments_method ON payments(method)"
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
    def _row_to_payment(row: tuple) -> Payment:
        """Convertit une ligne SQLite en entité Payment.
        
        Utilise `sqlite3.Row` pour accéder aux colonnes par nom (TÂCHE 6).
        """
        return Payment(
            id=row["id"],
            customer_id=row["customer_id"],
            credit_id=row["credit_id"],
            amount=Decimal(row["amount"]),
            method=row["method"],
            reference=row["reference"],
            note=row["note"],
            payment_date=datetime.fromisoformat(row["payment_date"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            sync_status=row["sync_status"],
        )

    def add(self, payment: Payment, conn=None) -> Payment:
        """Ajoute un nouveau paiement à la base de données."""
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO payments
                    (id, customer_id, credit_id, amount, method, reference,
                     note, payment_date, created_at, updated_at, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payment.id, payment.customer_id, payment.credit_id,
                    str(payment.amount), payment.method, payment.reference,
                    payment.note, payment.payment_date.isoformat(),
                    payment.created_at.isoformat(), payment.updated_at.isoformat(),
                    payment.sync_status,
                ),
            )
        return payment

    def get_by_id(self, payment_id: str, conn=None) -> Optional[Payment]:
        """Récupère un paiement par son ID."""
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(
                """
                SELECT id, customer_id, credit_id, amount, method, reference,
                       note, payment_date, created_at, updated_at, sync_status
                FROM payments WHERE id = ?
                """,
                (payment_id,),
            )
            row = cur.fetchone()
            return self._row_to_payment(row) if row else None

    def get_by_customer(
        self,
        customer_id: str,
        offset: int = 0,
        limit: Optional[int] = None,
        conn=None,
    ) -> List[Payment]:
        """Retourne tous les paiements d'un client (paginé)."""
        # Enforce max page size to prevent memory issues on low-end devices
        if limit is None or limit > self.MAX_PAGE_SIZE:
            limit = self.DEFAULT_PAGE_SIZE
        pagination, params = self._pagination_sql(offset, limit)
        sql = (
            "SELECT id, customer_id, credit_id, amount, method, reference, "
            "note, payment_date, created_at, updated_at, sync_status "
            "FROM payments WHERE customer_id = ? ORDER BY payment_date DESC"
            + pagination
        )
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(sql, (customer_id,) + params)
            return [self._row_to_payment(row) for row in cur.fetchall()]

    def get_by_credit(
        self,
        credit_id: str,
        offset: int = 0,
        limit: Optional[int] = None,
        conn=None,
    ) -> List[Payment]:
        """Retourne tous les paiements liés à un crédit (paginé)."""
        # Enforce max page size to prevent memory issues on low-end devices
        if limit is None or limit > self.MAX_PAGE_SIZE:
            limit = self.DEFAULT_PAGE_SIZE
        pagination, params = self._pagination_sql(offset, limit)
        sql = (
            "SELECT id, customer_id, credit_id, amount, method, reference, "
            "note, payment_date, created_at, updated_at, sync_status "
            "FROM payments WHERE credit_id = ? ORDER BY payment_date DESC"
            + pagination
        )
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(sql, (credit_id,) + params)
            return [self._row_to_payment(row) for row in cur.fetchall()]

    def get_all(self, offset: int = 0, limit: Optional[int] = None, conn=None) -> List[Payment]:
        """Récupère tous les paiements (paginé)."""
        # Enforce max page size to prevent memory issues on low-end devices
        if limit is None or limit > self.MAX_PAGE_SIZE:
            limit = self.DEFAULT_PAGE_SIZE
        pagination, params = self._pagination_sql(offset, limit)
        sql = (
            "SELECT id, customer_id, credit_id, amount, method, reference, "
            "note, payment_date, created_at, updated_at, sync_status "
            "FROM payments ORDER BY payment_date DESC"
            + pagination
        )
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(sql, params)
            return [self._row_to_payment(row) for row in cur.fetchall()]

    def count_all(self, conn=None) -> int:
        """Retourne le nombre total de paiements."""
        with self.connection_manager.cursor(conn) as cur:
            cur.execute("SELECT COUNT(*) FROM payments")
            return int(cur.fetchone()[0])

    def total_paid_for_credit(self, credit_id: str, conn=None) -> Decimal:
        """Retourne le total des montants payés pour un crédit.

        Les montants sont stockés en TEXT (chaînes décimales exactes) et
        additionnés en Python avec `Decimal` : SQLite ne possède aucune
        arithmétique décimale exacte (SUM passerait par le double IEEE-754),
        ce qui faisait dériver le total cumulé sur de nombreux paiements.
        """
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(
                "SELECT amount FROM payments WHERE credit_id = ?",
                (credit_id,),
            )
            total = Decimal("0")
            for (amount_text,) in cur.fetchall():
                total += Decimal(amount_text)
            return total

    def update(self, payment: Payment, conn=None) -> Payment:
        """Met à jour un paiement existant."""
        if not payment.id:
            raise ValueError("L'ID du paiement est requis pour la mise à jour.")
        with self.connection_manager.cursor(conn) as cur:
            cur.execute(
                """
                UPDATE payments SET
                    customer_id = ?, credit_id = ?, amount = ?, method = ?,
                    reference = ?, note = ?, payment_date = ?,
                    updated_at = ?, sync_status = ?
                WHERE id = ?
                """,
                (
                    payment.customer_id, payment.credit_id, str(payment.amount),
                    payment.method, payment.reference, payment.note,
                    payment.payment_date.isoformat(), payment.updated_at.isoformat(),
                    payment.sync_status, payment.id,
                ),
            )
            if cur.rowcount == 0:
                raise ValueError(f"Aucun paiement trouvé avec l'ID {payment.id}.")
        return payment

    def delete(self, payment_id: str, conn=None) -> None:
        """Supprime un paiement par son ID."""
        with self.connection_manager.cursor(conn) as cur:
            cur.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
            if cur.rowcount == 0:
                raise ValueError(f"Aucun paiement trouvé avec l'ID {payment_id}.")