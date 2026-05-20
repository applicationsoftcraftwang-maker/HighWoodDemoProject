from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.middleware.response import error, success
from app.middleware.customer import get_customer_id


router = APIRouter(prefix="/sites", tags=["metrics"])


@router.get("/{site_id}/metrics")
async def get_site_metrics(
    site_id: UUID,
    request: Request,
    customer_id: UUID = Depends(get_customer_id),
):
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        site = await conn.fetchrow(
            """
            SELECT
                site_id,
                customer_id,
                site_name,
                site_location,
                methane_emission_limit,
                methane_accumulated_emissions_to_date,
                site_metadata,
                created_at,
                updated_at
            FROM sites
            WHERE site_id = $1
              AND customer_id = $2
            """,
            site_id,
            customer_id,
        )

        if site is None:
            return error(
                "SITE_NOT_FOUND",
                f"Methane monitoring site {site_id} was not found",
                404,
            )

        reading_stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS reading_count,
                COALESCE(SUM(emission_value), 0) AS recorded_total,
                MAX(captured_at) AS last_captured_at
            FROM methane_emission_readings
            WHERE site_id = $1
              AND customer_id = $2
            """,
            site_id,
            customer_id,
        )

        ingestion_stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS ingestion_job_count,
                COUNT(*) FILTER (
                    WHERE processing_status = 'processed'
                ) AS processed_job_count,
                COUNT(*) FILTER (
                    WHERE processing_status = 'duplicate'
                ) AS duplicate_job_count,
                COUNT(*) FILTER (
                    WHERE processing_status = 'failed'
                ) AS failed_job_count,
                MAX(updated_at) AS last_ingestion_at
            FROM emission_ingestion_jobs
            WHERE site_id = $1
              AND customer_id = $2
            """,
            site_id,
            customer_id,
        )

        open_notification_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM emission_notifications
            WHERE customer_id = $1
              AND is_acknowledged = FALSE
            """,
            customer_id,
        )

    methane_limit = float(site["methane_emission_limit"])
    accumulated_total = float(site["methane_accumulated_emissions_to_date"])

    utilization_percent = (
        round((accumulated_total / methane_limit) * 100, 2)
        if methane_limit > 0
        else 0.0
    )

    if accumulated_total > methane_limit:
        compliance_status = "limit_exceeded"
    elif utilization_percent >= 90:
        compliance_status = "near_limit"
    else:
        compliance_status = "within_limit"

    last_captured_at = reading_stats["last_captured_at"]
    last_ingestion_at = ingestion_stats["last_ingestion_at"]

    return success(
        {
            "site_id": str(site["site_id"]),
            "customer_id": str(site["customer_id"]),
            "site_name": site["site_name"],
            "site_location": site["site_location"],
            "methane_emission_limit": methane_limit,
            "methane_accumulated_emissions_to_date": accumulated_total,
            "methane_recorded_total_from_readings": float(
                reading_stats["recorded_total"]
            ),
            "compliance_status": compliance_status,
            "utilization_percent": utilization_percent,
            "reading_count": int(reading_stats["reading_count"]),
            "last_reading_captured_at": (
                last_captured_at.isoformat()
                if last_captured_at
                else None
            ),
            "ingestion_jobs": {
                "total": int(ingestion_stats["ingestion_job_count"]),
                "processed": int(ingestion_stats["processed_job_count"]),
                "duplicate": int(ingestion_stats["duplicate_job_count"]),
                "failed": int(ingestion_stats["failed_job_count"]),
                "last_ingestion_at": (
                    last_ingestion_at.isoformat()
                    if last_ingestion_at
                    else None
                ),
            },
            "open_notification_count": int(open_notification_count),
            "site_metadata": site["site_metadata"],
            "updated_at": site["updated_at"].isoformat(),
        }
    )