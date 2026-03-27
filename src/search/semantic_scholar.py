"""
Semantic Scholar API search.

Free API, no key required (rate limited to 100 req/5min).
"""

from dataclasses import dataclass

import httpx

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"


@dataclass
class Paper:
    title: str
    authors: list[str]
    year: int | None
    abstract: str
    url: str
    citation_count: int
    venue: str


async def search_papers(
    tags: list[str],
    max_results: int = 10,
    year_from: int | None = None,
) -> list[Paper]:
    """
    Search Semantic Scholar for papers matching the given tags.

    Args:
        tags: Search keywords.
        max_results: Maximum number of papers to return.
        year_from: Only return papers from this year onwards.

    Returns:
        List of Paper results.
    """
    query = " ".join(tags)
    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,authors,year,abstract,url,citationCount,venue",
    }
    if year_from:
        params["year"] = f"{year_from}-"

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            SEMANTIC_SCHOLAR_API, params=params, timeout=15
        )
        resp.raise_for_status()
        data = resp.json()

    papers = []
    for item in data.get("data", []):
        authors = [a.get("name", "") for a in item.get("authors", [])]
        papers.append(
            Paper(
                title=item.get("title", ""),
                authors=authors,
                year=item.get("year"),
                abstract=item.get("abstract") or "",
                url=item.get("url", ""),
                citation_count=item.get("citationCount", 0),
                venue=item.get("venue", ""),
            )
        )

    return papers
