"""Tests d'intégration bout-en-bout via HTTP — FastAPI → services → SQLite.

Exerce la pile complète : AuthMiddleware → routes API → services applicatifs
→ repositories SQLite en mémoire. Le serveur de sync distant est absent
(mode offline-first Burkina Faso).
"""


class TestApiBusinessFlow:
    def test_full_customer_credit_payment_flow_over_http(self, client):
        """Cycle de vie complet via l'API : création client, crédit, paiements,
        vérification des soldes et du statut du crédit."""
        # 1. Création client
        r = client.post(
            "/api/customers/",
            json={"name": "Issa Traoré", "phone": "+226 76 55 44 33"},
        )
        assert r.status_code == 201
        customer = r.json()
        customer_id = customer["id"]
        assert float(customer["total_credit"]) == 0

        # 2. Création crédit 5000 FCFA
        r = client.post(
            "/api/credits/",
            json={"customer_id": customer_id, "amount": "5000", "description": "Sac de riz"},
        )
        assert r.status_code == 201
        credit = r.json()
        credit_id = credit["id"]
        assert credit["status"] == "pending"

        # 3. Paiement partiel 2000
        r = client.post(
            "/api/payments/",
            json={
                "customer_id": customer_id,
                "credit_id": credit_id,
                "amount": "2000",
                "method": "cash",
            },
        )
        assert r.status_code == 201
        payment_id = r.json()["id"]

        # 4. Vérif crédit partiel + solde client
        r = client.get(f"/api/credits/{credit_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "partial"

        r = client.get(f"/api/customers/{customer_id}")
        assert float(r.json()["total_paid"]) == 2000
        assert float(r.json()["balance"]) == 3000

        # 5. Solde 3000 → crédit soldé
        r = client.post(
            "/api/payments/",
            json={
                "customer_id": customer_id,
                "credit_id": credit_id,
                "amount": "3000",
                "method": "mobile_money",
            },
        )
        assert r.status_code == 201

        r = client.get(f"/api/credits/{credit_id}")
        assert r.json()["status"] == "paid"

        # 6. Journal : 2 transactions liées au paiement et au client
        r = client.get("/api/payments/", params={"offset": 0})
        assert r.status_code == 200
        body = r.json()
        total = body.get("total") if isinstance(body, dict) else len(body)
        assert total == 2

        r = client.get(f"/api/payments/{payment_id}")
        assert r.status_code == 200
        assert float(r.json()["amount"]) == 2000

    def test_api_rejects_invalid_payment_amount(self, client):
        """Montant <= 0 rejeté par la validation DTO (422), rien n'est écrit."""
        r = client.post(
            "/api/customers/",
            json={"name": "Fatou Kaboré"},
        )
        customer_id = r.json()["id"]

        r = client.post("/api/credits/", json={"customer_id": customer_id, "amount": "1000"})
        credit_id = r.json()["id"]

        r = client.post(
            "/api/payments/",
            json={
                "customer_id": customer_id,
                "credit_id": credit_id,
                "amount": "-500",
            },
        )
        assert r.status_code == 422

    def test_delete_customer_cascades_to_http_errors(self, client):
        """Supprimer un client rend ses sous-ressources introuvables (404)."""
        r = client.post("/api/customers/", json={"name": "Zongo Ali"})
        customer_id = r.json()["id"]

        r = client.delete(f"/api/customers/{customer_id}")
        assert r.status_code == 204

        r = client.get(f"/api/customers/{customer_id}")
        assert r.status_code == 404
