from __future__ import annotations

def test_list_sites_returns_seeded_data(customer):
    response = customer.get("/api/v1/sites")
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) == 3

    assert {site["site_name"] for site in body["data"]} == {
        "Highwood Well Pad Alpha",
        "Pembina Compressor Station",
        "Montney Gas Processing Facility",
    }


def test_get_site_by_id(customer):
    sites = customer.get("/api/v1/sites").json()["data"]
    site_id = sites[0]["site_id"]
    response = customer.get(f"/api/v1/sites/{site_id}")

    assert response.status_code == 200
    assert response.json()["data"]["site_id"] == site_id


def test_get_unknown_site_returns_404(customer):
    response = customer.get(
        "/api/v1/sites/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404
    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "SITE_NOT_FOUND"


def test_create_site_returns_201(customer):
    response = customer.post(
        "/api/v1/sites",
        json={
            "site_name": "Calgary Methane Test Site",
            "site_location": "Calgary, Alberta",
            "methane_emission_limit": 1000,
            "site_metadata": {
                "operator": "Test Operator",
                "site_type": "test_site",
            },
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["success"] is True
    assert body["data"]["site_name"] == "Calgary Methane Test Site"
    assert body["data"]["site_location"] == "Calgary, Alberta"
    assert float(body["data"]["methane_emission_limit"]) == 1000.0
    assert float(body["data"]["methane_accumulated_emissions_to_date"]) == 0.0


def test_create_site_validation_error(customer):
    response = customer.post(
        "/api/v1/sites",
        json={
            "site_name": "",
            "site_location": "Calgary, Alberta",
            "methane_emission_limit": 1000,
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False


def test_response_envelope_shape(customer):
    response = customer.get("/api/v1/sites")

    assert response.status_code == 200
    body = response.json()

    assert set(body.keys()) == {"success", "data", "meta"}
    assert set(body["meta"].keys()) >= {"timestamp", "version"}


def test_error_envelope_shape(customer):
    response = customer.get(
        "/api/v1/sites/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404
    body = response.json()

    assert set(body.keys()) == {"success", "error", "meta"}
    assert set(body["error"].keys()) >= {"code", "message"}


def test_customer_isolation(customer):
    response = customer.get(
        "/api/v1/sites",
        headers={
            "X-Customer-Id": "00000000-0000-0000-0000-000000000999",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_invalid_customer_id_returns_400(customer):
    response = customer.get(
        "/api/v1/sites",
        headers={"X-Customer-Id": "not-a-uuid"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CUSTOMER_ID"