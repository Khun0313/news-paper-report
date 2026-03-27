"""
Aggregates search results from all sources.
"""

from dataclasses import dataclass, field
from datetime import datetime

from src.search.google_news import NewsArticle, search_news
from src.search.semantic_scholar import Paper, search_papers


@dataclass
class SearchResults:
    query_tags: list[str]
    news: list[NewsArticle] = field(default_factory=list)
    papers: list[Paper] = field(default_factory=list)
    searched_at: str = ""


async def aggregate_search(
    tags: list[str],
    news_count: int = 10,
    paper_count: int = 10,
    paper_year_from: int | None = None,
) -> SearchResults:
    """
    Search all sources in parallel and aggregate results.

    Args:
        tags: Search keywords/tags.
        news_count: Max news articles to fetch.
        paper_count: Max papers to fetch.
        paper_year_from: Only fetch papers from this year onwards.
    """
    import asyncio

    news_task = asyncio.create_task(search_news(tags, news_count))
    papers_task = asyncio.create_task(
        search_papers(tags, paper_count, paper_year_from)
    )

    news, papers = await asyncio.gather(news_task, papers_task, return_exceptions=True)

    return SearchResults(
        query_tags=tags,
        news=news if isinstance(news, list) else [],
        papers=papers if isinstance(papers, list) else [],
        searched_at=datetime.now().isoformat(),
    )
