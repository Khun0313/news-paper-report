"""
Summarizer using OpenAI Codex 5.2 via OAuth.

Uses the Codex responses API (same endpoint OpenClaw uses)
with the access token obtained from the PKCE OAuth flow.
"""

import httpx

from src.search.aggregator import SearchResults

# Codex uses the responses API endpoint
CODEX_API_URL = "https://api.openai.com/v1/responses"
CODEX_MODEL = "gpt-5.2-codex"

SYSTEM_PROMPT = """\
You are a daily briefing assistant. You receive a large batch of news articles and \
academic papers, and your job is to:

1. SELECT the most important and impactful items (top 5 news, top 5 papers)
2. SUMMARIZE them into a concise, easy-to-understand daily report in Korean

Selection criteria:
- Prioritize breaking news, major announcements, and high-impact findings
- Prefer recent and novel content over incremental updates
- For papers: favor those with practical implications or breakthrough results
- Remove duplicates or near-duplicate coverage of the same event

Report rules:
- Write in Korean
- Be concise and clear — each item should be 2-3 sentences max
- For news: highlight the key event and why it matters
- For papers: explain the main finding in plain language, note practical implications
- Use bullet points for readability
- Include source links
- Start with a one-line overall summary of today's key takeaway
"""


def _build_content(results: SearchResults) -> str:
    """Build the content to send to the model for summarization."""
    parts = [f"검색 태그: {', '.join(results.query_tags)}\n"]

    if results.news:
        parts.append("=== 뉴스 기사 ===")
        for i, article in enumerate(results.news, 1):
            parts.append(
                f"{i}. [{article.title}]({article.link})\n"
                f"   출처: {article.source} | 발행: {article.published}\n"
                f"   {article.snippet}"
            )

    if results.papers:
        parts.append("\n=== 학술 논문 ===")
        for i, paper in enumerate(results.papers, 1):
            authors = ", ".join(paper.authors[:3])
            if len(paper.authors) > 3:
                authors += " et al."
            parts.append(
                f"{i}. [{paper.title}]({paper.url})\n"
                f"   저자: {authors} | 연도: {paper.year} | "
                f"인용: {paper.citation_count}\n"
                f"   {paper.abstract[:300]}"
            )

    return "\n".join(parts)


async def summarize(
    access_token: str,
    results: SearchResults,
) -> str:
    """
    Summarize search results using Codex 5.2.

    Args:
        access_token: OAuth access token for Codex.
        results: Aggregated search results.

    Returns:
        Summarized report text in Korean.
    """
    content = _build_content(results)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            CODEX_API_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "model": CODEX_MODEL,
                "instructions": SYSTEM_PROMPT,
                "input": (
                    f"아래 검색 결과에서 가장 중요하고 영향력 있는 뉴스 5개와 "
                    f"논문 5개를 선별한 뒤, 브리핑 리포트를 작성해줘.\n\n"
                    f"{content}"
                ),
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

    # Extract text from responses API output
    output = data.get("output", [])
    texts = []
    for item in output:
        if item.get("type") == "message":
            for block in item.get("content", []):
                if block.get("type") == "output_text":
                    texts.append(block["text"])
    return "\n".join(texts) if texts else "요약 생성에 실패했습니다."
