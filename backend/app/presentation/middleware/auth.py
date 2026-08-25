"""Middleware d'authentification minimal pour TÂCHE 5.

Vérifie le header `Authorization: Bearer <token>` sur les routes `/api/*`.

Le token est lu depuis ``settings.AUTH_TOKEN`` (env ``CAHIER_AUTH_TOKEN``).
Si le token est vide, l'auth est désactivée (mode dev local).

NOTE: On retourne une JSONResponse plutôt que lever HTTPException :
une exception levée dans un BaseHTTPMiddleware contourne les handlers
FastAPI et produirait un 500 côté serveur.
"""

from typing import Optional

import hmac
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from backend.app.config import settings


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware qui exige un token Bearer statique pour accéder aux routes `/api/*`."""

    def __init__(self, app, auth_token: Optional[str] = None):
        super().__init__(app)
        self.auth_token = auth_token if auth_token is not None else settings.AUTH_TOKEN

    async def dispatch(self, request: Request, call_next):
        if self.auth_token and request.url.path.startswith("/api/"):
            expected = f"Bearer {self.auth_token}"
            # compare_digest : comparaison à temps constant (anti timing-attack)
            if not hmac.compare_digest(
                request.headers.get("Authorization", ""), expected
            ):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized — token manquant ou invalide"},
                )
        return await call_next(request)
