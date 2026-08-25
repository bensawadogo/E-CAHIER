"""Tests de l'API transactions (journal des opérations) via HTTP."""

from decimal import Decimal


class TestTransactionsAPI:
    def _seed_one_payment(self, client) -> tuple[str, str]:
        """Crée client + crédit + paiement ; retourne (customer_id, credit_id)."""
        r = client.post("/api/customers/", json={"name": "Client Journal"})
        customer_id = r.json()["id"]
        r = client.post(
            "/api/credits/",
            json={"customer_id": customer_id, "amount": "1000"},
        )
        credit_id = r.json()["id"]
        r = client.post(
            "/api/payments/",
            json={
                "customer_id": customer_id,
                "credit_id": credit_id,
                "amount": "400",
                "method": "cash",
            },
        )
        assert r.status_code == 201
        return customer_id, credit_id

    def test_list_transactions_returns_journal_with_total(self, client):
        self._seed_one_payment(client)

        r = client.get("/api/transactions/")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 2  # 1 crédit + 1 paiement
        assert body["page"] == 1
        types = {t["type"] for t in body["transactions"]}
        assert {"credit", "payment"} <= types

    def test_list_transactions_pagination(self, client):
        self._seed_one_payment(client)

        r = client.get("/api/transactions/", params={"page": 1, "page_size": 1})
        assert r.status_code == 200
        assert len(r.json()["transactions"]) == 1
        assert r.json()["total"] >= 2

    def test_list_transactions_invalid_page_rejected(self, client):
        """page < 1 rejeté par la validation Query (422)."""
        r = client.get("/api/transactions/", params={"page": 0})
        assert r.status_code == 422

    def test_customer_transactions_after_flow(self, client):
        customer_id, _ = self._seed_one_payment(client)

        r = client.get(f"/api/transactions/customer/{customer_id}")
        assert r.status_code == 200
        entries = r.json()
        assert len(entries) == 2
        assert all(t["customer_id"] == customer_id for t in entries)
        amounts = sorted(float(t["amount"]) for t in entries)
        assert amounts == [400.0, 1000.0]

    def test_customer_transactions_empty_for_unknown_customer(self, client):
        r = client.get("/api/transactions/customer/inconnu-123")
        assert r.status_code == 200
        assert r.json() == []

    def test_transaction_payload_shape(self, client):
        """Le journal expose payment_id / balance_after correctement liés."""
        customer_id, _ = self._seed_one_payment(client)
        entries = client.get(f"/api/transactions/customer/{customer_id}").json()
        payments = [t for t in entries if t["type"] == "payment"]

        assert len(payments) == 1
        assert payments[0]["payment_id"]
        # balance_after = dette restante (total_credit - total_paid) = 600 FCFA
        assert float(payments[0]["balance_after"]) == Decimal("1000") - Decimal("400")
