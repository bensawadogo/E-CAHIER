#!/usr/bin/env python3
"""
Ecahier — Rotation de la clé de chiffrement PII.

Phase de transition :
  - La clé principale (CAHIER_PII_ENCRYPTION_KEY, dans .env) chiffre les nouvelles
    valeurs.
  - L'ancienne clé (fichier .pii_key_dev) est chargée en secondaire tant qu'elle
    existe, de sorte que MultiFernet puisse encore LIRE les données chiffrées
    avec l'ancienne clé.
  - Ce script parcourt la base et re-chiffre chaque valeur PII avec la nouvelle
    clé (via MultiFernet.rotate). Une fois exécuté, l'ancien fichier .pii_key_dev
    peut être retiré du disque.

Sûreté :
  - Idempotent : re-exécuter ne dégrade rien (les valeurs déjà roulées sont
    simplement re-chiffrées à l'identique avec la première clé).
  - Transactionnel : toute erreur provoque un ROLLBACK, aucune écriture
    partielle n'est conservée.

Usage :
  python scripts/rotate_pii_key.py [chemin/vers/cahier_boutique.db]
"""

import os
import sqlite3
import sys
from pathlib import Path

from cryptography.fernet import Fernet, MultiFernet

# Racinisation : permet `python scripts/rotate_pii_key.py` depuis n'importe où
BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
for p in (BACKEND_DIR, REPO_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

from backend.app.infrastructure.security.pii_encryptor import ENV_KEY_NAME, LEGACY_KEY_NAME


def _load_legacy_key() -> bytes:
    """Charge l'ancienne clé depuis .pii_key_dev (fichier de transition)."""
    legacy_file = Path(__file__).resolve().parents[2] / "backend" / \
        "app" / "infrastructure" / "security" / LEGACY_KEY_NAME
    if not legacy_file.exists():
        sys.exit(f"[rotate] Ancienne clé introuvable : {legacy_file}")
    return legacy_file.read_bytes().strip()


def _resolve_db(argv_db: str) -> Path:
    """Résout le chemin de la base (relatif → racine du repo)."""
    p = Path(argv_db)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        sys.exit(f"[rotate] Base introuvable : {p}")
    return p


def rotate_db(db_path: Path, principal: bytes, legacy: bytes) -> int:
    """Re-chiffre les PII de la table customers. Retourne le nb de lignes touchées."""
    multi = MultiFernet([Fernet(principal), Fernet(legacy)])
    conn = sqlite3.connect(str(db_path))
    conn.execute("BEGIN")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, phone, address, photo_path FROM customers")
        rows = cur.fetchall()
        count = 0
        for cid, phone, address, photo in rows:
            new_phone = multi.rotate(phone.encode()) if phone else b""
            new_address = multi.rotate(address.encode()) if address else b""
            new_photo = multi.rotate(photo.encode()) if photo else b""
            cur.execute(
                "UPDATE customers SET phone=?, address=?, photo_path=? WHERE id=?",
                (new_phone.decode(), new_address.decode(), new_photo.decode(), cid),
            )
            count += 1
        conn.commit()
        return count
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main(argv: list) -> None:
    db_arg = argv[1] if len(argv) > 1 else "data/cahier_boutique.db"
    db_path = _resolve_db(db_arg)

    principal = os.environ.get(ENV_KEY_NAME)
    if not principal:
        sys.exit("[rotate] CAHIER_PII_ENCRYPTION_KEY absente du .env")
    legacy = _load_legacy_key()

    print(f"[rotate] Base : {db_path}")
    print(f"[rotate] Rotation PII (clé principale chargée [{len(principal)} car.], clé legacy de transition chargée [{len(legacy)} car.])")
    count = rotate_db(db_path, principal.encode("utf-8"), legacy)
    print(f"[rotate] Terminée : {count} ligne(s) re-chiffrée(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))