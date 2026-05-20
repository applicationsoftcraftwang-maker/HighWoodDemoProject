> **Disclosure:** This document was revised with assistance from an AI tool and then reviewed for accuracy and alignment with this solution.
>
> 
# Highwood Emissions Ingestion & Analytics Engine

A full-stack emissions monitoring solution built with **FastAPI**, **PostgreSQL**, and **React**. The platform focuses on safe data ingestion, tenant isolation, duplicate protection, and a clean operator dashboard for reviewing sites, metrics, and manual ingestion results.

> The preferred backend stack for the role is NestJS. I used FastAPI because the main engineering challenge is ingestion correctness: idempotency, PostgreSQL transactions, concurrency control, and reliable auditability. The same design can be implemented in NestJS with Prisma, Drizzle, or node-postgres.

---

## What this solution demonstrates

- Durable idempotency using `(tenant_id, site_id, idempotency_key)`
- Request-hash conflict detection for reused keys with different payloads
- Cached duplicate response replay from PostgreSQL
- Pessimistic row locking with `SELECT ... FOR UPDATE`
- Atomic writes for measurements, site totals, audit logs, and outbox events
- Monthly partitioning for high-volume measurement data
- Tenant-scoped data access through an explicit FastAPI dependency
- Unified API response envelope for success and error responses
- React dashboard with site list, metrics, ingestion form, and connection status
- Docker Compose setup for local evaluation

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI, Uvicorn, Pydantic v2 |
| Database | PostgreSQL, asyncpg |
| Frontend | React, TypeScript, Vite |
| Client state | TanStack Query, Zustand |
| Styling | CSS modules / app-level CSS |
| Runtime | Docker, Docker Compose |
| Testing | pytest, pytest-asyncio |

---

## Live deployment

The web application is now live and available for review.

```text
Frontend: https://high-wood-demo-project.vercel.app/
Swagger:  https://highwooddemoproject-production.up.railway.app/api/docs
API:      https://highwooddemoproject-production.up.railway.app/api/v1/health
Backend:  https://highwooddemoproject-production.up.railway.app
SourceCode: https://github.com/applicationsoftcraftwang-maker/HighWoodDemoProject  
```

The backend is deployed on Railway with PostgreSQL, and the frontend is deployed on Vercel. The Railway service runs the FastAPI app on the platform-provided runtime port, currently exposed internally on port `8080`.

---

## Quick start

From the project root:

```bash
cp .env.example .env
docker compose up -d --build
```

Open locally:

```text
Frontend: http://localhost:5173
Swagger:  http://localhost:8000/api/docs
API:      http://localhost:8000/api/v1
```

Optional pgAdmin:

```bash
docker compose --profile tools up -d
```

```text
pgAdmin: http://localhost:5050
```

---

## Local development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL=postgresql://emissions:emissions@localhost:5432/emissions
export RUN_MIGRATIONS=true

uvicorn app.main:app --reload --port 8000
```

The application runs migrations and seed data on startup when `RUN_MIGRATIONS=true`.

### Frontend

```bash
cd frontend
cp .env.example .env.local
npm ci
npm run dev
```

Expected frontend environment:

```env
VITE_API_URL=http://localhost:8000/api/v1
VITE_TENANT_ID=00000000-0000-0000-0000-000000000001
```

---

## How to evaluate the app

1. Start the stack with Docker Compose.
2. Open the dashboard at `http://localhost:5173`.
3. Select one of the seeded sites.
4. Submit a measurement batch from the ingestion form.
5. Submit the same batch again with the same idempotency key.
6. Confirm the second request returns `duplicate` and does not increase the site total.
7. Change the payload but reuse the same idempotency key.
8. Confirm the API returns `409 IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD`.

---

## Main API endpoints

All routes are under `/api/v1`.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/sites` | List tenant-scoped sites |
| `POST` | `/sites` | Create a monitoring site |
| `GET` | `/sites/{site_id}` | Get site details |
| `GET` | `/sites/{site_id}/metrics` | Get site emission metrics |
| `POST` | `/ingest` | Submit a measurement batch |
| `GET` | `/ingest/stats` | Get ingestion counters |

The API accepts `X-Tenant-Id`. If omitted, the app uses a demo tenant for local development.

---

## Example ingestion request

```json
{
  "site_id": "<site-uuid>",
  "idempotency_key": "batch-001",
  "measurements": [
    {
      "value": 42.5,
      "unit": "kg",
      "recorded_at": "2026-01-15T14:30:00Z"
    }
  ]
}
```

Idempotency behavior:

| Request pattern | Result |
|---|---|
| New key | `200`, status `processed` |
| Same key, same body | `200`, status `duplicate` |
| Same key, different body | `409 IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD` |

---

## Run tests

Backend tests require PostgreSQL because the suite validates real transaction, locking, foreign-key, and unique-constraint behavior.

```bash
docker compose up -d postgres

cd backend
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql://emissions:emissions@localhost:5432/emissions

python -m app.db.migrate
pytest -v
```

Frontend verification:

```bash
cd frontend
npm run lint
npm run build
```

---

## Implemented production patterns

- Tenant-scoped idempotency and duplicate replay
- Request-hash validation for conflict detection
- Deadlock-safe transaction order: site lock first, then FK-bearing inserts
- Monthly partitioned `measurements` table
- Transactional outbox foundation for downstream notifications
- Tenant-scoped audit logs
- Unified `{ success, data | error, meta }` response format
- OpenAPI documentation at `/api/docs`
- Dockerized local environment
- React operator dashboard

---

## Known production follow-ups

The current implementation is intentionally scoped for a take-home project. In production, I would add:

- JWT/OIDC authentication instead of demo `X-Tenant-Id`
- OpenAPI-generated TypeScript types
- Real outbox dispatch to Kafka, SNS, SQS, or webhooks
- Scheduled partition creation through `pg_cron` or an app scheduler
- API gateway rate limiting
- Centralized metrics and tracing
- Hardened production deployment configuration for long-term operations
