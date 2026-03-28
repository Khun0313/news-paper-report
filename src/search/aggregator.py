"""
Aggregates search results from all sources.

When there are many tags, splits them into smaller chunks
to avoid overly long queries that return no results.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from src.search.google_news import NewsArticle, search_news
from src.search.semantic_scholar import Paper, search_papers

MAX_TAGS_PER_QUERY = 3


@dataclass
class SearchResults:
    query_tags: list[str]
    news: list[NewsArticle] = field(default_factory=list)
    papers: list[Paper] = field(default_factory=list)
    searched_at: str = ""


def _chunk_tags(tags: list[str], size: int) -> list[list[str]]:
    """Split tags into chunks of given size."""
    return [tags[i:i + size] for i in range(0, len(tags), size)]


def _dedupe_news(articles: list[NewsArticle]) -> list[NewsArticle]:
    """Remove duplicate news articles by link."""
    seen = set()
    result = []
    for a in articles:
        if a.link not in seen:
            seen.add(a.link)
            result.append(a)
    return result


def _dedupe_papers(papers: list[Paper]) -> list[Paper]:
    """Remove duplicate papers by title (lowered)."""
    seen = set()
    result = []
    for p in papers:
        key = p.title.lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(p)
    return result


async def aggregate_search(
    tags: list[str],
    news_count: int = 10,
    paper_count: int = 10,
    paper_year_from: int | None = None,
) -> SearchResults:
    """
    Search all sources and aggregate results.

    When tags exceed MAX_TAGS_PER_QUERY, splits into smaller chunks,
    searches each chunk separately, then merges and deduplicates.
    Papers are searched sequentially to respect Semantic Scholar rate limits.
    """
    chunks = _chunk_tags(tags, MAX_TAGS_PER_QUERY)
    per_chunk_news = max(news_count // len(chunks), 5)
    per_chunk_papers = max(paper_count // len(chunks), 5)

    # Search news in parallel (Google News has no strict rate limit)
    news_tasks = [
        asyncio.create_task(search_news(chunk, per_chunk_news))
        for chunk in chunks
    ]
    news_results = await asyncio.gather(*news_tasks, return_exceptions=True)

    all_news = []
    for result in news_results:
        if isinstance(result, list):
            all_news.extend(result)
    all_news = _dedupe_news(all_news)[:news_count]

    # Search papers sequentially to avoid 429 rate limits
    all_papers = []
    for chunk in chunks:
        try:
            papers = await search_papers(chunk, per_chunk_papers, paper_year_from)
            all_papers.extend(papers)
        except Exception:
            # Skip failed chunks, continue with others
            pass
        # Small delay between requests to respect rate limits
        await asyncio.sleep(1)
    all_papers = _dedupe_papers(all_papers)[:paper_count]

    return SearchResults(
        query_tags=tags,
        news=all_news,
        papers=all_papers,
        searched_at=datetime.now().isoformat(),
    )
