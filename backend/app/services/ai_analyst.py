"""AI Analyst service — DeepSeek-powered hybrid analysis.

Architecture:
  Layer 1 (Statistics) → Fact Sheet (~500 tokens) → Layer 3 (LLM) → Recommendation

The LLM NEVER computes numbers — it only interprets pre-computed statistics
and analyzes news sentiment.
"""

import logging
import asyncio
from datetime import datetime
from typing import Any

import pandas as pd
from openai import AsyncOpenAI

logger = logging.getLogger("able.ai_analyst")

_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_DEEPSEEK_MODEL = "deepseek-chat"

_SYSTEM_PROMPT = """당신은 ABLE 플랫폼의 AI 매매 분석가입니다.

역할:
- 제공된 통계 팩트시트(숫자)를 해석하여 매매 판단을 내립니다
- 뉴스 감성을 분석합니다
- 절대로 직접 수치를 계산하지 마세요 — 팩트시트의 숫자만 인용하세요

응답 형식 (반드시 준수):
1. 종합 판단: 매수 / 매도 / 관망 (하나만 선택)
2. 확신도: 1~10 (10이 가장 확신)
3. 핵심 근거 (3줄 이내, 팩트시트 숫자 인용)
4. 리스크 요인 (2줄 이내)
5. 뉴스 감성: 긍정 / 중립 / 부정
6. 추천 진입가 / 손절가 / 목표가 (현재가 기준 %)

간결하게 답변하세요. 한국어로 답변하세요."""


async def analyze_stock(
    stock_code: str,
    stock_name: str | None,
    fact_sheet: str,
    news_items: list[dict] | None = None,
    api_key: str | None = None,
) -> dict:
    """Run AI analysis using DeepSeek.

    Args:
        stock_code: Stock code.
        stock_name: Optional stock name.
        fact_sheet: Pre-computed statistical fact sheet (from Layer 1).
        news_items: List of {"title": str, "source": str, "date": str}.
        api_key: DeepSeek API key (from user settings or .env).

    Returns:
        Dictionary with AI analysis results.
    """
    if not api_key:
        return {"error": "DeepSeek API 키가 설정되지 않았습니다. 설정 페이지에서 LLM API 키를 등록하세요."}

    # Build the user prompt
    prompt_parts = [fact_sheet]

    if news_items:
        prompt_parts.append("\n■ 최근 뉴스")
        for i, news in enumerate(news_items[:5], 1):
            prompt_parts.append(f"  {i}. \"{news.get('title', '')}\" ({news.get('source', '')})")

    prompt_parts.append("\n→ 위 데이터를 기반으로 매매 판단을 내려주세요.")

    user_prompt = "\n".join(prompt_parts)

    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=_DEEPSEEK_BASE_URL,
        )

        response = await client.chat.completions.create(
            model=_DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )

        ai_text = response.choices[0].message.content or ""
        usage = response.usage

        # Parse the AI response
        result = _parse_ai_response(ai_text)
        result["raw_response"] = ai_text
        result["model"] = _DEEPSEEK_MODEL
        result["tokens_used"] = {
            "prompt": usage.prompt_tokens if usage else 0,
            "completion": usage.completion_tokens if usage else 0,
            "total": usage.total_tokens if usage else 0,
        }
        result["fact_sheet_preview"] = fact_sheet[:200] + "..."
        result["timestamp"] = datetime.now().isoformat()

        logger.info(
            "AI analysis for %s: %s (confidence %s, tokens %s)",
            stock_code,
            result.get("decision", "unknown"),
            result.get("confidence", "?"),
            result["tokens_used"]["total"],
        )

        return result

    except Exception as e:
        logger.error("DeepSeek API error: %s", e)
        return {
            "error": f"AI 분석 실패: {str(e)}",
            "decision": "관망",
            "confidence": 0,
        }


def _parse_ai_response(text: str) -> dict:
    """Parse structured AI response into fields."""
    result = {
        "decision": "관망",
        "confidence": 5,
        "reasoning": "",
        "risks": "",
        "news_sentiment": "중립",
        "price_targets": {},
    }

    lines = text.strip().split("\n")

    for line in lines:
        line_lower = line.strip().lower()

        # Decision
        if "종합 판단" in line or "종합판단" in line:
            if "매수" in line:
                result["decision"] = "매수"
            elif "매도" in line:
                result["decision"] = "매도"
            else:
                result["decision"] = "관망"

        # Confidence
        if "확신도" in line:
            for part in line.split():
                try:
                    val = int(part.strip(":/"))
                    if 1 <= val <= 10:
                        result["confidence"] = val
                        break
                except ValueError:
                    continue

        # Reasoning
        if "핵심 근거" in line or "근거" in line:
            idx = lines.index(line)
            reasoning_lines = []
            for r in lines[idx:idx + 4]:
                if r.strip() and not any(k in r for k in ["리스크", "뉴스 감성", "추천"]):
                    reasoning_lines.append(r.strip())
            result["reasoning"] = " ".join(reasoning_lines)

        # Risks
        if "리스크" in line:
            idx = lines.index(line)
            risk_lines = []
            for r in lines[idx:idx + 3]:
                if r.strip() and not any(k in r for k in ["뉴스 감성", "추천", "핵심"]):
                    risk_lines.append(r.strip())
            result["risks"] = " ".join(risk_lines)

        # News sentiment
        if "뉴스 감성" in line:
            if "긍정" in line:
                result["news_sentiment"] = "긍정"
            elif "부정" in line:
                result["news_sentiment"] = "부정"
            else:
                result["news_sentiment"] = "중립"

    # If we couldn't parse well, use the whole text as reasoning
    if not result["reasoning"]:
        result["reasoning"] = text[:500]

    return result


async def fetch_news(stock_code: str, stock_name: str | None = None) -> list[dict]:
    """Fetch recent news for a stock using yfinance.

    Returns list of {"title": str, "source": str, "date": str, "url": str}.
    """
    try:
        import yfinance as yf
        from app.integrations.data.yahoo_provider import krx_to_yahoo_ticker

        ticker_str = krx_to_yahoo_ticker(stock_code)
        ticker = yf.Ticker(ticker_str)

        news = []
        try:
            raw_news = ticker.news or []
        except Exception:
            raw_news = []

        for item in raw_news[:10]:
            content = item.get("content", {}) if isinstance(item, dict) else {}
            title = content.get("title") or item.get("title", "")
            provider = content.get("provider", {})
            source = provider.get("displayName", "") if isinstance(provider, dict) else str(provider)
            pub_date = content.get("pubDate") or item.get("providerPublishTime", "")
            url = content.get("canonicalUrl", {}).get("url", "") or item.get("link", "")

            if title:
                news.append({
                    "title": title,
                    "source": source or "Unknown",
                    "date": str(pub_date)[:10] if pub_date else "",
                    "url": url,
                })

        return news

    except Exception as e:
        logger.warning("News fetch failed for %s: %s", stock_code, e)
        return []


async def run_full_analysis(
    stock_code: str,
    stock_name: str | None,
    df: pd.DataFrame,
    api_key: str,
    include_macro: bool = True,
) -> dict:
    """Run the complete hybrid analysis pipeline.

    1. Compute statistical features (Layer 1)
    2. Generate fact sheet (Layer 2)
    3. Fetch news + AI analysis (Layer 3)
    """
    from app.analysis.features.fact_sheet import generate_fact_sheet, get_current_signals

    # Layer 1: Statistics (runs in thread pool to avoid blocking)
    current_signals = await asyncio.to_thread(get_current_signals, df)

    macro_data = None
    if include_macro:
        try:
            from app.analysis.features.macro_correlation import analyze_macro_correlation
            macro_data = await asyncio.to_thread(
                analyze_macro_correlation, df, stock_code
            )
        except Exception as e:
            logger.warning("Macro analysis skipped: %s", e)

    # Layer 2: Fact Sheet
    fact_sheet = await asyncio.to_thread(
        generate_fact_sheet,
        df, stock_code, stock_name, macro_data, current_signals,
    )

    # Layer 3: News + AI
    news = await fetch_news(stock_code, stock_name)
    ai_result = await analyze_stock(
        stock_code, stock_name, fact_sheet, news, api_key,
    )

    # Combine everything
    from app.analysis.features.time_patterns import analyze_time_patterns
    from app.analysis.features.indicator_combos import analyze_indicator_accuracy

    time_patterns = await asyncio.to_thread(analyze_time_patterns, df)
    indicator_data = await asyncio.to_thread(analyze_indicator_accuracy, df)

    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "ai_analysis": ai_result,
        "fact_sheet": fact_sheet,
        "news": news[:5],
        "time_patterns": time_patterns,
        "indicator_accuracy": indicator_data,
        "macro_correlations": macro_data,
        "current_signals": {
            k: v for k, v in current_signals.items() if v["signal"] != "none"
        },
        "timestamp": datetime.now().isoformat(),
    }
