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

from app.db.migrate import run_migrations, seed  # noqa: E402


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


@pytest_asyncio.fixture
async def pool() -> asyncpg.Pool:
    """
    Function-scoped asyncpg pool.

    Important:
    Do not use scope='session' here unless pytest-asyncio is configured to use
    a session-scoped event loop. asyncpg pools are bound to the event loop that
    created them.
    """
    test_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=20,
    )

    async with test_pool.acquire() as conn:
        await run_migrations(conn)
        await seed(conn)

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
            SET
                methane_accumulated_emissions_to_date = 0,
                updated_at = NOW()
            WHERE customer_id = $1
            """,
            DEMO_CUSTOMER_ID,
        )

    try:
        yield test_pool
    finally:
        await test_pool.close()


@pytest_asyncio.fixture
async def site_id(pool: asyncpg.Pool) -> uuid.UUID:
    """
    Return one seeded methane monitoring site.
    """
    async with pool.acquire() as conn:
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
            "Check run_migrations() and seed()."
        )

    return value


@pytest_asyncio.fixture
async def customer_id() -> uuid.UUID:
    return DEMO_CUSTOMER_ID


@pytest.fixture
def client(pool: asyncpg.Pool) -> TestClient:
    """
    FastAPI test client for API-level tests.

    Keep this fixture name as `client` because test_ingest.py,
    test_sites.py, and most API tests expect that convention.
    """
    os.environ["DATABASE_URL"] = DATABASE_URL
    os.environ["RUN_MIGRATIONS"] = "false"

    from app.main import app
    app.state.pool = pool

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def customer(client: TestClient) -> TestClient:
    """
    Backward-compatible alias.

    Some older tests may still use `customer`.
    """
    return client
