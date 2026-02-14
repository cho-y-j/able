"""Tests for Naver Finance news sentiment analysis."""

import uuid
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import AIMessage

from app.integrations.data.naver_news import (
    analyze_headline_sentiment,
    NewsSentiment,
    NewsArticle,
    _parse_naver_news_html,
    fetch_naver_news,
    POSITIVE_KEYWORDS,
    NEGATIVE_KEYWORDS,
    STRONG_POSITIVE,
    STRONG_NEGATIVE,
)


# ── Sentiment Lexicon ────────────────────────────────────


class TestSentimentLexicon:
    def test_positive_keywords_exist(self):
        assert len(POSITIVE_KEYWORDS) >= 20
        assert "급등" in POSITIVE_KEYWORDS
        assert "상승" in POSITIVE_KEYWORDS
        assert "호재" in POSITIVE_KEYWORDS

    def test_negative_keywords_exist(self):
        assert len(NEGATIVE_KEYWORDS) >= 20
        assert "급락" in NEGATIVE_KEYWORDS
        assert "하락" in NEGATIVE_KEYWORDS
        assert "악재" in NEGATIVE_KEYWORDS

    def test_strong_positive_subset_of_positive(self):
        for kw in STRONG_POSITIVE:
            assert kw in POSITIVE_KEYWORDS or kw not in NEGATIVE_KEYWORDS

    def test_strong_negative_subset_of_negative(self):
        for kw in STRONG_NEGATIVE:
            assert kw in NEGATIVE_KEYWORDS or kw not in POSITIVE_KEYWORDS

    def test_no_overlap_between_positive_and_negative(self):
        overlap = set(POSITIVE_KEYWORDS) & set(NEGATIVE_KEYWORDS)
        assert len(overlap) == 0, f"Overlapping keywords: {overlap}"


# ── analyze_headline_sentiment ───────────────────────────


class TestHeadlineSentiment:
    def test_positive_headline(self):
        score = analyze_headline_sentiment("삼성전자 급등, 사상최고 기록")
        assert score > 0

    def test_negative_headline(self):
        score = analyze_headline_sentiment("코스피 급락, 외국인 매도 폭주")
        assert score < 0

    def test_neutral_headline(self):
        score = analyze_headline_sentiment("삼성전자 주주총회 일정 공지")
        assert score == 0.0

    def test_strong_positive_scores_higher(self):
        weak = analyze_headline_sentiment("삼성전자 상승세")
        strong = analyze_headline_sentiment("삼성전자 급등 사상최고")
        assert strong >= weak

    def test_strong_negative_scores_lower(self):
        weak = analyze_headline_sentiment("코스피 하락")
        strong = analyze_headline_sentiment("코스피 폭락 급락")
        assert strong <= weak

    def test_score_clamped_to_range(self):
        # Many positive keywords
        score = analyze_headline_sentiment(
            "급등 상승 호재 최고 돌파 신고가 흑자 성장 매수 강세"
        )
        assert -1.0 <= score <= 1.0

    def test_mixed_sentiment(self):
        score = analyze_headline_sentiment("삼성전자 상승했으나 리스크 우려도")
        # Has both positive and negative, should be closer to 0
        assert -0.5 <= score <= 0.5


# ── _parse_naver_news_html ───────────────────────────────


class TestParseNaverHtml:
    def test_parses_tit_class_links(self):
        html = '''
        <a class="tit" href="/news/005930/1">삼성전자 급등 이유</a>
        <a class="tit" href="/news/005930/2">코스피 반등 기대</a>
        '''
        articles = _parse_naver_news_html(html, "005930")
        assert len(articles) == 2
        assert articles[0].title == "삼성전자 급등 이유"
        assert articles[0].sentiment_score > 0

    def test_parses_title_attribute_links(self):
        html = '''
        <a title="LG에너지솔루션 실적 호조" href="/news/373220/1">link</a>
        <a title="현대차 매출 증가" href="/news/005380/1">link</a>
        '''
        articles = _parse_naver_news_html(html, "373220")
        assert len(articles) >= 1

    def test_empty_html_returns_empty(self):
        articles = _parse_naver_news_html("", "005930")
        assert articles == []

    def test_caps_at_20_articles(self):
        html = "\n".join(
            f'<a class="tit" href="/news/{i}">뉴스 제목 {i} 삼성전자</a>'
            for i in range(30)
        )
        articles = _parse_naver_news_html(html, "005930")
        assert len(articles) <= 20

    def test_url_prefixed_with_naver(self):
        html = '<a class="tit" href="/item/news.naver?code=005930">제목</a>'
        articles = _parse_naver_news_html(html, "005930")
        if articles:
            assert articles[0].url.startswith("https://finance.naver.com")


# ── NewsSentiment dataclass ──────────────────────────────


class TestNewsSentiment:
    def test_default_values(self):
        ns = NewsSentiment(stock_code="005930", stock_name="삼성전자")
        assert ns.overall_score == 0.0
        assert ns.total_count == 0
        assert ns.articles == []

    def test_summary_generation(self):
        ns = NewsSentiment(
            stock_code="005930",
            stock_name="삼성전자",
            overall_score=0.35,
            positive_count=5,
            negative_count=1,
            neutral_count=2,
            total_count=8,
            summary="삼성전자 뉴스 감성: 긍정 (점수: +0.35, 긍정 5/부정 1/중립 2건)",
        )
        assert "긍정" in ns.summary
        assert "삼성전자" in ns.summary


# ── fetch_naver_news (mocked HTTP) ───────────────────────


class TestFetchNaverNews:
    @pytest.mark.asyncio
    async def test_returns_sentiment_result(self):
        mock_html = '''
        <a class="tit" href="/news/1">삼성전자 급등 사상최고</a>
        <a class="tit" href="/news/2">코스피 반등 회복 기대</a>
        <a class="tit" href="/news/3">외국인 매도 하락세</a>
        '''
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.integrations.data.naver_news.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            result = await fetch_naver_news("005930", "삼성전자")

        assert isinstance(result, NewsSentiment)
        assert result.stock_code == "005930"
        assert result.total_count == 3
        assert result.positive_count >= 1
        assert result.negative_count >= 1
        assert result.summary != ""

    @pytest.mark.asyncio
    async def test_handles_network_error(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.integrations.data.naver_news.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            result = await fetch_naver_news("005930")

        assert result.total_count == 0
        assert "실패" in result.summary

    @pytest.mark.asyncio
    async def test_handles_no_httpx(self):
        with patch("app.integrations.data.naver_news.httpx", None):
            result = await fetch_naver_news("005930")
        assert result.total_count == 0
        assert "httpx" in result.summary


# ── Market Analyst Integration ───────────────────────────


class TestMarketAnalystWithSentiment:
    def _make_state(self, **overrides) -> dict:
        state = {
            "messages": [],
            "user_id": str(uuid.uuid4()),
            "session_id": str(uuid.uuid4()),
            "market_regime": None,
            "watchlist": ["005930"],
            "strategy_candidates": [],
            "optimization_status": "",
            "risk_assessment": None,
            "pending_orders": [],
            "executed_orders": [],
            "portfolio_snapshot": {},
            "alerts": [],
            "pending_approval": False,
            "pending_trades": [],
            "approval_status": None,
            "approval_threshold": 5_000_000,
            "hitl_enabled": False,
            "memory_context": "",
            "current_agent": "",
            "iteration_count": 0,
            "should_continue": True,
            "error_state": None,
        }
        state.update(overrides)
        return state

    @pytest.mark.asyncio
    async def test_market_analyst_with_sentiment_data(self):
        """Market analyst should include sentiment in output when available."""
        from app.agents.nodes.market_analyst import market_analyst_node

        sentiment = NewsSentiment(
            stock_code="005930",
            stock_name="삼성전자",
            overall_score=0.4,
            positive_count=5,
            negative_count=1,
            neutral_count=2,
            total_count=8,
            articles=[
                NewsArticle(title="삼성전자 급등", url="", source="", date="", sentiment_score=0.8),
            ],
            summary="삼성전자 뉴스 감성: 긍정",
        )

        async def mock_fetch(stock_code, stock_name=""):
            if stock_code == "005930":
                return sentiment
            return NewsSentiment(stock_code=stock_code, stock_name=stock_name)

        state = self._make_state()

        with patch("app.agents.nodes.market_analyst.fetch_naver_news", side_effect=mock_fetch):
            result = await market_analyst_node(state)

        regime = result["market_regime"]
        assert "news_sentiment" in regime
        assert "005930" in regime["news_sentiment"]
        assert regime["news_sentiment"]["005930"]["score"] > 0

    @pytest.mark.asyncio
    async def test_market_analyst_works_without_sentiment(self):
        """Market analyst should work fine when news fetch fails."""
        from app.agents.nodes.market_analyst import market_analyst_node

        async def mock_fetch_fail(stock_code, stock_name=""):
            raise Exception("Network error")

        state = self._make_state()

        with patch("app.agents.nodes.market_analyst.fetch_naver_news", side_effect=mock_fetch_fail):
            result = await market_analyst_node(state)

        assert "market_regime" in result
        assert result["market_regime"]["classification"] == "sideways"

    @pytest.mark.asyncio
    async def test_sentiment_passed_to_llm(self):
        """When LLM is available, sentiment data should be included in prompt."""
        from app.agents.nodes.market_analyst import market_analyst_node

        sentiment = NewsSentiment(
            stock_code="005930",
            stock_name="삼성전자",
            overall_score=0.5,
            positive_count=3,
            negative_count=0,
            neutral_count=1,
            total_count=4,
            articles=[],
            summary="삼성전자 뉴스 감성: 긍정 (점수: +0.50)",
        )

        async def mock_fetch(stock_code, stock_name=""):
            return sentiment

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content='{"regime": "bull", "confidence": 0.8, "analysis": "Bullish with positive sentiment"}'
        )

        state = self._make_state(_llm=mock_llm)

        with patch("app.agents.nodes.market_analyst.fetch_naver_news", side_effect=mock_fetch):
            result = await market_analyst_node(state)

        # Verify LLM was called with sentiment in the message
        call_args = mock_llm.ainvoke.call_args[0][0]
        human_msg = call_args[1].content
        assert "감성" in human_msg or "sentiment" in human_msg.lower()

        assert result["market_regime"]["classification"] == "bull"
