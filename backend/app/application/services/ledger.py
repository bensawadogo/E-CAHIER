"""
Ecahier - Règles de calcul des soldes.

Une seule définition, utilisée après toute modification ou suppression :

  - dette d'un client   = somme de ses crédits NON annulés
  - payé par un client  = somme de ses paiements
  - statut d'un crédit  = paid / partial / pending selon ses paiements
                          (un crédit « cancelled » reste annulé)

Sans cela, modifier ou supprimer un crédit/paiement laissait les totaux du
client et le statut du crédit faux.
"""

from typing import Optional


def sync_credit_status(credit, payment_repository, conn=None) -> bool:
    """Recalcule le statut du crédit d'après ses paiements. True si changé."""
    if credit.status == "cancelled":
        return False
    paid = payment_repository.total_paid_for_credit(credit.id, conn=conn)
    if paid >= credit.amount:
        new_status = "paid"
    elif paid > 0:
        new_status = "partial"
    else:
        new_status = "pending"
    if new_status == credit.status:
        return False
    {
        "paid": credit.mark_paid,
        "partial": credit.mark_partial,
        "pending": credit.mark_pending,
    }[new_status]()
    return True


def sync_customer_totals(
    customer_id: str,
    customer_repository,
    credit_repository,
    payment_repository,
    conn=None,
) -> bool:
    """Recalcule total_credit / total_paid du client. True si changé."""
    customer = customer_repository.get_by_id(customer_id, conn=conn)
    if customer is None:
        return False
    total_credit = credit_repository.total_amount_for_customer(customer_id, conn=conn)
    total_paid = payment_repository.total_paid_for_customer(customer_id, conn=conn)
    if customer.total_credit == total_credit and customer.total_paid == total_paid:
        return False
    customer.total_credit = total_credit
    customer.total_paid = total_paid
    customer_repository.update(customer, conn=conn)
    return True


def refresh_after_payment_change(
    customer_id: str,
    credit_id: Optional[str],
    customer_repository,
    credit_repository,
    payment_repository,
    conn=None,
) -> None:
    """Remet statut du crédit puis totaux du client d'aplomb."""
    credit = credit_repository.get_by_id(credit_id, conn=conn) if credit_id else None
    if credit is not None and sync_credit_status(credit, payment_repository, conn=conn):
        credit_repository.update(credit, conn=conn)
    sync_customer_totals(
        customer_id, customer_repository, credit_repository, payment_repository, conn=conn
    )
