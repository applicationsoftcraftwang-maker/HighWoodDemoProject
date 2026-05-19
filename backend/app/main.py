"""
Methane Emissions Platform API.

Application lifecycle:
  - Initializes asyncpg pool on startup and stores it in app.state.db_pool
  - Runs migrations + seed data if ENABLE_MIGRATIONS=true (default)
  - Gracefully closes database pool on shutdown

Future iterations will add:
  - standardized API response envelope
  - customer middleware (multi-tenant isolation)
  - emissions ingestion pipeline routes
  - facility analytics + reporting endpoints
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.database import init_emissions_db_pool, shutdown_emissions_db_pool
from app.db.migrate import run_migrations, seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager for emissions platform.
    """

    # -------------------------
    # Startup
    # -------------------------
    db_pool = await init_emissions_db_pool()
    app.state.db_pool = db_pool

    enable_migrations = os.getenv(
        "ENABLE_MIGRATIONS", "true").lower() == "true"

    if enable_migrations:
        async with db_pool.acquire_emissions_connection() as conn:
            await run_migrations(conn)
            await seed(conn)

    yield

    # -------------------------
    # Shutdown
    # -------------------------
    await shutdown_emissions_db_pool()


app = FastAPI(
    title="Methane Emissions Platform API",
    description=(
        "Customer-centric methane emissions ingestion, "
        "monitoring, and compliance analytics platform."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)


@app.get("/api/v1/health")
async def health_check() -> dict[str, str, str]:
    """
    Basic service health check endpoint.
    """
    return {
        "status": "ok",
        "service": "methane-emissions-platform",
        "version": "1.0.0",
    }
