"""
Token Usage Tracking
Tracks and logs token usage for billing and monitoring
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.db.postgres import get_db_cursor

logger = logging.getLogger(__name__)


def log_token_usage(
    user_id: str,
    tokens_used: int,
    operation_type: str = "chat",
    model: str = "gpt-4",
    details: dict = None,
) -> bool:
    """
    Log token usage for a user.
    
    Args:
        user_id: User ID
        tokens_used: Number of tokens used
        operation_type: Type of operation (chat, summarization, etc)
        model: Model used
        details: Additional details (optional)
        
    Returns:
        Success flag
    """
    try:
        with get_db_cursor() as cursor:
            # Create table if not exists
            cursor.execute("""
                create table if not exists public.token_usage (
                    id uuid primary key default gen_random_uuid(),
                    user_id uuid not null,
                    tokens_used int not null,
                    operation_type varchar(50),
                    model varchar(100),
                    details jsonb,
                    created_at timestamp default now()
                );
                create index if not exists idx_token_usage_user on public.token_usage(user_id);
                create index if not exists idx_token_usage_date on public.token_usage(created_at);
            """)
            
            cursor.execute("""
                insert into public.token_usage(user_id, tokens_used, operation_type, model, details)
                values (%s, %s, %s, %s, %s)
            """, (user_id, tokens_used, operation_type, model, details))
        
        logger.debug(
            "Logged %d tokens for user=%s operation=%s model=%s",
            tokens_used,
            user_id,
            operation_type,
            model,
        )
        return True
    except Exception as e:
        logger.exception("Error logging token usage for user=%s", user_id)
        return False


def get_token_usage_stats(
    user_id: str,
    days: int = 30,
) -> dict:
    """
    Get token usage statistics for a user.
    
    Args:
        user_id: User ID
        days: Number of days to look back
        
    Returns:
        Dictionary with usage stats
    """
    try:
        with get_db_cursor() as cursor:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            cursor.execute("""
                select
                    coalesce(sum(tokens_used), 0) as total_tokens,
                    count(*) as request_count,
                    max(tokens_used) as max_request_tokens,
                    avg(tokens_used) as avg_request_tokens
                from public.token_usage
                where user_id = %s and created_at >= %s
            """, (user_id, cutoff_date))
            
            row = cursor.fetchone()
            
            if row:
                return {
                    "total_tokens": row["total_tokens"],
                    "request_count": row["request_count"],
                    "max_request_tokens": row["max_request_tokens"],
                    "avg_request_tokens": round(row["avg_request_tokens"], 2) if row["avg_request_tokens"] else 0,
                    "period_days": days,
                }
        
        return {
            "total_tokens": 0,
            "request_count": 0,
            "max_request_tokens": 0,
            "avg_request_tokens": 0,
            "period_days": days,
        }
    except Exception as e:
        logger.exception("Error fetching token usage stats for user=%s", user_id)
        return {}


def get_token_usage_by_operation(
    user_id: str,
    days: int = 30,
) -> dict:
    """
    Get token usage breakdown by operation type.
    
    Args:
        user_id: User ID
        days: Number of days to look back
        
    Returns:
        Dictionary with usage by operation type
    """
    try:
        with get_db_cursor() as cursor:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            cursor.execute("""
                select
                    operation_type,
                    sum(tokens_used) as tokens,
                    count(*) as count
                from public.token_usage
                where user_id = %s and created_at >= %s
                group by operation_type
                order by tokens desc
            """, (user_id, cutoff_date))
            
            rows = cursor.fetchall()
            
            return {
                row["operation_type"]: {
                    "tokens": row["tokens"],
                    "count": row["count"],
                }
                for row in rows
            }
    except Exception as e:
        logger.exception("Error fetching operation-wise token usage for user=%s", user_id)
        return {}
