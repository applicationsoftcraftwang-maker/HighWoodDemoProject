from __future__ import annotations
import asyncio
import os
from datetime import date, datetime

import asyncpg
from dateutil.relativedelta import relativedelta

DEMO_CUSTOMER_ID = "00000000-0000-0000-0000-000000000001"

CREATE_TABLES_SQL = """
-- sites
CREATE TABLE IF NOT EXISTS sites (
    site_id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL,
    site_name VARCHAR(255) NOT NULL,
    site_location VARCHAR(255) NOT NULL,
    methane_emission_limit NUMERIC(12, 2) NOT NULL,
    methane_accumulated_emissions_to_date NUMERIC(14, 2) NOT NULL DEFAULT 0,
    site_metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sites_customer_id ON sites (customer_id);

CREATE TABLE IF NOT EXISTS methane_emission_readings (
    reading_id UUID NOT NULL DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL,
    site_id UUID NOT NULL REFERENCES sites(site_id) ON DELETE CASCADE,
    emission_value NUMERIC(12, 4) NOT NULL,
    emission_unit VARCHAR(50) NOT NULL DEFAULT 'kg',
    ingestion_job_id UUID NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (reading_id, captured_at)
) PARTITION BY RANGE (captured_at);

CREATE INDEX IF NOT EXISTS idx_methane_emission_readings_site_id
ON methane_emission_readings (site_id);

CREATE INDEX IF NOT EXISTS idx_methane_emission_readings_customer_id
ON methane_emission_readings (customer_id);

CREATE INDEX IF NOT EXISTS idx_methane_emission_readings_ingestion_job_id
ON methane_emission_readings (ingestion_job_id);

CREATE INDEX IF NOT EXISTS idx_methane_emission_readings_customer_site_id
ON methane_emission_readings (customer_id, site_id);

CREATE TABLE IF NOT EXISTS emission_ingestion_jobs (
    ingestion_job_id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL,
    site_id UUID NOT NULL
        REFERENCES sites(site_id)
        ON DELETE CASCADE,
    processing_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    received_record_count INT NOT NULL DEFAULT 0,
    processed_record_count INT NOT NULL DEFAULT 0,
    ingestion_token VARCHAR(255) NOT NULL,
    trace_request_id VARCHAR(255) NOT NULL,
    response_message TEXT,
    response_error_message TEXT,
    request_fingerprint VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_emission_ingestion_token
    UNIQUE (
        customer_id,
        site_id,
        ingestion_token
    )
);

CREATE INDEX IF NOT EXISTS idx_emission_ingestion_jobs_customer_id
ON emission_ingestion_jobs (customer_id);

CREATE INDEX IF NOT EXISTS idx_emission_ingestion_jobs_site_id
ON emission_ingestion_jobs (site_id);

CREATE TABLE IF NOT EXISTS emission_notifications (
    notification_id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL,
    notification_category VARCHAR(50) NOT NULL,
    notification_message TEXT NOT NULL,
    is_acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_emission_notifications_acknowledged
ON emission_notifications (is_acknowledged)
WHERE is_acknowledged = FALSE;

CREATE INDEX IF NOT EXISTS idx_emission_notifications_customer_id
ON emission_notifications (customer_id);

CREATE TABLE IF NOT EXISTS emission_audit_events (
    audit_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL,
    performed_by VARCHAR(255),
    event_action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID,
    event_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_emission_audit_events_customer_created
ON emission_audit_events (
    customer_id,
    created_at DESC
);
"""
async def create_partition(
    conn: asyncpg.Connection,
    year: int,
    month: int
) -> None:
    """
    Create a monthly partition for methane_emission_readings.
    Safe to run multiple times.
    """
    partition_suffix = f"{year}_{month:02d}"
    partition_start = date(year, month, 1)
    partition_end = (
        date(year + 1, 1, 1)
        if month == 12
        else date(year, month + 1, 1)
    )

    sql = f"""
        CREATE TABLE IF NOT EXISTS methane_emission_readings_{partition_suffix}
        PARTITION OF methane_emission_readings
        FOR VALUES FROM ('{partition_start}')
        TO ('{partition_end}');
    """

    await conn.execute(sql)


async def run_migrations(conn: asyncpg.Connection) -> None:
    """
    Run all schema migrations.

    Partition strategy:
    - 6 months historical partitions
    - 12 months future partitions
    """

    await conn.execute(CREATE_TABLES_SQL)
    today = date.today()

    for offset in range(-6, 13):
        partition_date = today + relativedelta(months=offset)
        await create_partition(
            conn,
            partition_date.year,
            partition_date.month
        )

    partition_window_start = today + relativedelta(months=-6)
    partition_window_end = today + relativedelta(months=12)

    print(
        f"Migration complete "
        f"(partition window: "
        f"{partition_window_start} -> {partition_window_end})"
    )


async def seed(conn: asyncpg.Connection) -> None:
    """
    Insert initial demo customer + site data.
    Seed executes only once.
    """

    existing_site_count = await conn.fetchval(
        "SELECT COUNT(*) FROM sites"
    )

    if existing_site_count > 0:
        print("Seed data already exists - skipping")
        return

    await conn.execute(
        f"""
        INSERT INTO sites (
            customer_id,
            site_name,
            site_location,
            methane_emission_limit,
            site_metadata
        )
        VALUES
        (
            '{DEMO_CUSTOMER_ID}',
            'Highwood Well Pad Alpha',
            'Alberta, Canada',
            5000.00,
            '{{"operator":"Highwood Energy","site_type":"well_pad"}}'
        ),
        (
            '{DEMO_CUSTOMER_ID}',
            'Pembina Compressor Station',
            'Pembina, Alberta',
            8000.00,
            '{{"operator":"Pembina Pipeline","site_type":"compressor_station"}}'
        ),
        (
            '{DEMO_CUSTOMER_ID}',
            'Montney Gas Processing Facility',
            'Northeast BC, Canada',
            12000.00,
            '{{"operator":"Montney Resources","site_type":"gas_processing_facility"}}'
        )
        """
    )

    print(
        "Seed complete - "
        "3 methane emission monitoring sites created"
    )


async def main() -> None:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://emissions:emissions@localhost:5432/emissions"
    )

    conn = await asyncpg.connect(database_url)
    try:
        await run_migrations(conn)
        await seed(conn)
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())