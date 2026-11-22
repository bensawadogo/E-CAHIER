"""Ecahier - Erreurs métier des services."""


class ConflictError(ValueError):
    """L'opération est refusée car elle laisserait des données incohérentes
    (ex. supprimer un crédit qui a déjà des paiements). Hérite de ValueError :
    le code existant qui attrape ValueError continue de fonctionner ; l'API la
    traduit en 409.
    """
