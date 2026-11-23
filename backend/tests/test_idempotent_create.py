"""Création idempotente : l'app mobile génère les ID hors ligne et peut renvoyer
la même requête après une coupure sans créer de doublon ni compter deux fois
un crédit ou un paiement."""

from decimal import Decimal


def _customer(client, **extra):
    payload = {"name": "Awa", "phone": "70000000", **extra}
    return client.post("/api/customers/", json=payload)


def _credit(client, customer_id, amount="5000", **extra):
    payload = {"customer_id": customer_id, "amount": amount, **extra}
    return client.post("/api/credits/", json=payload)


def _pay(client, customer_id, credit_id, amount="2000", **extra):
    payload = {
        "customer_id": customer_id,
        "credit_id": credit_id,
        "amount": amount,
        **extra,
    }
    return client.post("/api/payments/", json=payload)


# --- clients -------------------------------------------------------------

def test_customer_keeps_client_generated_id(client):
    r = _customer(client, id="3f2b8c1e-aaaa-4bbb-8ccc-0123456789ab")
    assert r.status_code == 201
    assert r.json()["id"] == "3f2b8c1e-aaaa-4bbb-8ccc-0123456789ab"


def test_customer_resend_does_not_duplicate(client):
    first = _customer(client, id="cust-1")
    second = _customer(client, id="cust-1")
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"] == "cust-1"
    assert client.get("/api/customers/").json()["total"] == 1


def test_customer_without_id_still_gets_server_uuid(client):
    r = _customer(client)
    assert r.status_code == 201
    assert len(r.json()["id"]) == 36


def test_customer_rejects_unsafe_id(client):
    r = _customer(client, id="a b/../c")
    assert r.status_code == 422


# --- crédits -------------------------------------------------------------

def test_credit_resend_does_not_double_the_debt(client):
    cid = _customer(client, id="cust-1").json()["id"]
    first = _credit(client, cid, id="cred-1")
    second = _credit(client, cid, id="cred-1")
    assert first.status_code == second.status_code == 201
    assert second.json()["id"] == "cred-1"
    assert client.get("/api/credits/").json()["total"] == 1
    customer = client.get(f"/api/customers/{cid}").json()
    assert Decimal(customer["total_credit"]) == Decimal("5000")


def test_credit_id_reused_for_another_customer_is_rejected(client):
    a = _customer(client, id="cust-a").json()["id"]
    b = _customer(client, id="cust-b").json()["id"]
    assert _credit(client, a, id="cred-1").status_code == 201
    r = _credit(client, b, id="cred-1")
    assert r.status_code == 400


# --- paiements -----------------------------------------------------------

def test_payment_resend_is_counted_once(client):
    cid = _customer(client, id="cust-1").json()["id"]
    credit = _credit(client, cid, id="cred-1").json()["id"]
    first = _pay(client, cid, credit, id="pay-1")
    second = _pay(client, cid, credit, id="pay-1")
    assert first.status_code == second.status_code == 201
    assert client.get("/api/payments/").json()["total"] == 1
    customer = client.get(f"/api/customers/{cid}").json()
    assert Decimal(customer["total_paid"]) == Decimal("2000")


def test_payment_for_credit_of_another_customer_is_rejected(client):
    a = _customer(client, id="cust-a").json()["id"]
    b = _customer(client, id="cust-b").json()["id"]
    credit = _credit(client, a, id="cred-1").json()["id"]
    r = _pay(client, b, credit)
    assert r.status_code == 400
    assert client.get("/api/payments/").json()["total"] == 0


# --- /status/commits -----------------------------------------------------

def test_status_commits_limit_is_bounded(client):
    assert client.get("/status/commits?limit=0").status_code == 422
    assert client.get("/status/commits?limit=100000").status_code == 422
    assert client.get("/status/commits?limit=3").status_code == 200
