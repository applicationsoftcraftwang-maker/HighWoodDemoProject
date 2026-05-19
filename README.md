# Highwood Emissions Ingestion & Analytics Engine

🚧 **Work in progress** — see [ARCHITECTURE.md](./ARCHITECTURE.md) (coming in a later commit) for design decisions.

## Quick start (Postgres only at this stage)

```bash
cp .env.example .env
docker compose up -d postgres
```

Postgres will be available at `localhost:5432` with the credentials in `.env`.