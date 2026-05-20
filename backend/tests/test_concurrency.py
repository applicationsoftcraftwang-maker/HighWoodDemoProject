from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models.schemas import (
    IngestBatchRequest,
    MethaneEmissionReadingItem,
    MethaneEmissionUnit,
)
from app.services.ingest_service import ingest_service


CONCURRENT_REQUEST_COUNT = 10
DEMO_CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _make_ingest_request(
    site_id: uuid.UUID,
    ingestion_token: str,
    trace_request_id: str | None = None,
    emission_value: Decimal | float | str = Decimal("7.0"),
    captured_at: datetime | None = None,
) -> IngestBatchRequest:
    """
    Build a methane ingestion request using the exact schema.py names:

        - IngestBatchRequest
        - MethaneEmissionReadingItem
        - MethaneEmissionUnit
        - ingestion_token
        - trace_request_id
        - readings
        - emission_value
        - emission_unit
        - captured_at
    """
    return IngestBatchRequest(
        site_id=site_id,
        ingestion_token=ingestion_token,
        trace_request_id=trace_request_id or f"pytest-trace-{uuid.uuid4()}",
        readings=[
            MethaneEmissionReadingItem(
                emission_value=Decimal(str(emission_value)),
                emission_unit=MethaneEmissionUnit.kg,
                captured_at=captured_at or datetime.now(timezone.utc),
            )
        ],
    )


async def _submit_ingestion_request(
    pool,
    dto: IngestBatchRequest,
):
    """
    Submit one request directly through the service.

    The service is responsible for detecting duplicate ingestion tokens and
    replaying duplicate responses safely.
    """
    return await ingest_service.process_batch(
        dto=dto,
        customer_id=DEMO_CUSTOMER_ID,
        pool=pool,
    )


@pytest.mark.asyncio
async def test_concurrent_unique_ingestion_tokens_update_methane_total_safely(
    pool,
    site_id,
):
    """
    Many unique ingestion tokens against the same site should all be processed.

    This verifies that site total updates are serialized correctly and no
    methane readings are lost during concurrent ingestion.
    """
    async with pool.acquire() as conn:
        starting_total = await conn.fetchval(
            """
            SELECT methane_accumulated_emissions_to_date
            FROM sites
            WHERE site_id = $1
              AND customer_id = $2
            """,
            site_id,
            DEMO_CUSTOMER_ID,
        )

        starting_reading_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM methane_emission_readings
            WHERE site_id = $1
              AND customer_id = $2
            """,
            site_id,
            DEMO_CUSTOMER_ID,
        )

    results = await asyncio.gather(
        *[
            _submit_ingestion_request(
                pool=pool,
                dto=_make_ingest_request(
                    site_id=site_id,
                    ingestion_token=f"pytest-unique-{uuid.uuid4()}",
                    emission_value=Decimal("7.0"),
                ),
            )
            for _ in range(CONCURRENT_REQUEST_COUNT)
        ],
        return_exceptions=True,
    )

    errors = [item for item in results if isinstance(item, Exception)]
    assert not errors, f"Unexpected concurrency errors: {errors}"

    processed = [
        item
        for item in results
        if item.processing_status.value == "processed"
    ]

    assert len(processed) == CONCURRENT_REQUEST_COUNT

    async with pool.acquire() as conn:
        ending_total = await conn.fetchval(
            """
            SELECT methane_accumulated_emissions_to_date
            FROM sites
            WHERE site_id = $1
              AND customer_id = $2
            """,
            site_id,
            DEMO_CUSTOMER_ID,
        )

        ending_reading_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM methane_emission_readings
            WHERE site_id = $1
              AND customer_id = $2
            """,
            site_id,
            DEMO_CUSTOMER_ID,
        )

    expected_added_total = Decimal(str(CONCURRENT_REQUEST_COUNT * 7.0))

    assert Decimal(str(ending_total)) - \
        Decimal(str(starting_total)) == expected_added_total
    assert ending_reading_count - starting_reading_count == CONCURRENT_REQUEST_COUNT


@pytest.mark.asyncio
async def test_concurrent_identical_ingestion_token_is_deduplicated(
    pool,
    site_id,
):
    """
    Many identical requests should result in one processed ingestion job.

    The duplicate requests should not insert extra methane readings and should
    not increase the site's accumulated emissions more than once.
    """
    shared_ingestion_token = f"pytest-shared-{uuid.uuid4()}"
    shared_trace_request_id = f"pytest-trace-{uuid.uuid4()}"
    shared_captured_at = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        starting_total = await conn.fetchval(
            """
            SELECT methane_accumulated_emissions_to_date
            FROM sites
            WHERE site_id = $1
              AND customer_id = $2
            """,
            site_id,
            DEMO_CUSTOMER_ID,
        )

        starting_reading_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM methane_emission_readings
            WHERE site_id = $1
              AND customer_id = $2
            """,
            site_id,
            DEMO_CUSTOMER_ID,
        )

    def make_identical_request() -> IngestBatchRequest:
        return _make_ingest_request(
            site_id=site_id,
            ingestion_token=shared_ingestion_token,
            trace_request_id=shared_trace_request_id,
            emission_value=Decimal("50.0"),
            captured_at=shared_captured_at,
        )

    results = await asyncio.gather(
        *[
            _submit_ingestion_request(
                pool=pool,
                dto=make_identical_request(),
            )
            for _ in range(CONCURRENT_REQUEST_COUNT)
        ],
        return_exceptions=True,
    )

    errors = [item for item in results if isinstance(item, Exception)]
    assert not errors, f"Unexpected duplicate-race errors: {errors}"

    processed = [
        item
        for item in results
        if item.processing_status.value == "processed"
    ]

    duplicates = [
        item
        for item in results
        if item.processing_status.value == "duplicate"
    ]

    assert len(processed) == 1
    assert len(duplicates) == CONCURRENT_REQUEST_COUNT - 1

    async with pool.acquire() as conn:
        ending_total = await conn.fetchval(
            """
            SELECT methane_accumulated_emissions_to_date
            FROM sites
            WHERE site_id = $1
              AND customer_id = $2
            """,
            site_id,
            DEMO_CUSTOMER_ID,
        )

        ending_reading_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM methane_emission_readings
            WHERE site_id = $1
              AND customer_id = $2
            """,
            site_id,
            DEMO_CUSTOMER_ID,
        )

        ingestion_job_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM emission_ingestion_jobs
            WHERE customer_id = $1
              AND site_id = $2
              AND ingestion_token = $3
            """,
            DEMO_CUSTOMER_ID,
            site_id,
            shared_ingestion_token,
        )

    assert Decimal(str(ending_total)) - \
        Decimal(str(starting_total)) == Decimal("50.0")
    assert ending_reading_count - starting_reading_count == 1
    assert ingestion_job_count == 1
