"""Scénarios d'intégration : routes + services + dépôts + vraie base SQLite.

Ils rejouent ce que font les téléphones : envois avec identifiants, renvois
après coupure, deux téléphones qui se synchronisent par curseur, et une suite
d'opérations aléatoires après chacune desquelles les soldes doivent rester
exacts.
"""

import random
import time
from decimal import Decimal

import pytest


def dec(value) -> Decimal:
    return Decimal(str(value))


# --- Aides : ce que fait un téléphone ---------------------------------------
class Phone:
    """Un téléphone : envoie des créations et lit par curseur."""

    def __init__(self, client):
        self.client = client
        self.cursors = {}
        self.local = {"customers": {}, "credits": {}, "payments": {}}

    def push(self, resource, body):
        return self.client.post(f"/api/{resource}/", json=body)

    def pull(self):
        """Lecture incrémentale de toutes les ressources, comme l'app."""
        received = {}
        for resource in ("customers", "credits", "payments"):
            params = {"page_size": 200}
            if resource in self.cursors:
                params["updated_since"] = self.cursors[resource]
            rows = self.client.get(f"/api/{resource}/", params=params).json()[resource]
            received[resource] = [r["id"] for r in rows]
            for row in rows:
                self.local[resource][row["id"]] = row
            if rows:
                self.cursors[resource] = max(r["updated_at"] for r in rows)
        return received


def make_world(client):
    """Un client, un crédit de 5000 et deux paiements, via l'API."""
    cid = client.post("/api/customers/", json={"name": "Awa"}).json()["id"]
    kid = client.post("/api/credits/", json={"customer_id": cid, "amount": 5000}).json()["id"]
    return cid, kid


def pay(client, cid, kid, amount):
    r = client.post("/api/payments/",
                    json={"customer_id": cid, "credit_id": kid, "amount": amount})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
class TestPhoneRoundTrip:
    def test_resending_everything_after_a_cut_creates_no_duplicate(self, client):
        phone = Phone(client)
        bodies = [
            ("customers", {"id": "cust-1", "name": "Awa"}),
            ("credits", {"id": "cred-1", "customer_id": "cust-1", "amount": 5000}),
            ("payments", {"id": "pay-1", "customer_id": "cust-1", "credit_id": "cred-1",
                          "amount": 2000}),
        ]

        for _ in range(3):  # la connexion a sauté : le téléphone renvoie tout
            for resource, body in bodies:
                assert phone.push(resource, body).status_code == 201

        assert client.get("/api/customers/").json()["total"] == 1
        assert client.get("/api/credits/").json()["total"] == 1
        assert client.get("/api/payments/").json()["total"] == 1
        customer = client.get("/api/customers/cust-1").json()
        assert (dec(customer["total_credit"]), dec(customer["total_paid"])) == (5000, 2000)

    def test_a_refused_item_does_not_prevent_the_next_ones(self, client):
        phone = Phone(client)
        assert phone.push("customers", {"id": "c1", "name": "Awa"}).status_code == 201

        bad = phone.push("credits", {"id": "k0", "customer_id": "c1", "amount": -5})
        good = phone.push("credits", {"id": "k1", "customer_id": "c1", "amount": 3000})

        assert bad.status_code == 422  # permanent : le téléphone le met de côté
        assert good.status_code == 201

    def test_payment_before_its_credit_is_refused_then_accepted_in_order(self, client):
        phone = Phone(client)
        phone.push("customers", {"id": "c1", "name": "Awa"})
        payment = {"id": "p1", "customer_id": "c1", "credit_id": "k1", "amount": 100}

        too_early = phone.push("payments", payment)
        phone.push("credits", {"id": "k1", "customer_id": "c1", "amount": 1000})
        in_order = phone.push("payments", payment)

        assert too_early.status_code == 400
        assert in_order.status_code == 201


class TestTwoPhonesIncrementalSync:
    def test_second_phone_gets_only_what_changed(self, client):
        a, b = Phone(client), Phone(client)
        a.push("customers", {"id": "c1", "name": "Awa"})
        a.push("credits", {"id": "k1", "customer_id": "c1", "amount": 5000})

        first = b.pull()
        assert first["customers"] == ["c1"] and first["credits"] == ["k1"]

        time.sleep(0.02)
        a.push("customers", {"id": "c2", "name": "Moussa"})
        second = b.pull()

        # Le nouveau arrive. Le crédit, inchangé, ne revient pas en liste
        # complète : au plus la borne du curseur (inclusive, pour ne jamais
        # rater une modification simultanée).
        assert "c2" in second["customers"]
        assert len(second["credits"]) <= 1

    def test_a_payment_makes_the_credit_travel_again_with_its_new_status(self, client):
        a, b = Phone(client), Phone(client)
        a.push("customers", {"id": "c1", "name": "Awa"})
        a.push("credits", {"id": "k1", "customer_id": "c1", "amount": 5000})
        b.pull()
        assert b.local["credits"]["k1"]["status"] == "pending"

        time.sleep(0.02)
        a.push("payments", {"id": "p1", "customer_id": "c1", "credit_id": "k1", "amount": 5000})
        received = b.pull()

        assert "k1" in received["credits"]
        assert b.local["credits"]["k1"]["status"] == "paid"
        assert received["payments"] == ["p1"]

    def test_an_edit_made_elsewhere_reaches_the_other_phone(self, client):
        a, b = Phone(client), Phone(client)
        a.push("customers", {"id": "c1", "name": "Awa"})
        b.pull()

        time.sleep(0.02)
        client.put("/api/customers/c1", json={"name": "Awa Ouédraogo"})
        received = b.pull()

        assert received["customers"] == ["c1"]
        assert b.local["customers"]["c1"]["name"] == "Awa Ouédraogo"

    def test_a_phone_that_pulls_twice_in_a_row_gets_a_stable_small_answer(self, client):
        a, b = Phone(client), Phone(client)
        for i in range(5):
            a.push("customers", {"id": f"c{i}", "name": f"C{i}"})
        b.pull()

        again = b.pull()

        # Seule la borne (inclusive) peut revenir : jamais toute la liste.
        assert len(again["customers"]) <= 1

    def test_pages_are_walked_without_gap_or_duplicate(self, client):
        a = Phone(client)
        for i in range(7):
            a.push("customers", {"id": f"c{i}", "name": f"C{i}"})
        seen = []
        for page in (1, 2, 3, 4):
            body = client.get("/api/customers/", params={
                "updated_since": "2000-01-01", "page": page, "page_size": 2}).json()
            seen += [c["id"] for c in body["customers"]]

        assert sorted(seen) == [f"c{i}" for i in range(7)]


class TestLifecycle:
    def test_edit_and_delete_payments_keep_balances_right(self, client):
        cid, kid = make_world(client)
        p1 = pay(client, cid, kid, 2000)
        p2 = pay(client, cid, kid, 3000)
        assert client.get(f"/api/credits/{kid}").json()["status"] == "paid"

        client.put(f"/api/payments/{p2}", json={"amount": 1000})
        assert client.get(f"/api/credits/{kid}").json()["status"] == "partial"
        assert dec(client.get(f"/api/customers/{cid}").json()["total_paid"]) == 3000

        client.delete(f"/api/payments/{p1}")
        client.delete(f"/api/payments/{p2}")
        assert client.get(f"/api/credits/{kid}").json()["status"] == "pending"
        assert dec(client.get(f"/api/customers/{cid}").json()["total_paid"]) == 0

    def test_cancel_then_delete_a_credit_without_payments(self, client):
        cid, kid = make_world(client)

        client.put(f"/api/credits/{kid}", json={"status": "cancelled"})
        assert dec(client.get(f"/api/customers/{cid}").json()["total_credit"]) == 0

        assert client.delete(f"/api/credits/{kid}").status_code == 204
        assert dec(client.get(f"/api/customers/{cid}").json()["total_credit"]) == 0

    def test_credit_with_payments_cannot_be_deleted_but_can_be_cancelled(self, client):
        cid, kid = make_world(client)
        pay(client, cid, kid, 1000)

        assert client.delete(f"/api/credits/{kid}").status_code == 409
        assert client.put(f"/api/credits/{kid}", json={"status": "cancelled"}).status_code == 200

        customer = client.get(f"/api/customers/{cid}").json()
        assert dec(customer["total_credit"]) == 0
        assert dec(customer["total_paid"]) == 1000  # le paiement reste tracé

    def test_journal_records_credit_and_payment(self, client):
        cid, kid = make_world(client)
        pay(client, cid, kid, 1000)

        entries = client.get(f"/api/transactions/customer/{cid}").json()

        assert sorted(e["type"] for e in entries) == ["credit", "payment"]


# ---------------------------------------------------------------------------
# Propriété : quoi qu'on fasse, les soldes restent exacts
# ---------------------------------------------------------------------------
class TestBalancesStayExact:
    @pytest.mark.parametrize("seed", [1, 7, 42])
    def test_random_operations(self, client, seed):
        rng = random.Random(seed)
        cid = client.post("/api/customers/", json={"name": "Awa"}).json()["id"]

        def credits():
            return client.get(f"/api/credits/customer/{cid}").json()

        def payments():
            return client.get(f"/api/payments/customer/{cid}").json()

        def check(step):
            customer = client.get(f"/api/customers/{cid}").json()
            cr, pa = credits(), payments()
            assert dec(customer["total_credit"]) == sum(
                (dec(c["amount"]) for c in cr if c["status"] != "cancelled"), Decimal(0)
            ), step
            assert dec(customer["total_paid"]) == sum(
                (dec(p["amount"]) for p in pa), Decimal(0)
            ), step
            paid_by_credit = {}
            for p in pa:
                paid_by_credit[p["credit_id"]] = (
                    paid_by_credit.get(p["credit_id"], 0) + dec(p["amount"]))
            for c in cr:
                if c["status"] == "cancelled":
                    continue
                paid = paid_by_credit.get(c["id"], Decimal(0))
                expected = ("paid" if paid >= dec(c["amount"])
                            else "partial" if paid > 0 else "pending")
                assert c["status"] == expected, (step, c["id"])

        for step in range(60):
            action = rng.choice(
                ["credit", "credit", "pay", "pay", "edit_payment", "delete_payment",
                 "cancel", "delete_credit", "edit_credit"]
            )
            cr, pa = credits(), payments()
            open_credits = [c for c in cr if c["status"] not in ("cancelled", "paid")]
            label = f"{seed}/{step}/{action}"

            if action == "credit":
                r = client.post("/api/credits/", json={
                    "customer_id": cid, "amount": rng.randint(100, 9000)})
                assert r.status_code == 201
            elif action == "pay" and open_credits:
                c = rng.choice(open_credits)
                paid = sum(dec(p["amount"]) for p in pa if p["credit_id"] == c["id"])
                left = int(dec(c["amount"]) - paid)
                if left > 0:
                    pay(client, cid, c["id"], rng.randint(1, left))
            elif action == "edit_payment" and pa:
                p = rng.choice(pa)
                r = client.put(f"/api/payments/{p['id']}", json={"amount": rng.randint(1, 9000)})
                assert r.status_code == 200
            elif action == "delete_payment" and pa:
                assert client.delete(f"/api/payments/{rng.choice(pa)['id']}").status_code == 204
            elif action == "cancel" and cr:
                c = rng.choice(cr)
                if c["status"] != "cancelled":
                    client.put(f"/api/credits/{c['id']}", json={"status": "cancelled"})
            elif action == "delete_credit" and cr:
                c = rng.choice(cr)
                has_payments = any(p["credit_id"] == c["id"] for p in pa)
                r = client.delete(f"/api/credits/{c['id']}")
                assert r.status_code == (409 if has_payments else 204), label
            elif action == "edit_credit" and cr:
                c = rng.choice(cr)
                if c["status"] != "cancelled":
                    r = client.put(f"/api/credits/{c['id']}",
                                   json={"amount": rng.randint(100, 9000)})
                    assert r.status_code == 200

            check(label)
