# Alembic Migrations (Supabase Postgres)

This project uses Alembic to migrate the Supabase-hosted PostgreSQL schema.

## Prerequisites

- `DATABASE_URL` must be set in `backend/.env`.
- Install dependencies from `backend/requirements.txt`.

## Run migrations

From the `backend` directory:

```bash
alembic upgrade head
```

## Create a new migration

```bash
alembic revision -m "describe_change"
```

Then edit the generated file under `alembic/versions/` and apply with:

```bash
alembic upgrade head
```
