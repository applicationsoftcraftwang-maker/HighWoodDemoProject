"""
IngestService — command-style methane ingestion workflow.
"""

from __future__ import annotations

import json
import hashlib
from decimal import Decimal
from uuid import UUID
import asyncpg

from app.models.schemas import (
    IngestBatchRequest,
    IngestBatchResponse,
    IngestionProcessingStatus,
)

from app.services.exceptions import (
    CustomerSiteNotFoundError,
    MethaneIngestionTokenConflictError,
)
class _ConcurrentDuplicate(Exception):
    """
    Internal sentinel used when another request inserts the same ingestion_token
    before this request commits.
    """
    pass
class IngestService:
    async def process_batch(self, dto: IngestBatchRequest, customer_id: UUID, pool: asyncpg.Pool) -> IngestBatchResponse:
        request_fingerprint = self._hash_request(dto)

        async with pool.acquire() as conn:
            existing_job = await self._find_existing_ingestion_job(
                conn=conn,
                customer_id=customer_id,
                site_id=dto.site_id,
                ingestion_token=dto.ingestion_token,
            )

        if existing_job is not None:
            return self._replay_or_conflict(
                existing_job=existing_job,
                request_fingerprint=request_fingerprint,
                dto=dto,
                customer_id=customer_id,
            )

        try:
            async with pool.acquire() as conn:
                return await self._execute_command(
                    conn=conn,
                    dto=dto,
                    customer_id=customer_id,
                    request_fingerprint=request_fingerprint,
                )

        except _ConcurrentDuplicate:
            async with pool.acquire() as conn:
                existing_job = await self._find_existing_ingestion_job(
                    conn=conn,
                    customer_id=customer_id,
                    site_id=dto.site_id,
                    ingestion_token=dto.ingestion_token,
                )

            if existing_job is None:
                raise

            return self._replay_or_conflict(
                existing_job=existing_job,
                request_fingerprint=request_fingerprint,
                dto=dto,
                customer_id=customer_id,
            )

    async def _execute_command(self, conn: asyncpg.Connection, dto: IngestBatchRequest, customer_id: UUID, request_fingerprint: str,) -> IngestBatchResponse:
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
            raise CustomerSiteNotFoundError(str(dto.site_id))

        async with conn.transaction():
            # Step 1: PESSIMISTIC LOCK FIRST
            site_row = await conn.fetchrow(
                """
                SELECT
                    site_id,
                    methane_emission_limit,
                    methane_accumulated_emissions_to_date
                FROM sites
                WHERE site_id = $1
                    AND customer_id = $2
                FOR UPDATE
                """,
                dto.site_id,
                customer_id,
            )
            if site_row is None:
                raise CustomerSiteNotFoundError(str(dto.site_id))

            # Step 2: insert idempotency record
            try:
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
                        response_message,
                        request_fingerprint
                    )
                    VALUES (
                        $1,
                        $2,
                        'processing',
                        $3,
                        0,
                        $4,
                        $5,
                        $6,
                        $7
                    )
                    RETURNING ingestion_job_id
                    """,
                    customer_id,
                    dto.site_id,
                    received_record_count,
                    dto.ingestion_token,
                    dto.trace_request_id,
                    "Methane ingestion request accepted",
                    request_fingerprint,
                )

            except asyncpg.UniqueViolationError:
                raise _ConcurrentDuplicate()

            # Step 3: insert all readings/ingestion
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

            received_record_count = len(dto.readings)
            processed_record_count = received_record_count
            total_methane_value = sum(Decimal(reading.emission_value)
                                      for reading in dto.readings)
            previous_site_total = Decimal(
                site_row["methane_accumulated_emissions_to_date"])
            methane_limit = Decimal(site_row["methane_emission_limit"])
            new_site_total = previous_site_total + total_methane_value
            limit_exceeded = new_site_total > methane_limit

            response_message = (
                "Methane readings processed, but the configured site limit was exceeded"
                if limit_exceeded
                else "Methane readings processed successfully"
            )

            # Step 4: atomically update site total ingestions
            await conn.execute(
                """
                UPDATE sites
                SET
                    methane_accumulated_emissions_to_date = $1,
                    updated_at = NOW()
                WHERE site_id = $2
                  AND customer_id = $3
                """,
                new_site_total,
                dto.site_id,
                customer_id,
            )

            # Step 5: persist final response for duplicate replay
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

            # Step 6: log an audit event with all relevant details for this ingestion
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
                        "customer_id": str(customer_id),
                        "site_id": str(dto.site_id),
                        "ingestion_token": dto.ingestion_token,
                        "trace_request_id": dto.trace_request_id,
                        "request_fingerprint": request_fingerprint,
                        "received_record_count": received_record_count,
                        "processed_record_count": processed_record_count,
                        "batch_total_methane_value": float(total_methane_value),
                        "previous_site_total": float(previous_site_total),
                        "new_site_total": float(new_site_total),
                        "methane_emission_limit": float(methane_limit),
                        "limit_exceeded": limit_exceeded,
                    }
                ),
            )

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

    async def _find_existing_ingestion_job(
        self,
        conn: asyncpg.Connection,
        customer_id: UUID,
        site_id: UUID,
        ingestion_token: str,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT
                ingestion_job_id,
                customer_id,
                site_id,
                ingestion_token,
                trace_request_id,
                processing_status,
                received_record_count,
                processed_record_count,
                response_message,
                response_error_message,
                request_fingerprint
            FROM emission_ingestion_jobs
            WHERE customer_id = $1
              AND site_id = $2
              AND ingestion_token = $3
            """,
            customer_id,
            site_id,
            ingestion_token,
        )

    def _replay_or_conflict(
        self,
        existing_job: asyncpg.Record,
        request_fingerprint: str,
        dto: IngestBatchRequest,
        customer_id: UUID,
    ) -> IngestBatchResponse:
        """
        Replay a completed ingestion when the same ingestion_token is submitted.
        If the ingestion_token is reused with a different body, reject it.
        """
        if existing_job["request_fingerprint"] != request_fingerprint:
            raise MethaneIngestionTokenConflictError(dto.ingestion_token)

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
                or "Duplicate methane ingestion request replayed safely"
            ),
            response_error_message=existing_job["response_error_message"],
        )

    def _hash_request(self, dto: IngestBatchRequest) -> str:
        payload = {
            "site_id": str(dto.site_id),
            "ingestion_token": dto.ingestion_token,
            "trace_request_id": dto.trace_request_id,
            "readings": [
                {
                    "emission_value": str(reading.emission_value),
                    "emission_unit": reading.emission_unit.value,
                    "captured_at": reading.captured_at.isoformat(),
                }
                for reading in dto.readings
            ],
        }

        canonical_payload = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


# Module-level singleton.
# IngestService is stateless, so one shared instance is safe.
ingest_service = IngestService()