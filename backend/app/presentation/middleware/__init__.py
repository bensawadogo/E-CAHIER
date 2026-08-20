"""Ecahier - Middleware (CORS, logging, error handling)."""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware de logging des requêtes (pour debug et monitoring)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "%s %s - %d - %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


def setup_middleware(app) -> None:
    """Configure tous les middleware sur l'app FastAPI."""
    # CORS — autorise les origines du frontend Flutter
    # NOTE: En production, remplacer "*" par la liste des domaines autorisés (ex: ["https://monapp.com"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Compression gzip — réduit la bande passante (critique en 2G/3G)
    # minimum_size=500 : ne compresse que les réponses utiles (>500 octets)
    app.add_middleware(GZipMiddleware, minimum_size=500)
    # Logging des requêtes
    app.add_middleware(LoggingMiddleware)


__all__ = ["LoggingMiddleware", "setup_middleware"]