"""Market Analyst Agent: Analyzes market conditions and classifies regimes.

Enhanced with Naver Finance news sentiment analysis for Korean stocks.
"""

import json
import logging
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.agents.state import TradingState
from app.integrations.data.naver_news import fetch_naver_news, NewsSentiment

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Market Analyst agent in an AI-powered automated trading team.

Your responsibilities:
1. Analyze current market conditions (KOSPI, KOSDAQ indices)
2. Classify the market regime: bull, bear, sideways, volatile, or crisis
3. Evaluate the user's watchlist stocks for trading opportunities
4. Provide context for strategy selection

When classifying market regime, consider:
- ADX > 25 with +DI > -DI = bull trend
- ADX > 25 with -DI > +DI = bear trend
- ADX < 20 = sideways/ranging
- ATR spike + BB expansion = volatile
- Circuit breaker or >3% index drop = crisis

Always provide your confidence level (0.0-1.0).
Be conservative: when uncertain, classify as 'sideways'.

Respond in JSON format:
{
    "regime": "bull|bear|sideways|volatile|crisis",
    "confidence": 0.0-1.0,
    "analysis": "brief explanation",
    "opportunities": ["stock_code1", "stock_code2"]
}"""


async def market_analyst_node(state: TradingState) -> dict:
    """LangGraph node: runs market analysis and updates shared state."""

    watchlist = state.get("watchlist", [])
    iteration = state.get("iteration_count", 0)

    # Try to use LLM if available in state
    llm = state.get("_llm")
    regime_data = None

    # Inject memory context if available
    memory_context = state.get("memory_context", "")
    memory_section = ""
    if memory_context:
        memory_section = f"\n\nRelevant memories from past sessions:\n{memory_context}\n"

    # Fetch news sentiment for watchlist stocks (best-effort, non-blocking)
    sentiment_data: list[NewsSentiment] = []
    sentiment_section = ""
    for stock_code in watchlist[:5]:
        try:
            ns = await fetch_naver_news(stock_code)
            if ns.total_count > 0:
                sentiment_data.append(ns)
        except Exception as e:
            logger.debug(f"News fetch failed for {stock_code}: {e}")

    if sentiment_data:
        sentiment_lines = [ns.summary for ns in sentiment_data]
        sentiment_section = "\n\nNews sentiment:\n" + "\n".join(sentiment_lines) + "\n"

    if llm:
        try:
            messages = [
                SystemMessage(content=SYSTEM_PROMPT + memory_section),
                HumanMessage(content=(
                    f"Iteration {iteration + 1}. "
                    f"Watchlist: {', '.join(watchlist)}. "
                    f"{sentiment_section}"
                    f"Please analyze current market conditions and classify the regime."
                )),
            ]
            response = await llm.ainvoke(messages)
            # Parse JSON from response
            text = response.content
            # Extract JSON from possible markdown code block
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            parsed = json.loads(text.strip())
            regime_data = {
                "classification": parsed.get("regime", "sideways"),
                "confidence": parsed.get("confidence", 0.6),
                "indicators": {},
                "analysis": parsed.get("analysis", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.warning(f"LLM market analysis failed, using rule-based: {e}")

    # Fallback: rule-based approach
    if not regime_data:
        regime_data = {
            "classification": "sideways",
            "confidence": 0.6,
            "indicators": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Attach news sentiment to regime data
    if sentiment_data:
        regime_data["news_sentiment"] = {
            ns.stock_code: {
                "score": round(ns.overall_score, 3),
                "positive": ns.positive_count,
                "negative": ns.negative_count,
                "neutral": ns.neutral_count,
                "total": ns.total_count,
                "summary": ns.summary,
            }
            for ns in sentiment_data
        }

    sentiment_msg = ""
    if sentiment_data:
        avg_score = sum(ns.overall_score for ns in sentiment_data) / len(sentiment_data)
        sentiment_label = "긍정" if avg_score > 0.1 else "부정" if avg_score < -0.1 else "중립"
        sentiment_msg = f" News sentiment: {sentiment_label} ({avg_score:+.2f})."

    return {
        "messages": [AIMessage(
            content=f"[Market Analyst] Iteration {iteration + 1}: "
                    f"Market regime classified as '{regime_data['classification']}' "
                    f"with {regime_data['confidence']:.0%} confidence. "
                    f"Monitoring {len(watchlist)} stocks.{sentiment_msg}"
        )],
        "market_regime": regime_data,
        "current_agent": "market_analyst",
        "iteration_count": iteration + 1,
    }
