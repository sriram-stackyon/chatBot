from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings


def _build_sync_db_url(database_url: str | None = None) -> str:
    """Build a SQLAlchemy sync URL for reflection/tooling with psycopg2."""
    source_url = (database_url or settings.DATABASE_URL or "").strip()
    if not source_url:
        raise RuntimeError("DATABASE_URL is not configured")

    if source_url.startswith("postgresql+asyncpg://"):
        return source_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if source_url.startswith("postgres+asyncpg://"):
        return source_url.replace("postgres+asyncpg://", "postgresql+psycopg2://", 1)
    if source_url.startswith("postgresql://"):
        return source_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if source_url.startswith("postgres://"):
        return source_url.replace("postgres://", "postgresql+psycopg2://", 1)
    return source_url


@contextmanager
def get_db_cursor() -> Iterator[psycopg.Cursor]:
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")

    with psycopg.connect(settings.DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()
