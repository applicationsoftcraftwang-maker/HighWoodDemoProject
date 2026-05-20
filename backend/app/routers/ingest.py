"""
Methane ingestion router — POST /api/v1/ingest.
"""

from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, Request

from app.middleware.customer import get_customer_id
from app.middleware.response import error, success
from app.models.schemas import IngestBatchRequest
from app.services.exceptions import EmissionsPlatformError
from app.services.ingest_service import ingest_service

router = APIRouter(prefix="/ingest", tags=["methane-ingestion"])

@router.post("")
async def ingest_methane_emission_readings(
    body: IngestBatchRequest,
    request: Request,
    customer_id: UUID = Depends(get_customer_id),
):
    """
    Ingest methane emission readings for one customer site.
    """
    pool = request.app.state.db_pool

    try:
        ingestion_result = await ingest_service.process_batch(
            dto=body,
            customer_id=customer_id,
            pool=pool,
        )
    except EmissionsPlatformError as exc:
        return error(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_hint,
        )

    return success(
        {
            "ingestion_job_id": str(ingestion_result.ingestion_job_id),
            "customer_id": str(customer_id),
            "site_id": str(body.site_id),
            "ingestion_token": body.ingestion_token,
            "trace_request_id": body.trace_request_id,
            "processing_status": ingestion_result.processing_status.value,
            "received_record_count": ingestion_result.received_record_count,
            "processed_record_count": ingestion_result.processed_record_count,
            "total_methane_emission_value": float(
                ingestion_result.total_methane_emission_value
            ),
            "response_message": ingestion_result.response_message,
            "response_error_message": ingestion_result.response_error_message,
        },
        status_code=200
    )


@router.get("/stats")
async def get_ingest_stats(request: Request):
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COALESCE(SUM(s.methane_accumulated_emissions_to_date), 0) AS total_emissions_to_date,
                COALESCE(SUM(s.methane_emission_limit), 0) AS emission_limit,
                COUNT(DISTINCT s.site_id) AS active_sites,
                (
                    SELECT COUNT(*)
                    FROM methane_emission_readings r
                ) AS total_measurements
            FROM sites s
            """
        )

    return success(
        {
            "total_emissions_to_date": float(row["total_emissions_to_date"] or 0),
            "emission_limit": float(row["emission_limit"] or 0),
            "total_measurements": int(row["total_measurements"] or 0),
            "active_sites": int(row["active_sites"] or 0),
        }
    )
