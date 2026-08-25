"""
Ecahier - Implémentation SQLite du Customer Repository
Adaptateur concret pour le port CustomerRepository.

Sécurité intégrée :
  - Chiffrement AES-256 des PII (adresse, téléphone, chemin photo)
  - Protection contre le path traversal via validation des chemins
"""

import os
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from backend.app.domain.entities.customer import Customer
from backend.app.domain.repositories.customer_repository import CustomerRepository
from backend.app.infrastructure.database.sqlite_connection import SQLiteConnectionManager
from backend.app.infrastructure.security.path_sanitizer import PathSanitizer, PathTraversalError
from backend.app.infrastructure.security.pii_encryptor import PIIEncryptor


# Répertoire autorisé pour les photos — configurable via environnement
PHOTOS_DIR = os.environ.get("CAHIER_PHOTOS_DIR", "data/photos")


class SQLiteCustomerRepository(CustomerRepository):
    """Implémentation concrète du CustomerRepository utilisant SQLite."""

    def __init__(
        self,
        connection_manager: SQLiteConnectionManager,
        encryptor: Optional[PIIEncryptor] = None,
        path_sanitizer: Optional[PathSanitizer] = None,
    ):
        self.connection_manager = connection_manager
        self._encryptor = encryptor or PIIEncryptor()
        self._path_sanitizer = path_sanitizer or PathSanitizer(PHOTOS_DIR)
        self._create_table()

    # ------------------------------------------------------------------
    # Helpers PII
    # ------------------------------------------------------------------

    def _encrypt_pii(self, customer: Customer) -> dict:
        """Chiffre les champs PII (adresse, téléphone, photo_path)."""
        return {
            "id": customer.id,
            "name": customer.name,
            "phone": self._encryptor.encrypt(customer.phone),
            "address": self._encryptor.encrypt(customer.address),
            "notes": customer.notes,
            "photo_path": self._encryptor.encrypt(customer.photo_path),
            "total_credit": str(customer.total_credit),
            "total_paid": str(customer.total_paid),
            "is_active": int(customer.is_active),
            "created_at": customer.created_at.isoformat(),
            "updated_at": customer.updated_at.isoformat(),
            "sync_status": customer.sync_status,
        }

    def _decrypt_pii(self, row: tuple) -> Customer:
        """Convertit une ligne SQLite en Customer en déchiffrant les PII.
        
        Utilise `sqlite3.Row` pour accéder aux colonnes par nom (TÂCHE 6).
        """
        return Customer(
            id=row["id"],
            name=row["name"],
            phone=self._encryptor.decrypt(row["phone"]),
            address=self._encryptor.decrypt(row["address"]),
            notes=row["notes"],
            photo_path=self._encryptor.decrypt(row["photo_path"]),
            total_credit=Decimal(row["total_credit"]),
            total_paid=Decimal(row["total_paid"]),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            sync_status=row["sync_status"],
        )

    @staticmethod
    def _sanitize_photo_path(photo_path: str) -> str:
        """Valide et normalise un chemin de photo."""
        sanitizer = PathSanitizer(PHOTOS_DIR)
        return sanitizer.sanitize(photo_path)

    # ------------------------------------------------------------------
    # Gestion de la table
    # ------------------------------------------------------------------

    def _create_table(self) -> None:
        """Crée la table 'customers' et ses index si elle n'existe pas."""
        with self.connection_manager.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL DEFAULT '',
                    address TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    photo_path TEXT NOT NULL DEFAULT '',
                    total_credit TEXT NOT NULL DEFAULT '0.0',
                    total_paid TEXT NOT NULL DEFAULT '0.0',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    sync_status TEXT NOT NULL DEFAULT 'pending'
                )
                """
            )
            # Index pour accélérer le tri (ORDER BY name) et les filtres fréquents
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_customers_active ON customers(is_active)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_customers_sync ON customers(sync_status)"
            )

    @staticmethod
    def _pagination_sql(offset: int, limit: Optional[int]) -> tuple:
        """Construit la clause LIMIT/OFFSET et ses paramètres (SQLite)."""
        if limit is None:
            return " LIMIT -1 OFFSET ?", (offset,)  # -1 = pas de limite
        return " LIMIT ? OFFSET ?", (limit, offset)

    # ------------------------------------------------------------------
    # Opérations CRUD
    # ------------------------------------------------------------------

    def add(self, customer: Customer) -> Customer:
        """Ajoute un nouveau client à la base de données."""
        pii = self._encrypt_pii(customer)
        with self.connection_manager.cursor() as cur:
            cur.execute(
                """
                INSERT INTO customers
                    (id, name, phone, address, notes, photo_path,
                     total_credit, total_paid, is_active,
                     created_at, updated_at, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pii["id"], pii["name"], pii["phone"], pii["address"],
                    pii["notes"], pii["photo_path"],
                    pii["total_credit"], pii["total_paid"],
                    pii["is_active"], pii["created_at"],
                    pii["updated_at"], pii["sync_status"],
                ),
            )
        return customer

    def get_by_id(self, customer_id: str) -> Optional[Customer]:
        """Récupère un client par son ID."""
        with self.connection_manager.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, phone, address, notes, photo_path,
                       total_credit, total_paid, is_active,
                       created_at, updated_at, sync_status
                FROM customers WHERE id = ?
                """,
                (customer_id,),
            )
            row = cur.fetchone()
            return self._decrypt_pii(row) if row else None

    def get_all(self, offset: int = 0, limit: Optional[int] = None) -> List[Customer]:
        """Récupère tous les clients (paginé)."""
        pagination, params = self._pagination_sql(offset, limit)
        sql = (
            "SELECT id, name, phone, address, notes, photo_path, "
            "total_credit, total_paid, is_active, "
            "created_at, updated_at, sync_status "
            "FROM customers ORDER BY name ASC"
            + pagination
        )
        with self.connection_manager.cursor() as cur:
            cur.execute(sql, params)
            return [self._decrypt_pii(row) for row in cur.fetchall()]

    def get_active(self, offset: int = 0, limit: Optional[int] = None) -> List[Customer]:
        """Récupère les clients actifs uniquement (paginé)."""
        pagination, params = self._pagination_sql(offset, limit)
        sql = (
            "SELECT id, name, phone, address, notes, photo_path, "
            "total_credit, total_paid, is_active, "
            "created_at, updated_at, sync_status "
            "FROM customers WHERE is_active = 1 ORDER BY name ASC"
            + pagination
        )
        with self.connection_manager.cursor() as cur:
            cur.execute(sql, params)
            return [self._decrypt_pii(row) for row in cur.fetchall()]

    def count_all(self) -> int:
        """Retourne le nombre total de clients."""
        with self.connection_manager.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM customers")
            return int(cur.fetchone()[0])

    def count_active(self) -> int:
        """Retourne le nombre total de clients actifs."""
        with self.connection_manager.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM customers WHERE is_active = 1")
            return int(cur.fetchone()[0])

    def update(self, customer: Customer) -> Customer:
        """Met à jour un client existant."""
        if not customer.id:
            raise ValueError("L'ID du client est requis pour la mise à jour.")

        pii = self._encrypt_pii(customer)
        with self.connection_manager.cursor() as cur:
            cur.execute(
                """
                UPDATE customers SET
                    name = ?, phone = ?, address = ?, notes = ?,
                    photo_path = ?, total_credit = ?, total_paid = ?,
                    is_active = ?, updated_at = ?, sync_status = ?
                WHERE id = ?
                """,
                (
                    pii["name"], pii["phone"], pii["address"],
                    pii["notes"], pii["photo_path"],
                    pii["total_credit"], pii["total_paid"],
                    pii["is_active"], pii["updated_at"],
                    pii["sync_status"], pii["id"],
                ),
            )
            if cur.rowcount == 0:
                raise ValueError(f"Aucun client trouvé avec l'ID {customer.id}.")
        return customer

    def delete(self, customer_id: str) -> None:
        """Supprime un client par son ID."""
        with self.connection_manager.cursor() as cur:
            cur.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
            if cur.rowcount == 0:
                raise ValueError(f"Aucun client trouvé avec l'ID {customer_id}.")

    def search_by_name(
        self,
        query: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> List[Customer]:
        """Recherche des clients par nom (paginée, insensible à la casse)."""
        pagination, params = self._pagination_sql(offset, limit)
        sql = (
            "SELECT id, name, phone, address, notes, photo_path, "
            "total_credit, total_paid, is_active, "
            "created_at, updated_at, sync_status "
            "FROM customers WHERE name LIKE ? ORDER BY name ASC"
            + pagination
        )
        with self.connection_manager.cursor() as cur:
            cur.execute(sql, (f"%{query}%",) + params)
            return [self._decrypt_pii(row) for row in cur.fetchall()]

    # ------------------------------------------------------------------
    # Validation de photo avec protection path traversal
    # ------------------------------------------------------------------

    def validate_and_save_photo(self, customer_id: str, raw_filename: str) -> str:
        """
        Valide un nom de fichier photo et retourne le chemin sécurisé.

        Args:
            customer_id: ID du client (pour organisation des fichiers).
            raw_filename: Nom de fichier fourni par l'utilisateur.

        Returns:
            str: Chemin absolu sécurisé pour enregistrer la photo.

        Raises:
            PathTraversalError: Si le chemin tente de sortir du répertoire autorisé.
            ValueError: Si le nom de fichier est invalide.
        """
        # 1. Nettoyer le nom de fichier
        safe_name = PathSanitizer.sanitize_filename(raw_filename)

        # 2. Construire un chemin relatif organisé par client
        relative_path = f"{customer_id}/{safe_name}"

        # 3. Valider contre le path traversal
        full_path = self._path_sanitizer.sanitize(relative_path)

        return full_path