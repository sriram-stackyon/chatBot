"""
Rate Limiting Middleware
Implements request rate limiting and token quota management
"""

import logging
from datetime import datetime, timedelta
from typing import Callable, Coroutine, Any

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.db.postgres import get_db_cursor
from app.services.auth_service import verify_access_token

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for API requests.
    Tracks requests per minute and token quota per day.
    """
    _rate_limits_table_warned = False
    _token_usage_table_warned = False
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Coroutine[Any, Any, Any]],
    ) -> Any:
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)
        
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)
        
        # Get user ID from token
        user_id = self._extract_user_id(request)
        if not user_id:
            return await call_next(request)
        
        # Check rate limits
        if not self._check_rate_limits(user_id):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
            )
        
        # Log request
        self._log_request(user_id, request)
        
        return await call_next(request)
    
    @staticmethod
    def _extract_user_id(request: Request) -> str | None:
        """Extract user ID from JWT token in Authorization header."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header[7:]
        try:
            user = verify_access_token(token)
            return user.user_id
        except Exception:
            return None
        return None
    
    @staticmethod
    def _check_rate_limits(user_id: str) -> bool:
        """Check if user is within rate limits."""
        try:
            with get_db_cursor() as cursor:
                # Rate limit checks should be resilient during partial schema rollout.
                cursor.execute("select to_regclass('public.rate_limits') as table_name")
                rate_limits_exists = bool((cursor.fetchone() or {}).get("table_name"))

                # Check requests per minute
                if rate_limits_exists:
                    minute_ago = datetime.now() - timedelta(minutes=1)
                    cursor.execute("""
                        select count(*) as count
                        from public.rate_limits
                        where user_id = %s and created_at >= %s
                    """, (user_id, minute_ago))

                    row = cursor.fetchone()
                    if row and row["count"] >= settings.RATE_LIMIT_REQUESTS_PER_MINUTE:
                        logger.warning(
                            "Rate limit exceeded for user=%s (requests/min)",
                            user_id,
                        )
                        return False
                elif not RateLimitMiddleware._rate_limits_table_warned:
                    logger.warning(
                        "Skipping request/minute limit because public.rate_limits table is missing"
                    )
                    RateLimitMiddleware._rate_limits_table_warned = True
                
                # Check token quota per day
                cursor.execute("select to_regclass('public.token_usage') as table_name")
                token_usage_exists = bool((cursor.fetchone() or {}).get("table_name"))

                if token_usage_exists:
                    day_ago = datetime.now() - timedelta(days=1)
                    cursor.execute("""
                        select coalesce(sum(tokens_used), 0) as total
                        from public.token_usage
                        where user_id = %s and created_at >= %s
                    """, (user_id, day_ago))

                    row = cursor.fetchone()
                    if row and row["total"] >= settings.RATE_LIMIT_TOKENS_PER_DAY:
                        logger.warning(
                            "Token quota exceeded for user=%s (tokens/day)",
                            user_id,
                        )
                        return False
                elif not RateLimitMiddleware._token_usage_table_warned:
                    logger.warning(
                        "Skipping tokens/day limit because public.token_usage table is missing"
                    )
                    RateLimitMiddleware._token_usage_table_warned = True
                
                return True
        except Exception:
            logger.exception("Error checking rate limits for user=%s", user_id)
            # Fail open - don't block if check fails
            return True
    
    @staticmethod
    def _log_request(user_id: str, request: Request) -> None:
        """Log request for rate limiting tracking."""
        try:
            with get_db_cursor() as cursor:
                # Create table if not exists
                cursor.execute("""
                    create table if not exists public.rate_limits (
                        id uuid primary key default gen_random_uuid(),
                        user_id uuid not null,
                        method varchar(10),
                        path varchar(255),
                        created_at timestamp default now()
                    );
                    create index if not exists idx_rate_limits_user on public.rate_limits(user_id);
                    create index if not exists idx_rate_limits_date on public.rate_limits(created_at);
                """)
                
                cursor.execute("""
                    insert into public.rate_limits(user_id, method, path)
                    values (%s, %s, %s)
                """, (user_id, request.method, request.url.path))
        except Exception:
            logger.exception("Error logging rate limit request for user=%s", user_id)
