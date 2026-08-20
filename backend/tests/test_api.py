"""API integration tests for the FastAPI backend.

These tests use the ``client`` fixture from ``conftest.py`` which wires every
service to a fresh in-memory SQLite database, so the real ``data/`` database is
never touched and tests are fully hermetic and repeatable.
"""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["app"] == "Ecahier API"


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["app"] == "Ecahier API"
    assert "/docs" in body["docs"]


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
def test_create_customer(client):
    r = client.post("/api/customers/", json={"name": "Test Client", "phone": "+226 70 00 00 00"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Test Client"
    assert body["balance"] == "0.0"
    assert body["is_active"] is True
    assert body["sync_status"] == "pending"


def test_create_customer_validation_error(client):
    r = client.post("/api/customers/", json={"name": "  "})
    assert r.status_code == 422


def test_create_customer_invalid_name_via_api(client):
    # Empty name after strip → 422 from the DTO validator.
    r = client.post("/api/customers/", json={"name": "   ", "phone": ""})
    assert r.status_code == 422


def test_list_customers(client):
    client.post("/api/customers/", json={"name": "Awa"})
    client.post("/api/customers/", json={"name": "Alima"})
    r = client.get("/api/customers/")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert len(body["customers"]) == 2


def test_list_customers_active_only(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    client.post("/api/customers/", json={"name": "Inactive"})

    # Deactivate the first customer
    r = client.put(f"/api/customers/{customer_id}", json={"is_active": False})
    assert r.status_code == 200

    r = client.get("/api/customers/?active_only=true")
    body = r.json()
    assert body["total"] == 1
    assert body["customers"][0]["name"] == "Inactive"


def test_get_customer(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa", "phone": "+226 70 11 22 33"}
    ).json()["id"]
    r = client.get(f"/api/customers/{customer_id}")
    assert r.status_code == 200
    assert r.json()["phone"] == "+226 70 11 22 33"


def test_get_customer_not_found(client):
    r = client.get("/api/customers/does-not-exist")
    assert r.status_code == 404


def test_update_customer(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    r = client.put(f"/api/customers/{customer_id}", json={"name": "Awa B"})
    assert r.status_code == 200
    assert r.json()["name"] == "Awa B"


def test_update_customer_not_found(client):
    r = client.put("/api/customers/does-not-exist", json={"name": "X"})
    assert r.status_code == 404


def test_delete_customer(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    r = client.delete(f"/api/customers/{customer_id}")
    assert r.status_code == 204
    # Verify it's gone
    assert client.get(f"/api/customers/{customer_id}").status_code == 404


def test_search_customers(client):
    client.post("/api/customers/", json={"name": "Awa Ouédraogo"})
    client.post("/api/customers/", json={"name": "Alima Sawadogo"})
    r = client.get("/api/customers/search/alima")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "Alima Sawadogo"


# ---------------------------------------------------------------------------
# Credits
# ---------------------------------------------------------------------------
def test_create_credit(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    r = client.post(
        "/api/credits/",
        json={"customer_id": customer_id, "amount": 5000, "description": "Marchandises"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["amount"] == "5000"
    assert body["status"] == "pending"
    assert body["customer_id"] == customer_id


def test_create_credit_customer_not_found(client):
    r = client.post(
        "/api/credits/", json={"customer_id": "missing", "amount": 5000}
    )
    assert r.status_code == 400


def test_create_credit_invalid_amount(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    r = client.post("/api/credits/", json={"customer_id": customer_id, "amount": 0})
    assert r.status_code == 422


def test_list_credits(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    client.post("/api/credits/", json={"customer_id": customer_id, "amount": 5000})
    client.post("/api/credits/", json={"customer_id": customer_id, "amount": 3000})
    r = client.get("/api/credits/")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert len(body["credits"]) == 2


def test_list_credits_pending_only(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    credit_id = client.post(
        "/api/credits/", json={"customer_id": customer_id, "amount": 5000}
    ).json()["id"]

    # Pay fully → status becomes paid
    client.post(
        "/api/payments/",
        json={"customer_id": customer_id, "credit_id": credit_id, "amount": 5000, "method": "cash"},
    )

    r = client.get("/api/credits/?pending_only=true")
    body = r.json()
    assert body["total"] == 0


def test_get_customer_credits(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    client.post("/api/credits/", json={"customer_id": customer_id, "amount": 5000})
    r = client.get(f"/api/credits/customer/{customer_id}")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_get_credit(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    credit_id = client.post(
        "/api/credits/", json={"customer_id": customer_id, "amount": 5000}
    ).json()["id"]
    r = client.get(f"/api/credits/{credit_id}")
    assert r.status_code == 200
    assert r.json()["amount"] == "5000"


def test_get_credit_not_found(client):
    r = client.get("/api/credits/does-not-exist")
    assert r.status_code == 404


def test_update_credit(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    credit_id = client.post(
        "/api/credits/", json={"customer_id": customer_id, "amount": 5000}
    ).json()["id"]
    r = client.put(f"/api/credits/{credit_id}", json={"status": "cancelled"})
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_delete_credit(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    credit_id = client.post(
        "/api/credits/", json={"customer_id": customer_id, "amount": 5000}
    ).json()["id"]
    r = client.delete(f"/api/credits/{credit_id}")
    assert r.status_code == 204
    assert client.get(f"/api/credits/{credit_id}").status_code == 404


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
def test_record_payment(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    credit_id = client.post(
        "/api/credits/", json={"customer_id": customer_id, "amount": 5000}
    ).json()["id"]

    r = client.post(
        "/api/payments/",
        json={
            "customer_id": customer_id,
            "credit_id": credit_id,
            "amount": 2000,
            "method": "cash",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["amount"] == "2000"
    assert body["method"] == "cash"

    # Credit should now be partial
    r = client.get(f"/api/credits/{credit_id}")
    assert r.json()["status"] == "partial"


def test_record_payment_full_marks_credit_paid(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    credit_id = client.post(
        "/api/credits/", json={"customer_id": customer_id, "amount": 5000}
    ).json()["id"]

    r = client.post(
        "/api/payments/",
        json={
            "customer_id": customer_id,
            "credit_id": credit_id,
            "amount": 5000,
            "method": "mobile_money",
            "reference": "REF-001",
        },
    )
    assert r.status_code == 201

    credit = client.get(f"/api/credits/{credit_id}").json()
    assert credit["status"] == "paid"
    # Customer balance should be 0
    customer = client.get(f"/api/customers/{customer_id}").json()
    assert customer["balance"] == "0.0"


def test_record_payment_customer_not_found(client):
    r = client.post(
        "/api/payments/",
        json={"customer_id": "missing", "credit_id": "x", "amount": 100, "method": "cash"},
    )
    assert r.status_code == 400


def test_record_payment_credit_not_found(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    r = client.post(
        "/api/payments/",
        json={"customer_id": customer_id, "credit_id": "x", "amount": 100, "method": "cash"},
    )
    assert r.status_code == 400


def test_list_payments(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    credit_id = client.post(
        "/api/credits/", json={"customer_id": customer_id, "amount": 5000}
    ).json()["id"]
    client.post(
        "/api/payments/",
        json={"customer_id": customer_id, "credit_id": credit_id, "amount": 100, "method": "cash"},
    )
    r = client.get("/api/payments/")
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_get_payment(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    credit_id = client.post(
        "/api/credits/", json={"customer_id": customer_id, "amount": 5000}
    ).json()["id"]
    payment_id = client.post(
        "/api/payments/",
        json={"customer_id": customer_id, "credit_id": credit_id, "amount": 100, "method": "cash"},
    ).json()["id"]
    r = client.get(f"/api/payments/{payment_id}")
    assert r.status_code == 200
    assert r.json()["amount"] == "100"


def test_get_payment_not_found(client):
    r = client.get("/api/payments/does-not-exist")
    assert r.status_code == 404


def test_get_customer_payments(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    credit_id = client.post(
        "/api/credits/", json={"customer_id": customer_id, "amount": 5000}
    ).json()["id"]
    client.post(
        "/api/payments/",
        json={"customer_id": customer_id, "credit_id": credit_id, "amount": 100, "method": "cash"},
    )
    r = client.get(f"/api/payments/customer/{customer_id}")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_get_credit_payments(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    credit_id = client.post(
        "/api/credits/", json={"customer_id": customer_id, "amount": 5000}
    ).json()["id"]
    client.post(
        "/api/payments/",
        json={"customer_id": customer_id, "credit_id": credit_id, "amount": 100, "method": "cash"},
    )
    r = client.get(f"/api/payments/credit/{credit_id}")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_delete_payment(client):
    customer_id = client.post(
        "/api/customers/", json={"name": "Awa"}
    ).json()["id"]
    credit_id = client.post(
        "/api/credits/", json={"customer_id": customer_id, "amount": 5000}
    ).json()["id"]
    payment_id = client.post(
        "/api/payments/",
        json={"customer_id": customer_id, "credit_id": credit_id, "amount": 100, "method": "cash"},
    ).json()["id"]
    r = client.delete(f"/api/payments/{payment_id}")
    assert r.status_code == 204
    assert client.get(f"/api/payments/{payment_id}").status_code == 404


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------
def test_sync_status(client):
    r = client.get("/api/sync/status")
    assert r.status_code == 200
    body = r.json()
    assert body["is_syncing"] is False
    assert body["pending_count"] == 0


def test_sync_pending_operations(client):
    r = client.get("/api/sync/pending")
    assert r.status_code == 200
    body = r.json()
    assert body["pending_count"] == 0
    assert body["operations"] == []


def test_sync_clear_pending(client):
    r = client.delete("/api/sync/pending")
    assert r.status_code == 204


def test_sync_push_offline(client):
    # No server configured → sync_once returns all skipped.
    r = client.post("/api/sync/push")
    assert r.status_code == 200
    body = r.json()
    assert body["synced"] == 0
    assert body["failed"] == 0

