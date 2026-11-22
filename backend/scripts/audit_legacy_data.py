#!/usr/bin/env python3
"""
Ecahier — Audit des données héritées de l'ancienne version de l'app.

Pourquoi : l'ancienne app envoyait les montants en « centimes » (5 000 FCFA
arrivaient comme 500 000) et créait des doublons à chaque renvoi (le serveur
ignorait l'identifiant fourni par le téléphone). Ce script aide à nettoyer la
base de production AVANT de déployer la nouvelle version.

Par défaut il est en LECTURE SEULE : il liste seulement ce qui paraît suspect.
Il ne devine rien : un crédit de 500 000 FCFA peut être légitime, c'est à vous
de désigner ceux à corriger.

Usage :
  # 1) Audit (aucune écriture)
  python backend/scripts/audit_legacy_data.py [--db chemin/cahier_boutique.db]

  # 2) Corriger des crédits précis (simulation par défaut)
  python backend/scripts/audit_legacy_data.py --divide-credit-by-100 ID1 ID2
  # ...puis, si la simulation est bonne :
  python backend/scripts/audit_legacy_data.py --divide-credit-by-100 ID1 ID2 --apply

Correction d'un crédit (--apply) : une sauvegarde complète de la base est
faite d'abord ; le montant du crédit, le total du client et les lignes du
journal « crédit » sont divisés ensemble dans UNE transaction ; `updated_at` est
mis à jour pour que les téléphones reçoivent la correction à leur prochaine
synchronisation (lecture incrémentale).
"""

import argparse
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
for _p in (BACKEND_DIR, REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ImportError:  # python-dotenv est optionnel
    pass

DEFAULT_THRESHOLD = Decimal("1000000")


# --------------------------------------------------------------------------
# Audit (lecture seule)
# --------------------------------------------------------------------------
def find_duplicate_customers(customers: list) -> List[list]:
    """Groupes de clients ayant le même nom ET le même téléphone."""
    groups: Dict[tuple, list] = defaultdict(list)
    for c in customers:
        key = (c.name.strip().lower(), (c.phone or "").strip())
        groups[key].append(c)
    return [g for g in groups.values() if len(g) > 1]


def find_suspect_credits(conn: sqlite3.Connection, threshold: Decimal) -> List[dict]:
    """Crédits ≥ seuil dont le montant est un multiple de 100.

    Un montant saisi en FCFA puis multiplié par 100 est toujours un multiple de
    100 ; c'est nécessaire (pas suffisant) pour être un crédit « ×100 ».
    """
    suspects = []
    for row in conn.execute(
        "SELECT id, customer_id, amount, description, created_at FROM credits"
    ):
        amount = Decimal(row[2])
        if amount >= threshold and amount % 100 == 0:
            suspects.append(
                {
                    "id": row[0],
                    "customer_id": row[1],
                    "amount": amount,
                    "description": row[3],
                    "created_at": row[4],
                }
            )
    return sorted(suspects, key=lambda s: s["amount"], reverse=True)


def find_total_mismatches(conn: sqlite3.Connection) -> List[dict]:
    """Clients dont total_credit / total_paid ≠ somme de leurs lignes (information)."""
    # Sommes en Decimal côté Python (les montants sont stockés en texte).
    credits: Dict[str, Decimal] = defaultdict(Decimal)
    for customer_id, amount in conn.execute("SELECT customer_id, amount FROM credits"):
        credits[customer_id] += Decimal(amount)
    paid: Dict[str, Decimal] = defaultdict(Decimal)
    try:
        for customer_id, amount in conn.execute("SELECT customer_id, amount FROM payments"):
            paid[customer_id] += Decimal(amount)
    except sqlite3.OperationalError:
        pass  # base sans table des paiements : aucun paiement à compter
    out = []
    for cid, total_credit, total_paid in conn.execute(
        "SELECT id, total_credit, total_paid FROM customers"
    ):
        exp_credit = credits.get(cid, Decimal(0))
        exp_paid = paid.get(cid, Decimal(0))
        if Decimal(total_credit) != exp_credit or Decimal(total_paid) != exp_paid:
            out.append(
                {
                    "customer_id": cid,
                    "total_credit": Decimal(total_credit),
                    "somme_credits": exp_credit,
                    "total_paid": Decimal(total_paid),
                    "somme_paiements": exp_paid,
                }
            )
    return out


# --------------------------------------------------------------------------
# Correction explicite
# --------------------------------------------------------------------------
def backup_database(conn: sqlite3.Connection, db_path: Path) -> Path:
    """Copie complète et cohérente de la base (API de sauvegarde SQLite)."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = db_path.with_name(f"{db_path.name}.avant-correction-{stamp}")
    dest = sqlite3.connect(str(target))
    try:
        conn.backup(dest)
    finally:
        dest.close()
    return target


def divide_credit_by_100(conn: sqlite3.Connection, credit_id: str, apply: bool) -> str:
    """Divise par 100 un crédit « centimes » ; renvoie une description de l'action.

    Refuse si le crédit est introuvable ou si son montant n'est pas un multiple
    de 100 (il ne peut alors pas venir d'un ×100).
    """
    row = conn.execute(
        "SELECT customer_id, amount FROM credits WHERE id = ?", (credit_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"crédit introuvable : {credit_id}")
    customer_id, old_text = row
    old = Decimal(old_text)
    if old % 100 != 0:
        raise ValueError(
            f"crédit {credit_id} : {old} n'est pas un multiple de 100, "
            "il ne vient pas d'un envoi en centimes."
        )
    new = old / 100
    delta = old - new

    line = f"crédit {credit_id} : {old} -> {new} FCFA (client {customer_id}, -{delta} sur sa dette)"
    if not apply:
        return "[simulation] " + line

    total_row = conn.execute(
        "SELECT total_credit FROM customers WHERE id = ?", (customer_id,)
    ).fetchone()
    if total_row is None:
        raise ValueError(f"client introuvable pour le crédit {credit_id}")
    new_total = Decimal(total_row[0]) - delta
    if new_total < 0:
        raise ValueError(
            f"crédit {credit_id} : le total du client deviendrait négatif "
            f"({new_total}) ; ses totaux sont déjà incohérents, vérifiez à la main."
        )
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE credits SET amount = ?, updated_at = ? WHERE id = ?",
        (str(new), now, credit_id),
    )
    conn.execute(
        "UPDATE customers SET total_credit = ?, updated_at = ? WHERE id = ?",
        (str(new_total), now, customer_id),
    )
    conn.execute(
        "UPDATE transactions SET amount = ? WHERE credit_id = ? AND type = 'credit'",
        (str(new), credit_id),
    )
    return "[appliqué] " + line


# --------------------------------------------------------------------------
# Programme principal
# --------------------------------------------------------------------------
def _load_customers(db_path: Path) -> list:
    """Clients déchiffrés (téléphone) via le dépôt de l'application."""
    from backend.app.infrastructure.database.repositories import SQLiteCustomerRepository
    from backend.app.infrastructure.database.sqlite_connection import SQLiteConnectionManager
    from backend.app.infrastructure.security.pii_encryptor import PIIEncryptor

    manager = SQLiteConnectionManager(db_path=str(db_path))
    repo = SQLiteCustomerRepository(manager, PIIEncryptor())
    customers, offset = [], 0
    while True:
        page = repo.get_all(offset=offset, limit=repo.MAX_PAGE_SIZE)
        customers.extend(page)
        if len(page) < repo.MAX_PAGE_SIZE:
            break
        offset += len(page)
    manager.close_connection()
    return customers


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--db", default=None, help="chemin de la base SQLite")
    parser.add_argument(
        "--threshold",
        type=Decimal,
        default=DEFAULT_THRESHOLD,
        help="montant à partir duquel un crédit est jugé suspect (défaut 1 000 000)",
    )
    parser.add_argument(
        "--divide-credit-by-100", nargs="+", metavar="ID",
        help="identifiants des crédits à diviser par 100",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="écrit réellement (sans cette option : simulation)",
    )
    args = parser.parse_args(argv)

    if args.db:
        db_path = Path(args.db)
    else:
        from backend.app.config import settings

        db_path = Path(settings.SQLITE_PATH)
    if not db_path.exists():
        print(f"Base introuvable : {db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(db_path))
    try:
        if args.divide_credit_by_100:
            if args.apply:
                backup = backup_database(conn, db_path)
                print(f"Sauvegarde : {backup}")
            try:
                conn.execute("BEGIN IMMEDIATE")
                for credit_id in args.divide_credit_by_100:
                    print(divide_credit_by_100(conn, credit_id, args.apply))
                if args.apply:
                    conn.commit()
                    print("Terminé. Redémarrez l'API si elle tourne pendant l'opération.")
                else:
                    conn.rollback()
                    print("Simulation seulement : ajoutez --apply pour écrire.")
            except ValueError as exc:
                conn.rollback()
                print(f"Annulé, rien n'a été modifié : {exc}", file=sys.stderr)
                return 1
            return 0

        print(f"Base : {db_path}  (lecture seule)\n")
        duplicates = find_duplicate_customers(_load_customers(db_path))
        print(f"== Clients en double (même nom + même téléphone) : {len(duplicates)} groupe(s)")
        for group in duplicates:
            print(f"  - {group[0].name!r} ({group[0].phone or 'sans téléphone'}) : "
                  + ", ".join(c.id for c in group))

        suspects = find_suspect_credits(conn, args.threshold)
        print(f"\n== Crédits >= {args.threshold} FCFA, multiples de 100 : {len(suspects)} à vérifier")
        for s in suspects:
            print(f"  - {s['id']}  {s['amount']} FCFA  {s['created_at']}  {s['description']!r}")
        if suspects:
            print("  Si l'un d'eux était en réalité X/100 : relancez avec "
                  "--divide-credit-by-100 <id> (simulation par défaut).")

        mismatches = find_total_mismatches(conn)
        print(f"\n== Totaux clients différents de la somme de leurs lignes : {len(mismatches)}")
        for m in mismatches[:20]:
            print(f"  - client {m['customer_id']} : dette {m['total_credit']} "
                  f"(lignes {m['somme_credits']}), payé {m['total_paid']} "
                  f"(lignes {m['somme_paiements']})")
        if len(mismatches) > 20:
            print(f"  ... et {len(mismatches) - 20} autre(s)")
        print("\nAucune écriture n'a été faite.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
