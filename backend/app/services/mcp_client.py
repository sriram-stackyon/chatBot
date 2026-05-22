"""
MCP client for the arXiv MCP server — Project 12.

Connects to the public cyanheads/arxiv-mcp-server via Streamable HTTP transport.

  Registry server : https://arxiv.caseyjhand.com/mcp
  Rate limiting   : Handled server-side — 3 s crawl delay + adaptive cooldown on
                    HTTP 429 (5 s → 10 s → 20 s → 30 s), honors Retry-After.
  Auth required   : None (arXiv API is free / CC0).
  No local subprocess, no custom arXiv package needed.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Data model ────────────────────────────────────────────────────────────────


@dataclass
class ArxivPaperMcp:
    title: str
    authors: list[str]
    summary: str      # mapped from cyanheads "abstract" field
    published: str
    arxiv_url: str    # mapped from cyanheads "abstract_url" field
    pdf_url: str
    arxiv_id: str     # mapped from cyanheads "id" field


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
    timeout: float = 90.0,
) -> Any:
    """
    Call *tool_name* on the registry arXiv MCP server via Streamable HTTP.

    Returns ``result.structuredContent`` when the server populates it
    (MCP ≥ 1.2 structured output), otherwise JSON-parses the first text block.
    Raises ``RuntimeError`` on connection failures or tool-level errors.
    """
    url = settings.MCP_ARXIV_URL
    logger.info("[MCP-CLIENT] ▶ tool=%r  url=%s", tool_name, url)
    t0 = time.perf_counter()
    try:
        async with streamablehttp_client(url, timeout=30.0) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=15.0)
                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments=arguments),
                    timeout=timeout,
                )
                elapsed = time.perf_counter() - t0
                if result.isError:
                    err = result.content[0].text if result.content else repr(result)
                    raise RuntimeError(f"MCP tool '{tool_name}' returned error: {err}")
                # Prefer structured JSON output (MCP 1.2+ — cyanheads server supports it)
                if result.structuredContent:
                    logger.info("[MCP-CLIENT] ✔ tool=%r  %.2fs  (structured)", tool_name, elapsed)
                    return result.structuredContent
                # Fallback: first text content block
                if result.content:
                    try:
                        parsed = json.loads(result.content[0].text)
                        logger.info("[MCP-CLIENT] ✔ tool=%r  %.2fs  (json-text)", tool_name, elapsed)
                        return parsed
                    except (json.JSONDecodeError, AttributeError):
                        logger.warning("[MCP-CLIENT] ⚠ tool=%r returned non-JSON text", tool_name)
                        return {"_text": result.content[0].text}
                logger.warning("[MCP-CLIENT] ⚠ tool=%r returned empty result", tool_name)
                return None
    except RuntimeError:
        raise
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        logger.error(
            "[MCP-CLIENT] ✖ tool=%r  %.2fs  %s: %s",
            tool_name, elapsed, type(exc).__name__, exc,
        )
        raise RuntimeError(f"MCP tool '{tool_name}' failed: {exc}") from exc


def _paper_from_dict(item: dict[str, Any]) -> ArxivPaperMcp:
    """Map a cyanheads PaperMetadata dict → ArxivPaperMcp."""
    return ArxivPaperMcp(
        title=item.get("title", ""),
        authors=item.get("authors", []),
        summary=item.get("abstract", item.get("summary", "")),
        published=(item.get("published") or "").split("T")[0],
        arxiv_url=item.get("abstract_url", item.get("arxiv_url", "")),
        pdf_url=item.get("pdf_url", ""),
        arxiv_id=item.get("id", item.get("arxiv_id", "")),
    )


# ── Public API ────────────────────────────────────────────────────────────────


async def mcp_search_arxiv(query: str, max_results: int = 8) -> list[ArxivPaperMcp]:
    """Search arXiv via the registry MCP server.

    The cyanheads server handles arXiv rate limiting internally (3 s crawl
    delay + adaptive cooldown on 429) — no client-side retry loop needed.
    Response: ``{"total_results": N, "start": 0, "papers": [...]}``
    """
    logger.info("[MCP-CLIENT] mcp_search_arxiv  query=%r  max_results=%d", query, max_results)
    raw = await _call_mcp_tool("arxiv_search", {"query": query, "max_results": max_results})
    if not isinstance(raw, dict):
        logger.error("[MCP-CLIENT] Unexpected response type from arxiv_search: %r", type(raw))
        return []
    papers_raw = raw.get("papers", [])
    if not isinstance(papers_raw, list):
        return []
    papers = [_paper_from_dict(item) for item in papers_raw if isinstance(item, dict)]
    logger.info(
        "[MCP-CLIENT] mcp_search_arxiv  parsed %d/%s papers",
        len(papers), raw.get("total_results", "?"),
    )
    return papers


async def mcp_get_paper_details(arxiv_id: str) -> ArxivPaperMcp | None:
    """Fetch full paper metadata by arXiv ID via the registry MCP server.

    Uses ``arxiv_get_metadata`` with ``paper_ids`` (single string or list).
    Response: ``{"papers": [...], "not_found": [...]}``
    """
    raw = await _call_mcp_tool("arxiv_get_metadata", {"paper_ids": arxiv_id})
    if not isinstance(raw, dict):
        return None
    papers_raw = raw.get("papers", [])
    if not papers_raw:
        return None
    return _paper_from_dict(papers_raw[0])
