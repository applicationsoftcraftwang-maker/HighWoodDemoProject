from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from uuid import UUID
import json

from app.middleware.customer import get_customer_id
from app.middleware.response import error, success
from app.models.schemas import CreateSiteRequest, SiteResponse

router = APIRouter(prefix="/sites", tags=["sites"])

def _jsonb_to_dict(value):
    if value is None:
        return None

    if isinstance(value, str):
        return json.loads(value)

    return value


def _site_record_to_response(row) -> dict:
    return {
        "site_id": str(row["site_id"]),
        "customer_id": str(row["customer_id"]),
        "site_name": row["site_name"],
        "site_location": row["site_location"],
        "methane_emission_limit": float(row["methane_emission_limit"]),
        "methane_accumulated_emissions_to_date": float(
            row["methane_accumulated_emissions_to_date"]
        ),
        "site_metadata": _jsonb_to_dict(row["site_metadata"]),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


@router.post("", status_code=201)
async def create_site(
    body: CreateSiteRequest,
    request: Request,
    customer_id: UUID = Depends(get_customer_id),
):
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO sites (
                    customer_id,
                    site_name,
                    site_location,
                    methane_emission_limit,
                    site_metadata
                )
                VALUES ($1, $2, $3, $4, $5::jsonb)
                RETURNING *
                """,
                customer_id,
                body.site_name,
                body.site_location,
                float(body.methane_emission_limit),
                json.dumps(body.site_metadata) if body.site_metadata else None,
            )

            await conn.execute(
                """
                INSERT INTO emission_audit_events (
                    customer_id,
                    performed_by,
                    event_action,
                    resource_type,
                    resource_id,
                    event_payload
                )
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                """,
                customer_id,
                "system",
                "SITE_CREATED",
                "site",
                row["site_id"],
                json.dumps(
                    {
                        "site_name": body.site_name,
                        "site_location": body.site_location,
                        "methane_emission_limit": str(body.methane_emission_limit),
                    }
                ),
            )

    return success(_site_record_to_response(row), status_code=201)

@router.get("")
async def list_sites(
    request: Request,
    customer_id: UUID = Depends(get_customer_id),
):
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM sites
            WHERE customer_id = $1
            ORDER BY created_at DESC
            """,
            customer_id,
        )

    return success([_site_record_to_response(row) for row in rows])


@router.get("/{site_id}")
async def get_site(
    site_id: UUID,
    request: Request,
    customer_id: UUID = Depends(get_customer_id),
):
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM sites
            WHERE site_id = $1
              AND customer_id = $2
            """,
            site_id,
            customer_id,
        )

    if not row:
        return error(
            "SITE_NOT_FOUND",
            f"Site {site_id} was not found for this customer.",
            404,
        )

    return success(_site_record_to_response(row))