"""
Methane Emissions Platform API.

This commit adds the cross-cutting concerns: unified response envelope (via
`middleware/response.py` helpers) and global exception handlers that ensure
every response shape is consistent regardless of where the error came from.

Routers (sites, ingest, metrics) come in subsequent commits.
"""

from __future__ import annotations
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.db.database import init_emissions_db_pool, shutdown_emissions_db_pool, acquire_emissions_connection
from app.db.migrate import run_migrations, seed
from app.middleware.response import success, error
from app.routers import sites, ingest

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_pool = await init_emissions_db_pool()
    app.state.db_pool = db_pool

    enable_migrations = os.getenv("RUN_MIGRATIONS", "true").lower() == "true"

    if enable_migrations:
        async with acquire_emissions_connection() as conn:
            await run_migrations(conn)
            await seed(conn)
    yield
    await shutdown_emissions_db_pool()


app = FastAPI(
    title="Methane Emissions API",
    description="Industrial methane emissions ingestion & analytics.",
    version="0.3.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# CORS — allow the frontend dev server (and any prod URL set via env)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("FRONTEND_URL", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers


@app.exception_handler(RequestValidationError)
async def fastapi_validation_handler(request: Request, exc: RequestValidationError):
    return error("VALIDATION_ERROR", "Validation failed", 422, exc.errors())


@app.exception_handler(ValidationError)
async def pydantic_validation_handler(request: Request, exc: ValidationError):
    return error("VALIDATION_ERROR", "Validation failed", 422, exc.errors())


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return error(
            exc.detail.get("code", "ERROR"),
            exc.detail.get("message", "Error"),
            exc.status_code,
            exc.detail.get("details"),
        )
    return error(f"HTTP_{exc.status_code}", str(exc.detail), exc.status_code)


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    return error("INTERNAL_ERROR", str(exc), 500)

# Routers
prefix = "/api/v1"
app.include_router(sites.router, prefix=prefix)
app.include_router(ingest.router, prefix=prefix)

@app.get("/api/v1/health")
async def health_check() -> dict[str, str, str]:
    return {
        "status": "ok",
        "service": "methane-emissions-platform",
        "version": "0.3.0",
    }
