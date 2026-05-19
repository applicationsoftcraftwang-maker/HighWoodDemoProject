from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient


# Allow tests/ to import the local app package without installing the project.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://emissions:emissions@localhost:5432/emissions",
)

DEMO_CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

SEEDED_SITE_NAMES = (
    "Highwood Well Pad Alpha",
    "Pembina Compressor Station",
    "Montney Gas Processing Facility",
)


@pytest_asyncio.fixture(autouse=True)
async def reset_db() -> None:
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        await conn.execute(
            """
            TRUNCATE TABLE
                methane_emission_readings,
                emission_ingestion_jobs,
                emission_notifications,
                emission_audit_events
            RESTART IDENTITY
            CASCADE
            """
        )

        await conn.execute(
            """
            DELETE FROM sites
            WHERE site_name <> ALL($1::text[])
            """,
            list(SEEDED_SITE_NAMES),
        )

        await conn.execute(
            """
            UPDATE sites
            SET methane_accumulated_emissions_to_date = 0
            """
        )

    finally:
        await conn.close()

    yield


@pytest_asyncio.fixture
async def pool() -> asyncpg.Pool:
    test_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=20,
    )

    try:
        yield test_pool
    finally:
        await test_pool.close()


@pytest.fixture
def customer() -> TestClient:
    """
    FastAPI test customer for API-level tests.

    The TestClient runs the FastAPI lifespan, so the app creates and closes its
    PostgreSQL pool the same way it does in normal local execution.
    """
    os.environ["DATABASE_URL"] = DATABASE_URL
    os.environ["RUN_MIGRATIONS"] = "false"

    from app.main import app

    with TestClient(app) as test_customer:
        yield test_customer


@pytest_asyncio.fixture
async def site_id() -> uuid.UUID:
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        value = await conn.fetchval(
            """
            SELECT site_id
            FROM sites
            WHERE customer_id = $1
            ORDER BY created_at
            LIMIT 1
            """,
            DEMO_CUSTOMER_ID,
        )

        if value is None:
            raise RuntimeError(
                "No seeded site found for the demo customer. "
                "Run `python -m app.db.migrate` before running tests."
            )

        return value

    finally:
        await conn.close()


@pytest_asyncio.fixture
async def customer_id() -> uuid.UUID:
    return DEMO_CUSTOMER_ID