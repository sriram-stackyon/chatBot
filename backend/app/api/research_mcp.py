"""FastAPI routes for Project 12 — MCP-based Research Digest Agent."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.ai.agents.research_mcp_agent import run_research_mcp_stream
from app.api.deps import get_current_user
from app.schemas.auth import AuthUser
from app.schemas.research import ResearchQueryRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["research-mcp"])


@router.post("/research-mcp/query", response_class=StreamingResponse)
async def research_mcp_query(
    request: ResearchQueryRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> StreamingResponse:
    """
    Stream a research digest via Server-Sent Events using the MCP arXiv server.

    Identical interface to /api/research/query (Project 10) but the arXiv
    tool calls are routed through the MCP server instead of direct Python calls.

    Each event is a JSON line:  ``data: {"type": "...", ...}\\n\\n``

    Event types:
    - ``status``  — progress message (``message`` field)
    - ``papers``  — found papers list (``papers`` field)
    - ``chunk``   — partial digest text (``text`` field)
    - ``done``    — stream finished
    - ``error``   — error message (``message`` field)
    """

    async def event_generator():
        try:
            async for event in run_research_mcp_stream(
                query=request.query,
                max_papers=request.max_papers,
                conversation_history=request.conversation_history,
                user_email=current_user.email or "",
            ):
                yield event
        except Exception as exc:  # noqa: BLE001
            logger.exception("Research MCP stream top-level error")
            payload = json.dumps({"type": "error", "message": str(exc)})
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
