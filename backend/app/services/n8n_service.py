"""
n8n outgoing service — triggers n8n webhooks from the FastAPI backend.
Execution records are persisted to the public.workflow_executions table in
Supabase/Postgres.  Sync DB calls are wrapped in asyncio.to_thread so the
async event loop is never blocked.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.db.postgres import get_db_cursor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal DB helpers (sync — run via asyncio.to_thread)
# ---------------------------------------------------------------------------

def _insert_execution(
    exec_id: str,
    workflow_id: str,
    workflow_name: str,
    triggered_by: str,
) -> None:
    with get_db_cursor() as cur:
        cur.execute(
            """
            insert into public.workflow_executions
                (id, workflow_id, workflow_name, status, triggered_by, triggered_at)
            values (%s, %s, %s, 'running', %s, now())
            """,
            (exec_id, workflow_id, workflow_name, triggered_by),
        )


def _update_execution(
    exec_id: str,
    status: str,
    execution_time: str,
    response_data: Optional[Dict[str, Any]],
    error_message: Optional[str],
) -> None:
    with get_db_cursor() as cur:
        cur.execute(
            """
            update public.workflow_executions
               set status         = %s,
                   execution_time = %s,
                   response_data  = %s,
                   error_message  = %s
             where id = %s
            """,
            (
                status,
                execution_time,
                json.dumps(response_data) if response_data else None,
                error_message,
                exec_id,
            ),
        )


def _fetch_history(limit: int = 50) -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute(
            """
            select id::text,
                   workflow_name,
                   status,
                   triggered_at,
                   execution_time,
                   triggered_by
              from public.workflow_executions
             order by triggered_at desc
             limit %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    result = []
    for row in rows:
        triggered_at = row["triggered_at"]
        result.append(
            {
                "id": row["id"],
                "workflow_name": row["workflow_name"],
                "status": row["status"],
                "triggered_at": (
                    triggered_at.isoformat()
                    if isinstance(triggered_at, datetime)
                    else str(triggered_at)
                ),
                "execution_time": row["execution_time"],
                "triggered_by": row["triggered_by"],
            }
        )
    return result


def _fetch_stats(workflow_id: str = "ai-news-digest") -> Dict[str, Any]:
    with get_db_cursor() as cur:
        cur.execute(
            """
            select
                count(*)                                         as total,
                count(*) filter (where status = 'success')      as successful,
                count(*) filter (where status = 'failed')       as failed,
                max(triggered_at)                               as last_run
              from public.workflow_executions
             where workflow_id = %s
            """,
            (workflow_id,),
        )
        row = cur.fetchone() or {}

    total = int(row.get("total") or 0)
    successful = int(row.get("successful") or 0)
    failed = int(row.get("failed") or 0)
    last_run = row.get("last_run")

    return {
        "total_executions": total,
        "successful": successful,
        "failed": failed,
        "success_rate": round(successful / total * 100, 1) if total else 0.0,
        "last_run": (
            last_run.isoformat() if isinstance(last_run, datetime) else (str(last_run) if last_run else None)
        ),
    }


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def trigger_news_digest() -> Dict[str, Any]:
    """POST to the configured n8n webhook and persist the execution record."""
    webhook_url = settings.N8N_WEBHOOK_URL
    if not webhook_url:
        raise RuntimeError("N8N_WEBHOOK_URL is not configured")

    exec_id = str(uuid.uuid4())
    workflow_id = "ai-news-digest"
    workflow_name = "AI News Digest"
    triggered_by = "manual_user"
    payload: Dict[str, Any] = {
        "source": "vue_dashboard",
        "triggered_by": triggered_by,
    }

    # Insert "running" record before calling n8n
    await asyncio.to_thread(
        _insert_execution, exec_id, workflow_id, workflow_name, triggered_by
    )

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()

        elapsed = f"{time.monotonic() - start:.1f}s"

        try:
            data: Any = resp.json()
            if not isinstance(data, dict):
                data = {"result": data}
        except Exception:
            data = {}

        await asyncio.to_thread(
            _update_execution, exec_id, "success", elapsed, data, None
        )
        logger.info("n8n '%s' executed in %s", workflow_name, elapsed)

        return {
            "success": True,
            "message": "Workflow executed successfully",
            "execution_time": elapsed,
            "workflow": workflow_name,
            "data": data,
        }

    except httpx.TimeoutException:
        elapsed = f"{time.monotonic() - start:.1f}s"
        await asyncio.to_thread(
            _update_execution, exec_id, "failed", elapsed, None,
            "Request to n8n timed out"
        )
        logger.error("n8n webhook timed out after %s", elapsed)
        raise

    except httpx.HTTPStatusError as exc:
        elapsed = f"{time.monotonic() - start:.1f}s"
        msg = f"n8n returned HTTP {exc.response.status_code}"
        await asyncio.to_thread(
            _update_execution, exec_id, "failed", elapsed, None, msg
        )
        logger.error("%s: %s", msg, exc.response.text[:500])
        raise

    except Exception as exc:
        elapsed = f"{time.monotonic() - start:.1f}s"
        await asyncio.to_thread(
            _update_execution, exec_id, "failed", elapsed, None, str(exc)
        )
        logger.exception("Unexpected error calling n8n webhook")
        raise


async def get_execution_history(limit: int = 50) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(_fetch_history, limit)


async def get_workflow_stats(workflow_id: str = "ai-news-digest") -> Dict[str, Any]:
    return await asyncio.to_thread(_fetch_stats, workflow_id)


async def get_workflow_list() -> List[Dict[str, Any]]:
    stats = await get_workflow_stats("ai-news-digest")
    return [
        {
            "id": "ai-news-digest",
            "name": "AI News Digest",
            "status": "active",
            "trigger_type": "Webhook",
            "webhook_path": "/webhook-test/ai-news-digest",
            "last_execution": stats["last_run"],
            "execution_count": stats["total_executions"],
            "success_rate": stats["success_rate"],
        }
    ]

