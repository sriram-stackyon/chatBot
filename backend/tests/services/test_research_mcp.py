"""Tests for Project 12 — MCP-based Research Digest Agent."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mcp_client import ArxivPaperMcp


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture()
def sample_papers() -> list[ArxivPaperMcp]:
    return [
        ArxivPaperMcp(
            title="Attention Is All You Need",
            authors=["Ashish Vaswani", "Noam Shazeer"],
            summary="We propose the Transformer, a model architecture based solely on attention.",
            published="2017-06-12",
            arxiv_url="https://arxiv.org/abs/1706.03762",
            pdf_url="https://arxiv.org/pdf/1706.03762",
            arxiv_id="1706.03762",
        ),
        ArxivPaperMcp(
            title="BERT: Pre-training of Deep Bidirectional Transformers",
            authors=["Jacob Devlin", "Ming-Wei Chang"],
            summary="We introduce BERT, designed to pre-train deep bidirectional representations.",
            published="2018-10-11",
            arxiv_url="https://arxiv.org/abs/1810.04805",
            pdf_url="https://arxiv.org/pdf/1810.04805",
            arxiv_id="1810.04805",
        ),
    ]


# ── Unit tests: MCP client ─────────────────────────────────────────────────────


class TestMcpSearchArxiv:
    """Tests for mcp_client.mcp_search_arxiv."""

    @pytest.mark.asyncio
    async def test_returns_papers_on_success(self, sample_papers: list[ArxivPaperMcp]) -> None:
        raw_payload = json.dumps(
            [
                {
                    "title": p.title,
                    "authors": p.authors,
                    "summary": p.summary,
                    "published": p.published,
                    "arxiv_url": p.arxiv_url,
                    "pdf_url": p.pdf_url,
                    "arxiv_id": p.arxiv_id,
                }
                for p in sample_papers
            ]
        )

        with patch(
            "app.services.mcp_client._call_mcp_tool",
            new=AsyncMock(return_value=json.loads(raw_payload)),
        ):
            from app.services.mcp_client import mcp_search_arxiv

            results = await mcp_search_arxiv("transformer", max_results=2)

        assert len(results) == 2
        assert results[0].arxiv_id == "1706.03762"
        assert results[1].title == "BERT: Pre-training of Deep Bidirectional Transformers"

    @pytest.mark.asyncio
    async def test_returns_empty_on_non_list_response(self) -> None:
        with patch(
            "app.services.mcp_client._call_mcp_tool",
            new=AsyncMock(return_value={"error": "something"}),
        ):
            from app.services.mcp_client import mcp_search_arxiv

            results = await mcp_search_arxiv("transformer")

        assert results == []

    @pytest.mark.asyncio
    async def test_raises_on_mcp_server_unreachable(self) -> None:
        with patch(
            "app.services.mcp_client._call_mcp_tool",
            new=AsyncMock(side_effect=RuntimeError("MCP server unreachable after 3 attempts")),
        ):
            from app.services.mcp_client import mcp_search_arxiv

            with pytest.raises(RuntimeError, match="MCP server unreachable"):
                await mcp_search_arxiv("transformer")


class TestMcpGetPaperDetails:
    """Tests for mcp_client.mcp_get_paper_details."""

    @pytest.mark.asyncio
    async def test_returns_paper_on_success(self) -> None:
        raw = {
            "title": "Attention Is All You Need",
            "authors": ["Ashish Vaswani"],
            "summary": "We propose the Transformer.",
            "published": "2017-06-12",
            "arxiv_url": "https://arxiv.org/abs/1706.03762",
            "pdf_url": "https://arxiv.org/pdf/1706.03762",
            "arxiv_id": "1706.03762",
        }
        with patch(
            "app.services.mcp_client._call_mcp_tool",
            new=AsyncMock(return_value=raw),
        ):
            from app.services.mcp_client import mcp_get_paper_details

            paper = await mcp_get_paper_details("1706.03762")

        assert paper is not None
        assert paper.arxiv_id == "1706.03762"

    @pytest.mark.asyncio
    async def test_returns_none_on_error_response(self) -> None:
        with patch(
            "app.services.mcp_client._call_mcp_tool",
            new=AsyncMock(return_value={"error": "Paper not found"}),
        ):
            from app.services.mcp_client import mcp_get_paper_details

            paper = await mcp_get_paper_details("9999.99999")

        assert paper is None


# ── Unit tests: MCP research agent ────────────────────────────────────────────


class TestRunResearchMcpStream:
    """Tests for research_mcp_agent.run_research_mcp_stream."""

    @pytest.mark.asyncio
    async def test_streams_status_papers_chunks_done(
        self, sample_papers: list[ArxivPaperMcp]
    ) -> None:
        async def _fake_stream(messages):
            chunk = MagicMock()
            chunk.content = "Digest content"
            yield chunk

        with (
            patch(
                "app.ai.agents.research_mcp_agent.mcp_search_arxiv",
                new=AsyncMock(return_value=sample_papers),
            ),
            patch(
                "app.ai.agents.research_mcp_agent.ChatOpenAI"
            ) as mock_llm_cls,
        ):
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(
                return_value=MagicMock(content="SUFFICIENT")
            )
            mock_llm.astream = _fake_stream
            mock_llm_cls.return_value = mock_llm

            from app.ai.agents.research_mcp_agent import run_research_mcp_stream

            events: list[str] = []
            async for ev in run_research_mcp_stream(
                query="transformer", max_papers=5, conversation_history=[], user_email="test@x.com"
            ):
                events.append(ev)

        event_types = []
        for ev in events:
            payload = ev.replace("data: ", "").strip()
            if payload:
                event_types.append(json.loads(payload).get("type"))

        assert "status" in event_types
        assert "papers" in event_types
        assert "chunk" in event_types
        assert "done" in event_types

    @pytest.mark.asyncio
    async def test_streams_error_when_mcp_unreachable(self) -> None:
        with patch(
            "app.ai.agents.research_mcp_agent.mcp_search_arxiv",
            new=AsyncMock(side_effect=RuntimeError("MCP server unreachable after 3 attempts")),
        ):
            from app.ai.agents.research_mcp_agent import run_research_mcp_stream

            events: list[str] = []
            async for ev in run_research_mcp_stream(
                query="transformer", max_papers=5, conversation_history=[], user_email="test@x.com"
            ):
                events.append(ev)

        error_events = [
            json.loads(ev.replace("data: ", "").strip())
            for ev in events
            if ev.strip()
        ]
        error_types = [e.get("type") for e in error_events]
        assert "error" in error_types

    @pytest.mark.asyncio
    async def test_streams_done_when_no_papers_found(self) -> None:
        with patch(
            "app.ai.agents.research_mcp_agent.mcp_search_arxiv",
            new=AsyncMock(return_value=[]),
        ):
            from app.ai.agents.research_mcp_agent import run_research_mcp_stream

            events: list[str] = []
            async for ev in run_research_mcp_stream(
                query="obscure topic xyz", max_papers=5, conversation_history=[], user_email="x"
            ):
                events.append(ev)

        types = [
            json.loads(ev.replace("data: ", "").strip()).get("type")
            for ev in events
            if ev.strip()
        ]
        assert "done" in types


# ── Unit tests: MCP server tools ──────────────────────────────────────────────


class TestArxivMcpServer:
    """Tests for the arXiv MCP server's tool implementations."""

    def test_search_arxiv_returns_list(self) -> None:
        from mcp_servers.arxiv_server import _search_arxiv

        with patch("mcp_servers.arxiv_server.arxiv") as mock_arxiv:
            mock_result = MagicMock()
            mock_result.entry_id = "https://arxiv.org/abs/1706.03762v5"
            mock_result.pdf_url = "https://arxiv.org/pdf/1706.03762"
            mock_result.title = "Attention Is All You Need"
            mock_result.authors = [MagicMock(name="Ashish Vaswani")]
            mock_result.summary = "Transformer paper."
            mock_result.published = MagicMock()
            mock_result.published.strftime.return_value = "2017-06-12"

            mock_client = MagicMock()
            mock_client.results.return_value = [mock_result]
            mock_arxiv.Client.return_value = mock_client
            mock_arxiv.Search.return_value = MagicMock()
            mock_arxiv.SortCriterion.Relevance = "relevance"

            papers = _search_arxiv("transformer", 1)

        assert len(papers) == 1
        assert papers[0].arxiv_id == "1706.03762"

    def test_get_paper_details_returns_paper(self) -> None:
        from mcp_servers.arxiv_server import _get_paper_details

        with patch("mcp_servers.arxiv_server.arxiv") as mock_arxiv:
            mock_result = MagicMock()
            mock_result.entry_id = "https://arxiv.org/abs/1706.03762v5"
            mock_result.pdf_url = "https://arxiv.org/pdf/1706.03762"
            mock_result.title = "Attention Is All You Need"
            mock_result.authors = [MagicMock(name="Ashish Vaswani")]
            mock_result.summary = "Transformer paper."
            mock_result.published = MagicMock()
            mock_result.published.strftime.return_value = "2017-06-12"

            mock_client = MagicMock()
            mock_client.results.return_value = [mock_result]
            mock_arxiv.Client.return_value = mock_client
            mock_arxiv.Search.return_value = MagicMock()

            paper = _get_paper_details("1706.03762")

        assert paper is not None
        assert paper.arxiv_id == "1706.03762"

    def test_get_paper_details_returns_none_on_empty(self) -> None:
        from mcp_servers.arxiv_server import _get_paper_details

        with patch("mcp_servers.arxiv_server.arxiv") as mock_arxiv:
            mock_client = MagicMock()
            mock_client.results.return_value = []
            mock_arxiv.Client.return_value = mock_client
            mock_arxiv.Search.return_value = MagicMock()

            paper = _get_paper_details("9999.99999")

        assert paper is None


# ── Authentication enforcement test ───────────────────────────────────────────


def test_research_mcp_endpoint_requires_auth() -> None:
    """Verify that /api/research-mcp/query returns 401/403 without a token."""
    import os

    os.environ.setdefault("LITELLM_PROXY_URL", "http://localhost:4000")
    os.environ.setdefault("LITELLM_API_KEY", "test-key")

    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/research-mcp/query",
        json={"query": "test", "max_papers": 3},
    )
    assert response.status_code in {401, 403, 422}
