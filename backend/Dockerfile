# Ecahier API — image de déploiement (Render / Railway)
# Contexte Burkina Faso : SQLite offline-first + compression.
FROM python:3.11-slim

# Pas de .pyc ni buffering (logs temps réel dans Render)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 1) Dépendances d'abord (cache Docker)
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 2) Code applicatif
COPY backend/app /app/backend/app
COPY backend/scripts /app/backend/scripts

# Port attendu par la plateforme (Render déploie $PORT=10000, Railway $PORT=8080)
EXPOSE $PORT

# Le host 0.0.0.0 est OBLIGATOIRE pour recevoir le trafic public.
CMD python -m uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-10000}