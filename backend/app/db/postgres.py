from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings


@contextmanager
def get_db_cursor() -> Iterator[psycopg.Cursor]:
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")

    with psycopg.connect(settings.DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()
