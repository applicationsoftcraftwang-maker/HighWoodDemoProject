"""
IngestService — command-style methane ingestion workflow.
"""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import UUID
import asyncpg

from app.models.schemas import (
    IngestBatchRequest,
    IngestBatchResponse,
    IngestionProcessingStatus,
)
from app.services.exceptions import SiteNotFoundError


class IngestService:
    async def process_batch(
        self,
        dto: IngestBatchRequest,
        customer_id: UUID,
        pool: asyncpg.Pool,
    ) -> IngestBatchResponse:
        async with pool.acquire() as conn:
            return await self._execute_command(
                conn=conn,
                dto=dto,
                customer_id=customer_id,
            )

    async def _execute_command(
        self,
        conn: asyncpg.Connection,
        dto: IngestBatchRequest,
        customer_id: UUID,
    ) -> IngestBatchResponse:
        site_row = await conn.fetchrow(
            """
            SELECT
                site_id,
                methane_emission_limit,
                methane_accumulated_emissions_to_date
            FROM sites
            WHERE site_id = $1
              AND customer_id = $2
            """,
            dto.site_id,
            customer_id,
        )

        if site_row is None:
            raise SiteNotFoundError(str(dto.site_id))

        total_methane_value = sum(
            Decimal(reading.emission_value)
            for reading in dto.readings
        )

        received_record_count = len(dto.readings)
        processed_record_count = 0
        ingestion_job_id: UUID | None = None
        response_message = "Methane emission readings processed successfully"
        response_error_message: str | None = None

        try:
            async with conn.transaction():
                ingestion_job_id = await conn.fetchval(
                    """
                    INSERT INTO emission_ingestion_jobs (
                        customer_id,
                        site_id,
                        processing_status,
                        received_record_count,
                        processed_record_count,
                        ingestion_token,
                        trace_request_id,
                        response_message
                    )
                    VALUES (
                        $1,
                        $2,
                        'processing',
                        $3,
                        0,
                        $4,
                        $5,
                        'Methane ingestion started'
                    )
                    RETURNING ingestion_job_id
                    """,
                    customer_id,
                    dto.site_id,
                    received_record_count,
                    dto.ingestion_token,
                    dto.trace_request_id,
                )

                await conn.executemany(
                    """
                    INSERT INTO methane_emission_readings (
                        customer_id,
                        site_id,
                        emission_value,
                        emission_unit,
                        ingestion_job_id,
                        captured_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    [
                        (
                            customer_id,
                            dto.site_id,
                            reading.emission_value,
                            reading.emission_unit.value,
                            ingestion_job_id,
                            reading.captured_at,
                        )
                        for reading in dto.readings
                    ],
                )

                processed_record_count = received_record_count

                await conn.execute(
                    """
                    UPDATE sites
                    SET
                        methane_accumulated_emissions_to_date =
                            methane_accumulated_emissions_to_date + $1,
                        updated_at = NOW()
                    WHERE site_id = $2
                      AND customer_id = $3
                    """,
                    total_methane_value,
                    dto.site_id,
                    customer_id,
                )

                previous_total = Decimal(
                    site_row["methane_accumulated_emissions_to_date"]
                )
                emission_limit = Decimal(site_row["methane_emission_limit"])
                new_total = previous_total + total_methane_value
                limit_exceeded = new_total > emission_limit

                if limit_exceeded:
                    response_message = (
                        "Methane readings processed, but the site emission "
                        "limit has been exceeded"
                    )

                await conn.execute(
                    """
                    UPDATE emission_ingestion_jobs
                    SET
                        processing_status = 'processed',
                        processed_record_count = $1,
                        response_message = $2,
                        updated_at = NOW()
                    WHERE ingestion_job_id = $3
                    """,
                    processed_record_count,
                    response_message,
                    ingestion_job_id,
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
                    VALUES (
                        $1,
                        'system',
                        'METHANE_READINGS_INGESTED',
                        'site',
                        $2,
                        $3::jsonb
                    )
                    """,
                    customer_id,
                    dto.site_id,
                    json.dumps(
                        {
                            "ingestion_job_id": str(ingestion_job_id),
                            "site_id": str(dto.site_id),
                            "trace_request_id": dto.trace_request_id,
                            "received_record_count": received_record_count,
                            "processed_record_count": processed_record_count,
                            "batch_total_methane_value": float(total_methane_value),
                            "previous_site_total": float(previous_total),
                            "new_site_total": float(new_total),
                            "methane_emission_limit": float(emission_limit),
                            "limit_exceeded": limit_exceeded,
                        }
                    ),
                )

        except asyncpg.UniqueViolationError:
            existing_job = await conn.fetchrow(
                """
                SELECT
                    ingestion_job_id,
                    processing_status,
                    received_record_count,
                    processed_record_count,
                    response_message,
                    response_error_message
                FROM emission_ingestion_jobs
                WHERE customer_id = $1
                  AND site_id = $2
                  AND ingestion_token = $3
                """,
                customer_id,
                dto.site_id,
                dto.ingestion_token,
            )

            if existing_job is not None:
                return IngestBatchResponse(
                    ingestion_job_id=existing_job["ingestion_job_id"],
                    customer_id=customer_id,
                    site_id=dto.site_id,
                    ingestion_token=dto.ingestion_token,
                    trace_request_id=dto.trace_request_id,
                    processing_status=IngestionProcessingStatus.duplicate,
                    received_record_count=existing_job["received_record_count"],
                    processed_record_count=existing_job["processed_record_count"],
                    total_methane_emission_value=0.0,
                    response_message=(
                        existing_job["response_message"]
                        or "Duplicate ingestion token received"
                    ),
                    response_error_message=existing_job["response_error_message"],
                )

            raise

        except Exception as exc:
            response_error_message = str(exc)

            if ingestion_job_id is not None:
                await conn.execute(
                    """
                    UPDATE emission_ingestion_jobs
                    SET
                        processing_status = 'failed',
                        response_error_message = $1,
                        updated_at = NOW()
                    WHERE ingestion_job_id = $2
                    """,
                    response_error_message,
                    ingestion_job_id,
                )

            raise

        return IngestBatchResponse(
            ingestion_job_id=ingestion_job_id,
            customer_id=customer_id,
            site_id=dto.site_id,
            ingestion_token=dto.ingestion_token,
            trace_request_id=dto.trace_request_id,
            processing_status=IngestionProcessingStatus.processed,
            received_record_count=received_record_count,
            processed_record_count=processed_record_count,
            total_methane_emission_value=float(total_methane_value),
            response_message=response_message,
            response_error_message=None,
        )


# Module-level singleton.
# The service is stateless, so one shared instance is safe.
ingest_service = IngestService()