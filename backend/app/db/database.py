import os
import asyncpg
from contextlib import asynccontextmanager

_emissions_db_pool: asyncpg.Pool | None = None


async def init_emissions_db_pool() -> asyncpg.Pool:
    """
    Initialize the global PostgreSQL connection pool for the methane emissions platform.
    Idempotent and safe to call multiple times.
    """

    global _emissions_db_pool

    if _emissions_db_pool is not None:
        return _emissions_db_pool

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://emissions:emissions@localhost:5432/emissions"
    )

    _emissions_db_pool = await asyncpg.create_pool(
        dsn=database_url,
        min_size=2,
        max_size=20,
        command_timeout=30,
    )

    return _emissions_db_pool


async def shutdown_emissions_db_pool() -> None:
    """
    Gracefully close the emissions database pool.
    Safe to call even if pool was never initialized.
    """

    global _emissions_db_pool

    if _emissions_db_pool is not None:
        await _emissions_db_pool.close()
        _emissions_db_pool = None


def get_emissions_db_pool() -> asyncpg.Pool:
    """
    Synchronous accessor for the emissions DB pool.

    Raises:
        RuntimeError: if pool has not been initialized.
    """

    if _emissions_db_pool is None:
        raise RuntimeError(
            "Emissions DB pool not initialized. "
            "Call init_emissions_db_pool() first."
        )

    return _emissions_db_pool


@asynccontextmanager
async def acquire_emissions_connection():
    """
    Acquire a single connection from the emissions DB pool.

    Usage:
        async with acquire_emissions_connection() as conn:
            await conn.fetch(...)
    """

    async with get_emissions_db_pool().acquire() as conn:
        yield conn