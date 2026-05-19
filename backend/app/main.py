from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="HighWood Demo Project Backend",
    description="This is the backend API for the HighWood Emissions Demo Project.",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

@app.get("/api/v1/health", tags=["Health Check"])
async def health_check() -> dict[str, str]:
    """
    Health check endpoint to verify that the API is running.
    """
    return {"status": "ok", "version": "0.1.0"}