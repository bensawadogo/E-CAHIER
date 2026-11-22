"""
Ecahier - Injection de dépendances FastAPI.

Les services sont posés sur ``app.state`` au démarrage (main.py) et lus par les
routes via ``Depends``. Plus de variables globales de module : chaque
application (donc chaque test) porte ses propres services, et un test peut les
remplacer avec ``app.dependency_overrides`` ou ``app.state``.
"""

from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import HTTPException, Query, Request, status


def service_getter(state_name: str, label: str) -> Callable[[Request], object]:
    """Fabrique une dépendance qui lit ``request.app.state.<state_name>``."""

    def dependency(request: Request):
        service = getattr(request.app.state, state_name, None)
        if service is None:
            raise RuntimeError(f"{label} non initialisé.")
        return service

    dependency.__name__ = f"get_{state_name}"
    return dependency


def updated_since_param(
    updated_since: Optional[str] = Query(
        None,
        description=(
            "Lecture incrémentale : ne renvoie que ce qui a changé depuis cet "
            "instant (ISO 8601, ex. 2026-11-22T10:00:00+00:00). Économise la "
            "connexion des téléphones : on ne retélécharge pas tout."
        ),
    ),
) -> Optional[str]:
    """Valide ``?updated_since=`` et le normalise en ISO 8601 UTC."""
    if not updated_since:
        return None
    try:
        moment = datetime.fromisoformat(updated_since.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="updated_since doit être une date ISO 8601.",
        )
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat()
