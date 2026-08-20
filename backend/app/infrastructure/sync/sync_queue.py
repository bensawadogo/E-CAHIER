"""
Ecahier - Sync Queue
File de synchronisation persistante pour le mode offline-first.

Stratégie pour le contexte Burkina Faso :
  - Les opérations sont stockées localement (JSON) quand il n'y a pas de connexion
  - Elles sont rejouées automatiquement quand la connexion revient
  - Persistance sur disque pour survivre aux redémarrages
"""

import json
import logging
import os
from collections import deque
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


class SyncQueue:
    """File de synchronisation persistante pour les opérations offline."""

    def __init__(self, queue_file_path: str = "data/sync_queue.json"):
        self.queue_file_path = queue_file_path
        self._queue: Deque[Dict[str, Any]] = deque()
        self._load_queue()

    def _load_queue(self) -> None:
        """Charge la file depuis le fichier persistant."""
        if os.path.exists(self.queue_file_path):
            try:
                with open(self.queue_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._queue = deque(data)
                logger.info(
                    "File de sync chargée depuis %s (%d opérations)",
                    self.queue_file_path,
                    len(self._queue),
                )
            except json.JSONDecodeError:
                logger.error("Erreur décodage JSON sync queue — file réinitialisée")
                self._queue = deque()
            except Exception as e:
                logger.error("Erreur chargement sync queue: %s — file réinitialisée", e)
                self._queue = deque()

    def _save_queue(self) -> None:
        """Sauvegarde la file vers le fichier persistant."""
        try:
            os.makedirs(os.path.dirname(self.queue_file_path), exist_ok=True)
            with open(self.queue_file_path, "w", encoding="utf-8") as f:
                json.dump(list(self._queue), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Erreur sauvegarde sync queue vers %s: %s", self.queue_file_path, e)

    def enqueue(self, operation: Dict[str, Any]) -> None:
        """Ajoute une opération à la fin de la file."""
        self._queue.append(operation)
        self._save_queue()
        logger.info("Opération en file. Taille: %d", len(self._queue))

    def dequeue(self) -> Optional[Dict[str, Any]]:
        """Retire et retourne la première opération de la file. None si vide."""
        if self._queue:
            operation = self._queue.popleft()
            self._save_queue()
            logger.info("Opération défilée. Taille restante: %d", len(self._queue))
            return operation
        return None

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