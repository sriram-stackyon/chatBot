from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


def _get_supabase_key() -> str:
    # Prefer service role key for backend persistence operations.
    return settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    supabase_url = settings.get_supabase_url()
    if not supabase_url:
        raise RuntimeError("SUPABASE_URL is not configured")

    key = _get_supabase_key()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY must be configured")

    return create_client(supabase_url, key)
