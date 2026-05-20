from __future__ import annotations
import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from app.models.schemas import IngestBatchRequest, MeasurementItem, UnitEnum
from app.services.ingest_service import ingest_service, _ConcurrentDuplicate


N = 10


def _make_dto(site_id: uuid.UUID, key: str, value: float = 7.0) -> IngestBatchRequest:
    return IngestBatchRequest(
        site_id=site_id,
        idempotency_key=key,
        measurements=[MeasurementItem(
            value=value, unit=UnitEnum.kg,
            recorded_at=datetime.now(timezone.utc),
        )],
    )


async def _fire_with_retry(pool, dto, tenant_id):
    """Mirror the router's _ConcurrentDuplicate retry pattern."""
    try:
        return await ingest_service.process_batch(dto, tenant_id, pool)
    except _ConcurrentDuplicate:
        return await ingest_service.process_batch(dto, tenant_id, pool)


@pytest.mark.asyncio
async def test_no_double_count_with_concurrent_unique_keys(pool, site_id):
    """N concurrent transactions, UNIQUE keys, same site → no lost updates."""
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    results = await asyncio.gather(
        *[_fire_with_retry(pool, _make_dto(site_id, f"k-{uuid.uuid4()}"), tenant_id)
          for _ in range(N)],
        return_exceptions=True,
    )

    errors = [r for r in results if isinstance(r, Exception)]
    assert not errors, f"Unexpected errors: {errors}"
    processed = [r for r in results if r.status.value == "processed"]
    assert len(processed) == N, f"Expected {N} processed, got {len(processed)}"

    async with pool.acquire() as conn:
        total = float(await conn.fetchval(
            "SELECT total_emissions_to_date FROM sites WHERE id = $1", site_id,
        ))
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM measurements WHERE site_id = $1", site_id,
        )
    assert total == N * 7.0, f"Lost updates: expected {N * 7.0}, got {total}"
    assert count == N


@pytest.mark.asyncio
async def test_concurrent_identical_requests_deduplicated(pool, site_id):
    """N parallel IDENTICAL requests → exactly 1 processed, rest are duplicates."""
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    shared_key = f"shared-{uuid.uuid4()}"
    recorded = datetime.now(timezone.utc)

    def fresh_dto():
        return IngestBatchRequest(
            site_id=site_id,
            idempotency_key=shared_key,
            measurements=[MeasurementItem(value=50.0, unit=UnitEnum.kg, recorded_at=recorded)],
        )

    results = await asyncio.gather(
        *[_fire_with_retry(pool, fresh_dto(), tenant_id) for _ in range(N)],
        return_exceptions=True,
    )

    errors = [r for r in results if isinstance(r, Exception)]
    assert not errors, f"Unexpected errors: {errors}"

    processed = [r for r in results if r.status.value == "processed"]
    duplicates = [r for r in results if r.status.value == "duplicate"]

    assert len(processed) == 1, f"Expected exactly 1 processed, got {len(processed)}"
    assert len(duplicates) == N - 1, f"Expected {N - 1} duplicates, got {len(duplicates)}"

    async with pool.acquire() as conn:
        total = float(await conn.fetchval(
            "SELECT total_emissions_to_date FROM sites WHERE id = $1", site_id,
        ))
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM measurements WHERE site_id = $1", site_id,
        )
    assert total == 50.0, f"Double-counted: expected 50, got {total}"
    assert count == 1
