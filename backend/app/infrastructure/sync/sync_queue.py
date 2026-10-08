"""
Ecahier - Sync Queue
File de synchronisation persistante pour le mode offline-first.

Stratégie pour le contexte Burkina Faso :
  - Les opérations sont stockées localement (JSON) quand il n'y a pas de connexion
  - Elles sont rejouées automatiquement quand la connexion revient
  - Persistance sur disque pour survivre aux redémarrages
  - Écriture atomique (write-to-tmp + os.replace) pour survivre aux coupures de courant
  - Clé d'idempotence UUID4 par opération pour éviter les doublons serveur
"""

import json
import logging
import os
import uuid
from collections import deque
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


class SyncQueue:
    """File de synchronisation persistante pour les opérations offline."""

    def __init__(self, queue_file_path: str = "data/sync_queue.json"):
        self.queue_file_path = queue_file_path
        self.dead_letter_path = queue_file_path.replace(".json", "_dead_letter.json")
        self._queue: Deque[Dict[str, Any]] = deque()
        self._load_queue()

    def _load_queue(self) -> None:
        """Charge la file depuis le fichier persistant. Tente une récupération partielle si corrompu."""
        if not os.path.exists(self.queue_file_path):
            return

        try:
            with open(self.queue_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("Format de file invalide: attendu une liste")
            self._queue = deque(data)
            logger.info(
                "File de sync chargée depuis %s (%d opérations)",
                self.queue_file_path,
                len(self._queue),
            )
        except json.JSONDecodeError as e:
            logger.error("Erreur décodage JSON sync queue à la position %d: %s", e.pos, e)
            recovered = self._try_recover_partial_queue()
            if recovered:
                logger.warning("Récupération partielle: %d opérations sauvées", len(recovered))
                self._queue = deque(recovered)
            else:
                logger.error("Impossible de récupérer la file — réinitialisation")
                self._queue = deque()
        except Exception as e:
            logger.error("Erreur chargement sync queue: %s — file réinitialisée", e)
            self._queue = deque()

    def _try_recover_partial_queue(self) -> List[Dict[str, Any]]:
        """Tente de récupérer des opérations valides depuis un fichier JSON corrompu."""
        recovered = []
        try:
            with open(self.queue_file_path, "r", encoding="utf-8") as f:
                content = f.read()

            decoder = json.JSONDecoder()
            pos = 0
            while pos < len(content):
                try:
                    obj, new_pos = decoder.raw_decode(content, pos)
                    if isinstance(obj, dict) and "idempotency_key" in obj:
                        recovered.append(obj)
                    pos = new_pos
                except json.JSONDecodeError:
                    pos += 1
        except Exception as e:
            logger.error("Échec récupération partielle: %s", e)
        return recovered

    def _save_queue(self) -> None:
        """Sauvegarde la file vers le fichier persistant de façon atomique."""
        tmp_path = self.queue_file_path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.queue_file_path), exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(list(self._queue), f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.queue_file_path)
        except Exception as e:
            logger.error("Erreur sauvegarde sync queue vers %s: %s", self.queue_file_path, e)
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def _save_dead_letter(self, operation: Dict[str, Any]) -> None:
        """Sauvegarde une opération échouée dans le fichier dead-letter."""
        try:
            dead_letters = []
            if os.path.exists(self.dead_letter_path):
                with open(self.dead_letter_path, "r", encoding="utf-8") as f:
                    dead_letters = json.load(f)
            dead_letters.append(operation)
            tmp_path = self.dead_letter_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(dead_letters, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.dead_letter_path)
            logger.warning("Opération déplacée vers dead-letter: %s", operation.get("idempotency_key"))
        except Exception as e:
            logger.error("Erreur écriture dead-letter: %s", e)

    def enqueue(self, operation: Dict[str, Any]) -> str:
        """
        Ajoute une opération à la fin de la file avec une clé d'idempotence.

        Returns:
            str: La clé d'idempotence générée (UUID4).
        """
        idempotency_key = str(uuid.uuid4())
        operation_with_key = {**operation, "idempotency_key": idempotency_key}
        self._queue.append(operation_with_key)
        self._save_queue()
        logger.info("Opération en file. Clé: %s. Taille: %d", idempotency_key, len(self._queue))
        return idempotency_key

    def dequeue(self) -> Optional[Dict[str, Any]]:
        """
        Retire et retourne la première opération de la file. None si vide.
        Sauvegarde AVANT de retirer pour ne pas perdre l'opération si l'écriture échoue.
        """
        if not self._queue:
            return None

        operation = self._queue[0]
        self._save_queue()
        self._queue.popleft()
        self._save_queue()
        logger.info("Opération défilée. Clé: %s. Taille restante: %d", operation.get("idempotency_key"), len(self._queue))
        return operation

    def peek(self) -> Optional[Dict[str, Any]]:
        """Regarde la première opération sans la retirer. None si vide."""
        if self._queue:
            return self._queue[0]
        return None

    def is_empty(self) -> bool:
        """Vérifie si la file est vide."""
        return len(self._queue) == 0

    def size(self) -> int:
        """Retourne la taille actuelle de la file."""
        return len(self._queue)

    def get_all(self) -> List[Dict[str, Any]]:
        """Retourne toutes les opérations sans les retirer (pour inspection)."""
        return list(self._queue)

    def clear(self) -> None:
        """Vide la file et supprime le fichier persistant."""
        self._queue.clear()
        if os.path.exists(self.queue_file_path):
            os.remove(self.queue_file_path)
        logger.info("File de sync vidée.")

    def move_to_dead_letter(self, operation: Dict[str, Any]) -> None:
        """Déplace une opération vers le dead-letter et la retire de la file principale."""
        if self._queue and self._queue[0] is operation:
            self._queue.popleft()
            self._save_queue()
        self._save_dead_letter(operation)