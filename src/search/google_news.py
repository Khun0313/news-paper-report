"""
Google News search via RSS feed.

Uses Google News RSS which doesn't require an API key.
"""

import html
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

import feedparser
import httpx

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


@dataclass
class NewsArticle:
    title: str
    link: str
    source: str
    published: str
    snippet: str


def _clean_html(raw: str) -> str:
    """Remove HTML tags and decode entities."""
    clean = re.sub(r"<[^>]+>", "", raw)
    return html.unescape(clean).strip()


async def search_news(tags: list[str], max_results: int = 10) -> list[NewsArticle]:
    """
    Search Google News RSS for articles matching the given tags.

    Args:
        tags: Search keywords/tags.
        max_results: Maximum number of articles to return per query.

    Returns:
        List of NewsArticle results.
    """
    articles = []
    seen_links = set()

    query = " OR ".join(tags)
    url = f"{GOOGLE_NEWS_RSS}?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(url, timeout=15)
        resp.raise_for_status()
        raw_text = resp.text

    feed = feedparser.parse(raw_text)

    for entry in feed.entries[:max_results]:
        link = entry.get("link", "")
        if link in seen_links:
            continue
        seen_links.add(link)

        source = ""
        if hasattr(entry, "source") and hasattr(entry.source, "title"):
            source = entry.source.title
        elif " - " in entry.get("title", ""):
            parts = entry["title"].rsplit(" - ", 1)
            if len(parts) == 2:
                source = parts[1]

        articles.append(
            NewsArticle(
                title=_clean_html(entry.get("title", "")),
                link=link,
                source=source,
                published=entry.get("published", ""),
                snippet=_clean_html(entry.get("summary", "")),
            )
        )

    return articles
