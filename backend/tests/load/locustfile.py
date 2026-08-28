"""Ecahier — Test de charge Locust pour l'API FastAPI + SQLite.

Scénario réaliste (offline-first, 1 terminal par boutique) :
  - LECTURE ~80% (dashboard, listes clients/crédits/paiements, recherche)
  - ÉCRITURE ~20% (créer client, crédit, paiement)

Usage :
  pip install locust
  locust -f backend/tests/load/locustfile.py --host http://127.0.0.1:8000
Puis ouvrir http://localhost:8089 (Web UI), ou mode headless :
  locust -f backend/tests/load/locustfile.py --host http://127.0.0.1:8000 \
        --headless -u 50 -r 5 -t 3m --csv backend/tests/load/results/load

Auth : si l'API exige un token Bearer (CAHIER_AUTH_TOKEN), définir
LOCUST_AUTH_TOKEN avant de lancer.
"""

import os
import random
import threading
from decimal import Decimal

from locust import HttpUser, between, task

# Token Bearer optionnel (aligné sur CAHIER_AUTH_TOKEN du backend)
AUTH_TOKEN = os.getenv("LOCUST_AUTH_TOKEN", "")

# Pool global d'IDs clients, partagé entre les users (pour les écritures)
_CUSTOMER_POOL = []
_CUSTOMER_LOCK = threading.Lock()
_METHODS = ["cash", "mobile_money", "bank_transfer", "other"]


def _auth_headers():
    h = {"Content-Type": "application/json"}
    if AUTH_TOKEN:
        h["Authorization"] = f"Bearer {AUTH_TOKEN}"
    return h


def _add_to_pool(cid):
    if cid:
        with _CUSTOMER_LOCK:
            _CUSTOMER_POOL.append(cid)
            if len(_CUSTOMER_POOL) > 500:
                _CUSTOMER_POOL.pop(0)


class EcahierUser(HttpUser):
    """Simule 1 terminal boutique : lit souvent, écrit parfois."""

    wait_time = between(0.5, 4.0)

    def on_start(self):
        # Chaque user crée 1-2 clients réels pour alimenter les écritures
        for _ in range(random.randint(1, 2)):
            self._create_customer()

    def _create_customer(self):
        payload = {
            "name": f"Boutiq-{random.randint(1000, 9999)}",
            "phone": "7" + str(random.randint(10000000, 99999999)),
        }
        r = self.client.post(
            "/api/customers/", json=payload, headers=_auth_headers(),
            name="POST /customers",
        )
        if r.status_code == 201:
            _add_to_pool(r.json().get("id"))

    def _random_customer(self):
        with _CUSTOMER_LOCK:
            return random.choice(_CUSTOMER_POOL) if _CUSTOMER_POOL else None

    # ---------- LECTURES (l'essentiel du trafic) ----------
    @task(8)
    def list_customers(self):
        self.client.get("/api/customers/", headers=_auth_headers(), name="GET /customers")

    @task(6)
    def list_credits(self):
        self.client.get("/api/credits/", headers=_auth_headers(), name="GET /credits")

    @task(4)
    def list_payments(self):
        self.client.get("/api/payments/", headers=_auth_headers(), name="GET /payments")

    @task(4)
    def dashboard(self):
        self.client.get(
            "/api/customers/?active_only=true", headers=_auth_headers(),
            name="GET /customers active",
        )

    @task(3)
    def search_customers(self):
        self.client.get(
            "/api/customers/search/Boutiq", headers=_auth_headers(),
            name="GET /customers/search",
        )

    @task(4)
    def sync_status(self):
        self.client.get("/api/sync/status", headers=_auth_headers(), name="GET /sync/status")

    @task(2)
    def transactions(self):
        self.client.get("/api/transactions/", headers=_auth_headers(), name="GET /transactions")

    # ---------- ÉCRITURES (minorité) ----------
    @task(2)
    def create_customer(self):
        self._create_customer()

    @task(2)
    def create_credit(self):
        cid = self._random_customer()
        if not cid:
            self._create_customer()
            return
        payload = {"customer_id": cid, "amount": random.randint(1000, 50000),
                   "description": "Marchandises"}
        self.client.post("/api/credits/", json=payload, headers=_auth_headers(), name="POST /credits")

    @task(2)
    def create_payment_flow(self):
        cid = self._random_customer()
        if not cid:
            self._create_customer()
            return
        # créer un crédit puis le payer
        credit_payload = {"customer_id": cid, "amount": 10000, "description": "Paiement test"}
        r = self.client.post(
            "/api/credits/", json=credit_payload, headers=_auth_headers(),
            name="POST /credits",
        )
        if r.status_code != 201:
            return
        credit_id = r.json().get("id")
        pay_payload = {
            "customer_id": cid, "credit_id": credit_id, "amount": 5000,
            "method": random.choice(_METHODS), "reference": f"ref-{random.randint(1, 99999)}",
        }
        self.client.post("/api/payments/", json=pay_payload, headers=_auth_headers(), name="POST /payments")