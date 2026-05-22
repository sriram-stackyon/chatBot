"""
Project 12 — MCP-based Research Digest Agent.

Identical workflow to Project 10 (research_agent.py) but Node 3
calls the arXiv MCP server instead of a local Python function.
Only the tool layer differs; orchestration, prompts, and LLM calls
are equivalent to Project 10.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.schemas.research import ConversationMessage
from app.services.mcp_client import ArxivPaperMcp, mcp_search_arxiv

logger = logging.getLogger(__name__)

# ── Prompts (identical to Project 10) ─────────────────────────────────────────

_DIGEST_SYSTEM_PROMPT = """\
You are an expert AI Research Analyst. You analyze arXiv papers and produce comprehensive, \
well-structured research digests that are accurate, insightful, and actionable.

Always structure your digest EXACTLY as follows (use the markdown headers as shown):

# Research Digest: {topic}

## 1. Topic Overview
Provide a 2–3 paragraph overview of the research area, why it matters, and the current state of the field.

## 2. Key Findings
List 6–10 key findings across all the papers. Use bullet points. Cite paper titles where relevant.

## 3. Important Papers
For each significant paper, use this format:
**[Title](arxiv_url)** — Authors — Date
> 2–3 sentence summary of the paper's contribution and methodology.
📄 [Download PDF](pdf_url)

## 4. Technical Insights
Deep technical analysis of methods, architectures, benchmarks, algorithms, and innovations found in the papers.

## 5. Research Trends
Emerging patterns, convergence of ideas, and research directions observed across the papers.

## 6. Limitations
Current limitations, open challenges, reproducibility concerns, and gaps in the literature.

## 7. Future Scope
Promising future research directions, open problems, and applications based on the papers.

## 8. Final Summary
A concise 2–3 paragraph synthesizing summary of the research landscape and takeaways.

Rules:
- Use markdown formatting throughout (bold, italics, bullet points, headers).
- Always hyperlink paper titles with their arXiv URLs.
- Always include PDF download links.
- Be thorough, accurate, and insightful — not generic.
- Do not fabricate papers, authors, or findings not present in the provided abstracts.\
"""

_EVALUATION_PROMPT = """\
Research query: "{query}"

I found {num_papers} papers so far:
{titles}

Should I search arXiv for additional papers with different keywords to better cover this query?
- If YES, respond with exactly: SEARCH: <specific search keywords>
- If NO, respond with exactly: SUFFICIENT

Only request an additional search if there is clearly an important aspect of the query not addressed by the current papers.\
"""


# ── Helpers ───────────────────────────────────────────────────────────────────


def _sse(event_type: str, data: dict) -> str:
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


def _format_papers_for_prompt(papers: list[ArxivPaperMcp]) -> str:
    parts: list[str] = []
    for i, p in enumerate(papers, 1):
        authors = ", ".join(p.authors[:3])
        if len(p.authors) > 3:
            authors += " et al."
        parts.append(
            f"[{i}] {p.title}\n"
            f"    Authors: {authors} | Published: {p.published}\n"
            f"    arXiv: {p.arxiv_url}\n"
            f"    PDF: {p.pdf_url}\n"
            f"    Abstract: {p.summary[:600]}\n"
        )
    return "\n".join(parts)


# ── Main agent ────────────────────────────────────────────────────────────────


async def run_research_mcp_stream(
    query: str,
    max_papers: int,
    conversation_history: list[ConversationMessage],
    user_email: str,
) -> AsyncIterator[str]:
    """
    MCP-based autonomous research loop with real-time SSE streaming.

    Identical to Project 10's run_research_stream except arXiv is
    queried via the MCP server instead of a direct Python function call.

    Yields SSE-formatted event strings with type:
      status  — progress message
      papers  — list of paper dicts
      chunk   — partial digest text
      done    — research complete
      error   — error message
    """
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        openai_api_key=settings.LLM_API_KEY,
        openai_api_base=settings.LLM_API_BASE,
        temperature=0.3,
        max_tokens=4096,
        streaming=True,
    )

    # ── Node 1: Accept topic / Node 2: Initial search via MCP ────────────────
    yield _sse("status", {"message": f"🔍 Calling arXiv via MCP: {query}"})

    try:
        papers = await mcp_search_arxiv(query, min(max_papers, 8))
    except RuntimeError as exc:
        yield _sse("error", {"message": f"MCP server error: {exc}"})
        return

    if not papers:
        yield _sse("status", {"message": "⚠️ No papers found. Try a different or broader query."})
        yield _sse("done", {})
        return

    yield _sse("status", {"message": f"📄 Found {len(papers)} papers via MCP. Evaluating coverage…"})
    yield _sse("papers", {"papers": [asdict(p) for p in papers]})

    # ── Node 5: Evaluate evidence sufficiency (LLM, conditional edge) ────────
    try:
        titles_text = "\n".join(f"- {p.title}" for p in papers)
        eval_response = await llm.ainvoke(
            [
                HumanMessage(
                    content=_EVALUATION_PROMPT.format(
                        query=query,
                        num_papers=len(papers),
                        titles=titles_text,
                    )
                )
            ]
        )
        eval_text = str(eval_response.content).strip()

        if eval_text.upper().startswith("SEARCH:"):
            # ── Node 6: Refine and re-search via MCP ─────────────────────────
            extra_query = eval_text[7:].strip()
            if extra_query:
                yield _sse("status", {"message": f"🔎 Additional MCP search: {extra_query}"})
                try:
                    extra_papers = await mcp_search_arxiv(extra_query, 6)
                except RuntimeError as exc:
                    logger.warning("MCP additional search failed: %s", exc)
                    extra_papers = []
                seen_ids = {p.arxiv_id for p in papers}
                new_papers = [p for p in extra_papers if p.arxiv_id not in seen_ids]
                if new_papers:
                    papers.extend(new_papers)
                    yield _sse("papers", {"papers": [asdict(p) for p in papers]})
                    yield _sse(
                        "status",
                        {"message": f"📄 Total: {len(papers)} papers collected via MCP. Analyzing…"},
                    )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Evaluation step skipped: %s", exc)

    # ── Node 7: Generate structured digest ────────────────────────────────────
    yield _sse("status", {"message": "🧠 Generating research digest…"})

    system_content = _DIGEST_SYSTEM_PROMPT.replace("{topic}", query)
    messages: list = [SystemMessage(content=system_content)]

    for hist in conversation_history[-6:]:
        if hist.role == "user":
            messages.append(HumanMessage(content=hist.content))
        elif hist.role == "assistant":
            messages.append(AIMessage(content=hist.content))

    papers_section = _format_papers_for_prompt(papers)
    user_prompt = (
        f"Research Query: {query}\n\n"
        f"Papers ({len(papers)} total, retrieved via MCP arXiv server):\n\n"
        f"{papers_section}\n\n"
        "Generate the complete Research Digest now, following the required format exactly. "
        "Include clickable links for all papers."
    )
    messages.append(HumanMessage(content=user_prompt))

    # ── Node 8: Stream progress ───────────────────────────────────────────────
    try:
        async for chunk in llm.astream(messages):
            text = getattr(chunk, "content", "")
            if text:
                yield _sse("chunk", {"text": text})
    except Exception as exc:  # noqa: BLE001
        logger.exception("Digest streaming failed")
        yield _sse("error", {"message": f"Digest generation failed: {exc}"})
        return

    yield _sse("done", {})
