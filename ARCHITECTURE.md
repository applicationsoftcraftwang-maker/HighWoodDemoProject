> **Disclosure:** This document was revised with assistance from an AI tool and then reviewed for accuracy and alignment with this solution.

# Architecture — Highwood Emissions Ingestion & Analytics Engine

## Overview

This solution is a modular full-stack emissions platform focused on ingestion correctness, auditability, and operational visibility.

The backend uses **FastAPI**, **asyncpg**, and **PostgreSQL**. The frontend uses **React**, **TypeScript**, and **Vite**. PostgreSQL is the source of truth for sites, measurements, idempotency records, audit logs, and Notification events.

The core design goal is simple: every measurement batch should be processed exactly once from the business perspective, even when clients retry, requests race, or the service restarts.

---

## High-level flow

```text
React Dashboard
      |
      v
FastAPI /api/v1
      |
      v
Tenant Resolver
      |
      v
Ingest Service
      |
      +--> PostgreSQL transaction
              |
              +--> Lock site row
              +--> Validate idempotency key
              +--> Insert measurements
              +--> Update site total
              +--> Write audit log
              +--> Write Notification event
```

---

## Main components

| Component | Responsibility |
|---|---|
| React dashboard | Site selection, metrics display, manual ingestion, API status |
| FastAPI routers | Versioned HTTP API under `/api/v1` |
| Tenant dependency | Resolves tenant from `X-Tenant-Id` or demo fallback |
| Ingest service | Owns idempotency, validation, locking, and transaction flow |
| PostgreSQL | Durable source of truth |
| Audit log | Persistent operational history |
| Notification processor | Reliable foundation for downstream event dispatch |

---

## Data model

### `sites`

Stores tenant-scoped monitoring sites, emission limits, total emissions, status, and version metadata.

### `measurements`

Stores individual measurement rows. The table is partitioned monthly by `recorded_at` to support higher data volume and date-range queries.

### `ingest_batches`

Stores idempotency records. Each record includes the tenant, site, idempotency key, request hash, measurement count, batch total, and cached response payload.

### `audit_logs`

Stores tenant-scoped operational history for ingestion and site changes.

### `Notification_events`

Stores events produced inside the same database transaction as the ingestion workflow.

---

## Idempotency design

The ingestion endpoint supports three required cases:

| Case | Result |
|---|---|
| New idempotency key | Process the batch |
| Same key and same payload | Return cached duplicate response |
| Same key and different payload | Return `409 IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD` |

The uniqueness rule is tenant and site scoped:

```sql
UNIQUE (tenant_id, site_id, idempotency_key)
```

This avoids false conflicts between different tenants or sites that may generate the same client-side key.

A SHA-256 hash of the canonical request body is stored as `request_hash`. This allows the service to detect whether a retry is a true duplicate or a key reuse bug.

---

## Transaction strategy

The ingest workflow is executed inside a single PostgreSQL transaction.

Final transaction order:

```text
1. Pre-check existing idempotency record
2. BEGIN
3. SELECT site FOR UPDATE
4. INSERT ingest batch placeholder
5. INSERT measurements
6. UPDATE site total and status
7. UPDATE ingest batch response payload
8. INSERT audit log
9. INSERT Notification event
10. COMMIT
```

The important decision is step 3: the service locks the site row before inserting rows that reference it.

This prevents a PostgreSQL lock-upgrade deadlock that can happen when concurrent transactions first insert foreign-key rows and then later try to upgrade to `FOR UPDATE` on the same parent site row.

---

## Concurrency control

Concurrent batches for the same site are serialized by:

```sql
SELECT ... FROM sites WHERE id = $1 AND tenant_id = $2 FOR UPDATE
```

This prevents lost updates when multiple batches try to update the same site total at the same time.

Batches for different sites can still proceed independently.

---

## Atomicity

The following changes are committed together:

- Ingest batch record
- Measurement rows
- Site total update
- Site status update
- Audit log
- Notification event

If any step fails, the full transaction rolls back. This keeps totals, measurements, duplicate replay, and audit history consistent.

---

## Notification pattern

The Notification event is written in the same transaction as the measurement data. This guarantees that a committed ingestion event is never lost simply because the process crashes before sending a downstream notification.

The background processor reads unprocessed rows using:

```sql
FOR UPDATE SKIP LOCKED
```

This allows multiple service instances to process Notification records safely. The current dispatcher is intentionally stubbed for the take-home; in production it can publish to Kafka, SNS, SQS, webhooks, or an internal notification service.

---

## Partitioning strategy

The `measurements` table is range-partitioned by month on `recorded_at`.

Benefits:

- Faster date-range queries through partition pruning
- Easier archival of old data
- Smaller indexes per partition
- Better long-term maintenance for high-volume sensor data

The migration creates a rolling partition window around the current date. In production, a scheduled job would keep future partitions available.

---

## Tenant isolation

Every core table includes `tenant_id`.

Every query is scoped by tenant. The API receives the tenant through a FastAPI dependency, making tenant access explicit in each route.

For the take-home, the tenant comes from `X-Tenant-Id` with a demo fallback. In production, this would be replaced with JWT/OIDC claim validation while keeping the service contract unchanged.

---

## API design

All routes are versioned under:

```text
/api/v1
```

Response shape is consistent across the API:

```json
{
  "success": true,
  "data": {},
  "meta": {
    "timestamp": "...",
    "version": "v1"
  }
}
```

Errors use the same envelope:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Readable message"
  },
  "meta": {
    "timestamp": "...",
    "version": "v1"
  }
}
```

---

## Frontend architecture

The frontend is a small operator dashboard built with React and TypeScript.

Main responsibilities:

- Display seeded and newly created sites
- Show site metrics and compliance status
- Submit manual ingestion batches
- Surface duplicate/conflict behavior clearly
- Show API connection status
- Use environment-based API configuration

Key frontend pieces:

| Area | Implementation |
|---|---|
| API client | Typed fetch wrapper with tenant header |
| Server state | TanStack Query |
| Local UI state | Zustand |
| Validation | Zod / TypeScript models |
| Build tooling | Vite |

---

## Testing strategy

The backend test suite uses real PostgreSQL instead of database mocks because the most important behavior depends on PostgreSQL semantics:

- Row locks
- Foreign-key validation
- Unique constraints
- Transaction rollback
- Concurrent requests

Important scenarios covered:

- New ingestion batch
- Duplicate replay
- Same key with different payload conflict
- Unknown site
- Tenant isolation
- Batch validation
- Concurrent unique batches
- Concurrent duplicate batches
- Stats counters
- Unified response envelope

---

## Current scope

Implemented:

- FastAPI backend
- PostgreSQL schema and migrations
- Tenant-scoped ingestion
- Durable idempotency
- Concurrent-safe site total updates
- Monthly measurement partitions
- Audit log
- Transactional Notification foundation
- React dashboard
- Docker Compose setup
- Backend tests and frontend build/lint workflow

Intentionally deferred:

- Production authentication
- API gateway and rate limiting
- Real message broker dispatch
- OpenAPI-generated frontend types
- Centralized tracing and metrics
- Cloud deployment pipeline

---

## Evolution path

The current design is a modular monolith. That is intentional for a take-home: it keeps the solution easy to run and review while preserving clear future service boundaries.

A production version could split into:

```text
API Gateway
   |
   +--> Ingestion Service
   +--> Compliance Rules Service
   +--> Reporting API
   +--> Notification Service
            ^
            |
        Notification / Event Bus
```

The current Notification table is the bridge toward that architecture.
