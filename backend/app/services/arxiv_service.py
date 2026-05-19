from __future__ import annotations

import logging
from dataclasses import dataclass, field

import arxiv

logger = logging.getLogger(__name__)


@dataclass
class ArxivPaper:
    title: str
    authors: list[str]
    summary: str
    published: str
    arxiv_url: str
    pdf_url: str
    arxiv_id: str


def search_papers(query: str, max_results: int = 12) -> list[ArxivPaper]:
    """Search arXiv and return structured paper list.

    Runs synchronously — call via ``asyncio.to_thread`` in async contexts.
    """
    client = arxiv.Client(page_size=min(max_results, 20), num_retries=2, delay_seconds=1.0)
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    papers: list[ArxivPaper] = []
    try:
        for result in client.results(search):
            entry_id: str = result.entry_id  # e.g. "https://arxiv.org/abs/2301.12345v2"
            arxiv_id = entry_id.split("/abs/")[-1].split("v")[0]
            pdf_url = str(result.pdf_url) if result.pdf_url else f"https://arxiv.org/pdf/{arxiv_id}"

            papers.append(
                ArxivPaper(
                    title=result.title.strip(),
                    authors=[a.name for a in result.authors[:6]],
                    summary=result.summary.replace("\n", " ").strip(),
                    published=result.published.strftime("%Y-%m-%d"),
                    arxiv_url=entry_id,
                    pdf_url=pdf_url,
                    arxiv_id=arxiv_id,
                )
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("arXiv search failed for query %r: %s", query, exc)

    return papers
