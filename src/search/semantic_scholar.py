"""
Semantic Scholar API search.

Free API, no key required. Unauthenticated users share a global
1,000 RPS pool, so 429 errors are common under load.
Implements exponential backoff with jitter on 429 responses.
"""

import asyncio
import random
from dataclasses import dataclass

import httpx

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"

MAX_RETRIES = 4
BASE_DELAY = 2  # seconds


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
    Retries with exponential backoff on 429 rate limit errors.
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
        for attempt in range(MAX_RETRIES + 1):
            resp = await client.get(
                SEMANTIC_SCHOLAR_API, params=params, timeout=15
            )
            if resp.status_code != 429:
                resp.raise_for_status()
                break
            if attempt == MAX_RETRIES:
                resp.raise_for_status()  # raise on final attempt
            # Exponential backoff with jitter
            delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
            await asyncio.sleep(delay)

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
