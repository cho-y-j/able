"""Naver Finance news scraping and Korean keyword-based sentiment analysis.

Provides market sentiment from Naver Finance news headlines for Korean stocks.
Uses a keyword-based approach (no ML model needed) for fast, dependency-free
sentiment scoring.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ── Korean sentiment lexicon ─────────────────────────────

POSITIVE_KEYWORDS = [
    "급등", "상승", "호재", "최고", "돌파", "신고가", "흑자", "성장",
    "매수", "강세", "반등", "회복", "상향", "호실적", "사상최고",
    "개선", "확대", "증가", "수주", "계약", "인수합병", "배당",
    "목표가상향", "실적개선", "영업이익", "순이익", "기대",
    "호조", "수혜", "긍정", "유망", "추천", "우상향",
]

NEGATIVE_KEYWORDS = [
    "급락", "하락", "악재", "최저", "폭락", "적자", "손실",
    "매도", "약세", "하향", "리스크", "위기", "경고", "부진",
    "감소", "축소", "하방", "불안", "우려", "제재", "조사",
    "목표가하향", "실적부진", "영업손실", "순손실", "충격",
    "악화", "둔화", "부담", "피해", "규제", "소송",
]

STRONG_POSITIVE = ["급등", "사상최고", "신고가", "호실적", "흑자전환"]
STRONG_NEGATIVE = ["급락", "폭락", "적자전환", "상장폐지", "부도"]


@dataclass
class NewsArticle:
    title: str
    url: str
    source: str
    date: str
    sentiment_score: float = 0.0


@dataclass
class NewsSentiment:
    stock_code: str
    stock_name: str
    articles: list[NewsArticle] = field(default_factory=list)
    overall_score: float = 0.0  # -1.0 (very negative) to 1.0 (very positive)
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    total_count: int = 0
    summary: str = ""


def analyze_headline_sentiment(title: str) -> float:
    """Score a single Korean headline. Returns -1.0 to 1.0."""
    score = 0.0

    for kw in STRONG_POSITIVE:
        if kw in title:
            score += 2.0
    for kw in STRONG_NEGATIVE:
        if kw in title:
            score -= 2.0

    for kw in POSITIVE_KEYWORDS:
        if kw in title:
            score += 1.0
    for kw in NEGATIVE_KEYWORDS:
        if kw in title:
            score -= 1.0

    # Clamp to [-1, 1]
    if score > 0:
        return min(score / 3.0, 1.0)
    elif score < 0:
        return max(score / 3.0, -1.0)
    return 0.0


def _parse_naver_news_html(html: str, stock_code: str) -> list[NewsArticle]:
    """Parse news articles from Naver Finance HTML."""
    articles: list[NewsArticle] = []

    # Match news list items: title in <a> tags within news list
    # Pattern: <a ... class="tit" ...>TITLE</a>
    title_pattern = re.compile(
        r'<a[^>]*class="tit"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    # Also try: <a ... title="TITLE" ... href="URL">
    title_pattern2 = re.compile(
        r'<a[^>]*title="([^"]*)"[^>]*href="([^"]*)"[^>]*>',
        re.DOTALL,
    )
    # Source/date pattern
    info_pattern = re.compile(
        r'<span class="info">(.*?)</span>',
        re.DOTALL,
    )
    date_pattern = re.compile(
        r'<span class="date">(.*?)</span>',
        re.DOTALL,
    )

    # Try first pattern
    matches = title_pattern.findall(html)
    for url, title in matches:
        clean_title = re.sub(r"<[^>]+>", "", title).strip()
        if clean_title:
            sentiment = analyze_headline_sentiment(clean_title)
            articles.append(NewsArticle(
                title=clean_title,
                url=url if url.startswith("http") else f"https://finance.naver.com{url}",
                source="네이버금융",
                date="",
                sentiment_score=sentiment,
            ))

    # Try second pattern if first didn't find enough
    if len(articles) < 3:
        matches2 = title_pattern2.findall(html)
        existing_titles = {a.title for a in articles}
        for title, url in matches2:
            clean_title = title.strip()
            if clean_title and clean_title not in existing_titles and len(clean_title) > 5:
                sentiment = analyze_headline_sentiment(clean_title)
                articles.append(NewsArticle(
                    title=clean_title,
                    url=url if url.startswith("http") else f"https://finance.naver.com{url}",
                    source="네이버금융",
                    date="",
                    sentiment_score=sentiment,
                ))
                existing_titles.add(clean_title)

    return articles[:20]  # Cap at 20 articles


async def fetch_naver_news(stock_code: str, stock_name: str = "") -> NewsSentiment:
    """Fetch and analyze news for a stock from Naver Finance.

    Args:
        stock_code: KRX stock code (e.g., "005930")
        stock_name: Optional stock name for display

    Returns:
        NewsSentiment with scored articles and overall sentiment.
    """
    result = NewsSentiment(stock_code=stock_code, stock_name=stock_name)

    if httpx is None:
        logger.warning("httpx not installed, cannot fetch Naver news")
        result.summary = "뉴스 수집 실패 (httpx 미설치)"
        return result

    url = f"https://finance.naver.com/item/news_news.naver?code={stock_code}&page=1"

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        logger.warning(f"Failed to fetch Naver news for {stock_code}: {e}")
        result.summary = f"뉴스 수집 실패: {e}"
        return result

    articles = _parse_naver_news_html(html, stock_code)
    result.articles = articles
    result.total_count = len(articles)

    if not articles:
        result.summary = f"{stock_code} 관련 뉴스 없음"
        return result

    # Aggregate sentiment
    for a in articles:
        if a.sentiment_score > 0.1:
            result.positive_count += 1
        elif a.sentiment_score < -0.1:
            result.negative_count += 1
        else:
            result.neutral_count += 1

    scores = [a.sentiment_score for a in articles]
    result.overall_score = sum(scores) / len(scores) if scores else 0.0

    # Generate summary
    sentiment_label = "긍정" if result.overall_score > 0.1 else "부정" if result.overall_score < -0.1 else "중립"
    result.summary = (
        f"{stock_name or stock_code} 뉴스 감성: {sentiment_label} "
        f"(점수: {result.overall_score:+.2f}, "
        f"긍정 {result.positive_count}/부정 {result.negative_count}/중립 {result.neutral_count}건)"
    )

    return result


def fetch_naver_news_sync(stock_code: str, stock_name: str = "") -> NewsSentiment:
    """Synchronous wrapper for fetch_naver_news."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(
                asyncio.run, fetch_naver_news(stock_code, stock_name)
            ).result()
    return asyncio.run(fetch_naver_news(stock_code, stock_name))
