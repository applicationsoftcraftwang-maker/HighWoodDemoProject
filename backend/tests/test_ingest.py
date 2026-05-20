from __future__ import annotations

import uuid
from datetime import datetime, timezone


def _body(
    site_id,
    ingestion_token: str | None = None,
    trace_request_id: str | None = None,
    emission_value=100,
    reading_count: int = 1,
    captured_at: datetime | None = None,
):
    captured_at = captured_at or datetime.now(timezone.utc)

    return {
        "site_id": str(site_id),
        "ingestion_token": ingestion_token or f"ingest-{uuid.uuid4()}",
        "trace_request_id": trace_request_id or f"trace-{uuid.uuid4()}",
        "readings": [
            {
                "emission_value": emission_value,
                "emission_unit": "kg",
                "captured_at": captured_at.isoformat(),
            }
            for _ in range(reading_count)
        ],
    }


def _first_site_id(client):
    sites = client.get("/api/v1/sites").json()["data"]
    return sites[0]["site_id"]


def _site_with_limit(client, methane_limit: float):
    sites = client.get("/api/v1/sites").json()["data"]

    for site in sites:
        if float(site["methane_emission_limit"]) == methane_limit:
            return site

    raise AssertionError(f"No seeded site found with methane limit {methane_limit}")


# ── Case 1: new token → processed ───────────────────────────────────────────


def test_fresh_methane_batch_returns_processed(client):
    site_id = _first_site_id(client)

    response = client.post(
        "/api/v1/ingest",
        json=_body(site_id, emission_value=50),
    )

    assert response.status_code == 200

    body = response.json()
    data = body["data"]

    assert body["success"] is True
    assert data["processing_status"] == "processed"
    assert data["total_methane_emission_value"] == 50
    assert data["received_record_count"] == 1
    assert data["processed_record_count"] == 1
    assert data["site_id"] == str(site_id)
    assert data["ingestion_token"] is not None
    assert data["trace_request_id"] is not None
    assert data["ingestion_job_id"] is not None


def test_methane_batch_increments_site_total(client):
    site_id = _first_site_id(client)

    client.post(
        "/api/v1/ingest",
        json=_body(site_id, emission_value=30),
    )
    client.post(
        "/api/v1/ingest",
        json=_body(site_id, emission_value=20),
    )

    metrics = client.get(f"/api/v1/sites/{site_id}/metrics").json()["data"]

    assert metrics["methane_accumulated_emissions_to_date"] == 50
    assert metrics["reading_count"] == 2


def test_batch_size_limit_enforced(client):
    """
    Batches over 100 readings must be rejected by the Pydantic schema.
    """
    site_id = _first_site_id(client)

    response = client.post(
        "/api/v1/ingest",
        json=_body(site_id, reading_count=101),
    )

    assert response.status_code == 422


def test_unknown_site_returns_404(client):
    response = client.post(
        "/api/v1/ingest",
        json=_body(uuid.uuid4()),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CUSTOMER_SITE_NOT_FOUND"


# ── Case 2: same token + same body → duplicate ──────────────────────────────


def test_duplicate_methane_request_returns_duplicate_response(client):
    site_id = _first_site_id(client)

    shared_token = f"duplicate-{uuid.uuid4()}"
    shared_trace_id = f"trace-{uuid.uuid4()}"
    shared_captured_at = datetime.now(timezone.utc)

    body = _body(
        site_id,
        ingestion_token=shared_token,
        trace_request_id=shared_trace_id,
        emission_value=42,
        captured_at=shared_captured_at,
    )

    first_response = client.post("/api/v1/ingest", json=body)
    second_response = client.post("/api/v1/ingest", json=body)

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_data = first_response.json()["data"]
    second_data = second_response.json()["data"]

    assert first_data["processing_status"] == "processed"
    assert second_data["processing_status"] == "duplicate"

    assert second_data["ingestion_job_id"] == first_data["ingestion_job_id"]
    assert second_data["ingestion_token"] == first_data["ingestion_token"]
    assert second_data["trace_request_id"] == first_data["trace_request_id"]

    # Duplicate replay should not create a new methane total.
    assert second_data["total_methane_emission_value"] == 0.0


def test_duplicate_methane_request_does_not_double_count(client):
    site_id = _first_site_id(client)

    shared_token = f"duplicate-count-{uuid.uuid4()}"
    shared_trace_id = f"trace-{uuid.uuid4()}"
    shared_captured_at = datetime.now(timezone.utc)

    body = _body(
        site_id,
        ingestion_token=shared_token,
        trace_request_id=shared_trace_id,
        emission_value=42,
        captured_at=shared_captured_at,
    )

    client.post("/api/v1/ingest", json=body)
    client.post("/api/v1/ingest", json=body)
    client.post("/api/v1/ingest", json=body)

    metrics = client.get(f"/api/v1/sites/{site_id}/metrics").json()["data"]

    assert metrics["methane_accumulated_emissions_to_date"] == 42
    assert metrics["reading_count"] == 1


# ── Case 3: same token + different body → 409 ───────────────────────────────


def test_same_ingestion_token_different_body_returns_409(client):
    site_id = _first_site_id(client)

    shared_token = f"conflict-{uuid.uuid4()}"
    shared_trace_id = f"trace-{uuid.uuid4()}"

    first_response = client.post(
        "/api/v1/ingest",
        json=_body(
            site_id,
            ingestion_token=shared_token,
            trace_request_id=shared_trace_id,
            emission_value=100,
        ),
    )

    second_response = client.post(
        "/api/v1/ingest",
        json=_body(
            site_id,
            ingestion_token=shared_token,
            trace_request_id=shared_trace_id,
            emission_value=999,
        ),
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 409

    body = second_response.json()

    assert body["success"] is False
    assert body["error"]["code"] in {
        "METHANE_INGESTION_TOKEN_CONFLICT",
        "INGESTION_TOKEN_REUSED_WITH_DIFFERENT_PAYLOAD",
        "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
    }


# ── Customer/site scoping ───────────────────────────────────────────────────


def test_same_ingestion_token_works_across_different_sites(client):
    """
    The unique constraint is scoped by customer_id + site_id + ingestion_token.

    So the same ingestion token can be used for a different site without being
    treated as a duplicate.
    """
    sites = client.get("/api/v1/sites").json()["data"]

    site_a = sites[0]["site_id"]
    site_b = sites[1]["site_id"]

    shared_token = f"cross-site-{uuid.uuid4()}"

    first_response = client.post(
        "/api/v1/ingest",
        json=_body(site_a, ingestion_token=shared_token, emission_value=10),
    )

    second_response = client.post(
        "/api/v1/ingest",
        json=_body(site_b, ingestion_token=shared_token, emission_value=10),
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    assert first_response.json()["data"]["processing_status"] == "processed"
    assert second_response.json()["data"]["processing_status"] == "processed"


# ── Compliance metrics ──────────────────────────────────────────────────────


def test_limit_exceeded_compliance_status(client):
    site = _site_with_limit(client, methane_limit=5000.0)
    site_id = site["site_id"]

    client.post(
        "/api/v1/ingest",
        json=_body(site_id, emission_value=6000),
    )

    metrics = client.get(f"/api/v1/sites/{site_id}/metrics").json()["data"]

    assert metrics["compliance_status"] == "limit_exceeded"
    assert metrics["utilization_percent"] > 100


def test_within_limit_compliance_status(client):
    site = _site_with_limit(client, methane_limit=5000.0)
    site_id = site["site_id"]

    client.post(
        "/api/v1/ingest",
        json=_body(site_id, emission_value=1000),
    )

    metrics = client.get(f"/api/v1/sites/{site_id}/metrics").json()["data"]

    assert metrics["compliance_status"] == "within_limit"
    assert metrics["utilization_percent"] == 20.0


def test_zero_emission_value_rejected(client):
    """
    Methane emission values must be greater than 0 per schema.py.
    """
    site_id = _first_site_id(client)

    response = client.post(
        "/api/v1/ingest",
        json=_body(site_id, emission_value=0),
    )

    assert response.status_code == 422


def test_metrics_includes_last_reading_captured_at(client):
    site_id = _first_site_id(client)

    client.post(
        "/api/v1/ingest",
        json=_body(site_id, emission_value=10),
    )

    metrics = client.get(f"/api/v1/sites/{site_id}/metrics").json()["data"]

    assert metrics["last_reading_captured_at"] is not None
    assert metrics["reading_count"] == 1