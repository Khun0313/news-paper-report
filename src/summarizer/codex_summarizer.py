"""
Summarizer using Codex via ChatGPT backend OAuth.

Uses the ChatGPT backend API endpoint (same as OpenClaw)
with the access token obtained from the PKCE OAuth flow.
Requires streaming mode, input as list, and store=false.
"""

import json

import httpx

from src.search.aggregator import SearchResults

# ChatGPT backend endpoint for Codex (NOT api.openai.com)
CODEX_API_URL = "https://chatgpt.com/backend-api/codex/responses"
CODEX_MODEL = "gpt-5.3-codex"

SYSTEM_PROMPT = """\
You are a daily briefing assistant. You will receive ACTUAL search results \
(news articles and academic papers) below. You MUST ONLY use the provided results. \
Do NOT generate, guess, or hallucinate any items not in the input.

Your job:
1. SELECT the most important items from the PROVIDED results (up to 5 news, up to 5 papers)
2. SUMMARIZE them into a concise daily report in Korean

If there are fewer than 5 items in a category, include all of them.

Selection criteria:
- Prioritize breaking news, major announcements, and high-impact findings
- Prefer recent and novel content over incremental updates
- For papers: favor those with practical implications or breakthrough results
- Remove duplicates or near-duplicate coverage of the same event

Report format:
- Write in Korean
- Each item: 2-3 sentences max
- For news: original title, Korean translation of the title (on the next line, prefixed with "→"), source, key event, why it matters, and the EXACT link from the input
- For papers: original title, Korean translation of the title (on the next line, prefixed with "→"), authors, main finding in plain language, practical implications, and the EXACT link from the input
- If the title is already in Korean, do NOT add a translation line
- Use bullet points for readability
- Start with a one-line overall summary of today's key takeaway
- IMPORTANT: Use ONLY the links provided in the search results. Never fabricate URLs.
"""

TAG_SUGGEST_PROMPT = """\
You are a research topic expert. Given a topic name and optional description, \
suggest 8-10 English search tags (keywords) that would be most effective for \
finding relevant news articles and academic papers on Google News and Semantic Scholar.

Rules:
- Tags must be in English (for better search coverage)
- Include both broad and specific terms
- Include common abbreviations or acronyms if applicable
- Return ONLY a comma-separated list of tags, nothing else
- Example output: machine learning, deep learning, neural network, NLP, transformer, LLM, reinforcement learning, computer vision
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


async def _stream_codex(access_token: str, instructions: str, user_message: str, timeout: int = 60) -> str:
    """Call the Codex backend API with streaming and collect the full response text."""
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            CODEX_API_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "model": CODEX_MODEL,
                "instructions": instructions,
                "input": [
                    {"role": "user", "content": user_message},
                ],
                "store": False,
                "stream": True,
            },
            timeout=timeout,
        ) as resp:
            resp.raise_for_status()
            text_parts = []
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[len("data: "):]
                if data_str == "[DONE]":
                    break
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                # Collect text deltas from output_text.delta events
                if event.get("type") == "response.output_text.delta":
                    delta = event.get("delta", "")
                    if delta:
                        text_parts.append(delta)
                # Also collect from completed response
                elif event.get("type") == "response.completed":
                    response = event.get("response", {})
                    for item in response.get("output", []):
                        if item.get("type") == "message":
                            for block in item.get("content", []):
                                if block.get("type") == "output_text":
                                    # Only use completed text if we didn't get deltas
                                    if not text_parts:
                                        text_parts.append(block["text"])
            return "".join(text_parts)


async def suggest_tags(access_token: str, topic_name: str, description: str = "") -> list[str]:
    """
    Suggest search tags for a given topic using Codex.

    Returns:
        List of suggested tag strings.
    """
    user_input = f"토픽: {topic_name}"
    if description:
        user_input += f"\n설명: {description}"

    text = await _stream_codex(access_token, TAG_SUGGEST_PROMPT, user_input, timeout=30)

    if not text:
        return []

    return [t.strip() for t in text.split(",") if t.strip()]


async def summarize(
    access_token: str,
    results: SearchResults,
) -> str:
    """
    Summarize search results using Codex.

    Args:
        access_token: OAuth access token for Codex.
        results: Aggregated search results.

    Returns:
        Summarized report text in Korean.
    """
    content = _build_content(results)
    user_message = (
        f"아래 검색 결과에서 가장 중요하고 영향력 있는 뉴스 5개와 "
        f"논문 5개를 선별한 뒤, 브리핑 리포트를 작성해줘.\n\n"
        f"{content}"
    )

    text = await _stream_codex(access_token, SYSTEM_PROMPT, user_message, timeout=60)
    return text if text else "요약 생성에 실패했습니다."
