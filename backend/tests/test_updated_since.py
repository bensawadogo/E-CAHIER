"""Lecture incrémentale : ?updated_since= sur clients, crédits et paiements.

Sur une connexion faible, l'app ne doit pas retélécharger toute la base à
chaque synchronisation : elle redemande seulement ce qui a changé.
"""

import time
from datetime import datetime, timezone

import pytest


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _create_customer(client, name="Awa"):
    r = client.post("/api/customers/", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def _create_credit(client, customer_id, amount="5000"):
    r = client.post("/api/credits/", json={"customer_id": customer_id, "amount": amount})
    assert r.status_code == 201, r.text
    return r.json()


def _pay(client, customer_id, credit_id, amount="2000"):
    r = client.post(
        "/api/payments/",
        json={"customer_id": customer_id, "credit_id": credit_id, "amount": amount},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _ids(body, key):
    return [row["id"] for row in body[key]]


@pytest.mark.parametrize("resource", ["customers", "credits", "payments"])
def test_without_param_nothing_changes(client, resource):
    c = _create_customer(client)
    cr = _create_credit(client, c["id"])
    _pay(client, c["id"], cr["id"])
    body = client.get(f"/api/{resource}/").json()
    assert body["total"] == 1


def test_only_changed_records_come_back(client):
    old = _create_customer(client, "Ancien")
    time.sleep(0.01)
    cursor = _now()
    time.sleep(0.01)
    new = _create_customer(client, "Nouveau")

    body = client.get("/api/customers/", params={"updated_since": cursor}).json()

    assert _ids(body, "customers") == [new["id"]]
    assert body["total"] == 1
    # Sans filtre : les deux.
    full = client.get("/api/customers/").json()
    assert {old["id"], new["id"]} == set(_ids(full, "customers"))


def test_credit_touched_by_a_payment_comes_back(client):
    """Un paiement change le statut du crédit : l'app doit le recevoir."""
    c = _create_customer(client)
    cr = _create_credit(client, c["id"])
    time.sleep(0.01)
    cursor = _now()
    time.sleep(0.01)
    pay = _pay(client, c["id"], cr["id"])

    credits = client.get("/api/credits/", params={"updated_since": cursor}).json()
    payments = client.get("/api/payments/", params={"updated_since": cursor}).json()

    assert _ids(credits, "credits") == [cr["id"]]
    assert credits["credits"][0]["status"] == "partial"
    assert _ids(payments, "payments") == [pay["id"]]


def test_boundary_is_inclusive(client):
    """>= : un enregistrement modifié à l'instant exact du curseur n'est pas perdu."""
    c = _create_customer(client)
    body = client.get(
        "/api/customers/", params={"updated_since": c["updated_at"]}
    ).json()
    assert c["id"] in _ids(body, "customers")


def test_future_cursor_returns_nothing(client):
    _create_customer(client)
    body = client.get(
        "/api/customers/", params={"updated_since": "2999-01-01T00:00:00+00:00"}
    ).json()
    assert body["customers"] == [] and body["total"] == 0


def test_pagination_is_stable(client):
    """Tri par date de modification puis id : pas de doublon ni de trou entre pages."""
    cursor = "2000-01-01T00:00:00+00:00"
    made = {_create_customer(client, f"C{i}")["id"] for i in range(5)}

    seen = []
    for page in (1, 2, 3):
        body = client.get(
            "/api/customers/",
            params={"updated_since": cursor, "page": page, "page_size": 2},
        ).json()
        seen += _ids(body, "customers")

    assert len(seen) == len(set(seen)) == 5
    assert set(seen) == made


def test_accepts_z_suffix_and_naive_dates(client):
    c = _create_customer(client)
    for value in ("2000-01-01T00:00:00Z", "2000-01-01T00:00:00", "2000-01-01"):
        body = client.get("/api/customers/", params={"updated_since": value}).json()
        assert c["id"] in _ids(body, "customers"), value


@pytest.mark.parametrize("resource", ["customers", "credits", "payments"])
def test_invalid_date_is_422(client, resource):
    r = client.get(f"/api/{resource}/", params={"updated_since": "pas-une-date"})
    assert r.status_code == 422
