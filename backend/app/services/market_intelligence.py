"""Daily Market Intelligence Service.

Fetches global market data (US, Europe, Asia, FX, commodities, bonds, VIX)
and generates an AI-powered daily briefing via DeepSeek.

No user API key required — uses system DeepSeek key.
Scheduled at 06:30 KST daily (before market open).
"""

import logging
from datetime import datetime, date, timedelta
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger("able.market_intel")

# ─── Global Market Tickers ──────────────────────────────────────────
GLOBAL_MARKETS = {
    # US indices
    "S&P 500": "^GSPC",
    "나스닥": "^IXIC",
    "다우존스": "^DJI",
    "러셀2000": "^RUT",
    # Korean indices
    "코스피": "^KS11",
    "코스닥": "^KQ11",
    # Asia
    "닛케이225": "^N225",
    "항셍": "^HSI",
    "상해종합": "000001.SS",
    # Europe
    "DAX": "^GDAXI",
    "FTSE100": "^FTSE",
    # Volatility
    "VIX": "^VIX",
}

COMMODITIES_FX = {
    # Commodities
    "WTI 원유": "CL=F",
    "브렌트유": "BZ=F",
    "금": "GC=F",
    "은": "SI=F",
    "구리": "HG=F",
    "천연가스": "NG=F",
    # FX
    "USD/KRW": "KRW=X",
    "달러인덱스": "DX-Y.NYB",
    "EUR/USD": "EURUSD=X",
    "USD/JPY": "JPY=X",
    # Bonds
    "미국2Y금리": "^IRX",
    "미국10Y금리": "^TNX",
    "미국30Y금리": "^TYX",
    # Futures
    "S&P500선물": "ES=F",
    "나스닥선물": "NQ=F",
}

# ─── Korean Theme → Leader Stock Mapping ────────────────────────────
# Theme-based trading (대장매매) — maps market themes to Korean sector leaders
THEME_STOCK_MAP = {
    "AI/반도체": {
        "leader": [("005930", "삼성전자"), ("000660", "SK하이닉스")],
        "follower": [("042700", "한미반도체"), ("403870", "HPSP"), ("058470", "리노공업")],
        "triggers": ["엔비디아", "AI", "반도체", "HBM", "GPU", "데이터센터"],
    },
    "2차전지/배터리": {
        "leader": [("373220", "LG에너지솔루션"), ("006400", "삼성SDI")],
        "follower": [("247540", "에코프로비엠"), ("086520", "에코프로"), ("003670", "포스코퓨처엠")],
        "triggers": ["배터리", "전기차", "리튬", "테슬라", "EV"],
    },
    "바이오/제약": {
        "leader": [("207940", "삼성바이오로직스"), ("068270", "셀트리온")],
        "follower": [("326030", "SK바이오팜"), ("145020", "휴젤"), ("196170", "알테오젠")],
        "triggers": ["바이오", "신약", "FDA", "임상", "GLP-1"],
    },
    "원자력/에너지": {
        "leader": [("009830", "한화솔루션"), ("267260", "HD현대일렉트릭")],
        "follower": [("034020", "두산에너빌리티"), ("108320", "LX세미콘")],
        "triggers": ["원전", "원자력", "SMR", "nuclear", "에너지"],
    },
    "방산/우주항공": {
        "leader": [("012450", "한화에어로스페이스"), ("047810", "한국항공우주")],
        "follower": [("079550", "LIG넥스원"), ("232140", "와이에이치")],
        "triggers": ["방산", "우주", "미사일", "NATO", "방위비"],
    },
    "로봇/자동화": {
        "leader": [("454910", "두산로보틱스"), ("090460", "비에이치")],
        "follower": [("108490", "로보티즈"), ("298040", "효성중공업")],
        "triggers": ["로봇", "자동화", "휴머노이드", "Figure", "robot"],
    },
    "자동차/모빌리티": {
        "leader": [("005380", "현대차"), ("000270", "기아")],
        "follower": [("018880", "한온시스템"), ("161390", "한국타이어앤테크놀로지")],
        "triggers": ["자동차", "전기차", "자율주행", "모빌리티"],
    },
    "조선/해양": {
        "leader": [("329180", "HD현대중공업"), ("009540", "HD한국조선해양")],
        "follower": [("010140", "삼성중공업"), ("042660", "한화오션")],
        "triggers": ["조선", "LNG", "해운", "컨테이너"],
    },
    "인터넷/플랫폼": {
        "leader": [("035420", "NAVER"), ("035720", "카카오")],
        "follower": [("263750", "펄어비스"), ("251270", "넷마블")],
        "triggers": ["플랫폼", "광고", "커머스", "메타버스"],
    },
    "금융/은행": {
        "leader": [("105560", "KB금융"), ("055550", "신한지주")],
        "follower": [("086790", "하나금융지주"), ("316140", "우리금융지주")],
        "triggers": ["금리", "은행", "배당", "밸류업", "PBR"],
    },
}


def fetch_global_market_data() -> dict[str, Any]:
    """Fetch all global market data using yfinance.

    Returns dict with indices, commodities, FX, bonds data.
    """
    import yfinance as yf

    all_tickers = {**GLOBAL_MARKETS, **COMMODITIES_FX}
    results = {}

    # Download all at once for efficiency (2 days for change calculation)
    ticker_list = list(all_tickers.values())
    try:
        data = yf.download(
            ticker_list,
            period="5d",
            progress=False,
            auto_adjust=True,
            group_by="ticker",
        )
    except Exception as e:
        logger.error("Bulk download failed: %s", e)
        data = pd.DataFrame()

    for name, ticker in all_tickers.items():
        try:
            if len(ticker_list) == 1:
                ticker_data = data
            else:
                ticker_data = data[ticker] if ticker in data.columns.get_level_values(0) else pd.DataFrame()

            if ticker_data.empty or len(ticker_data) < 1:
                continue

            # Flatten multi-level columns if needed
            if hasattr(ticker_data.columns, 'levels'):
                ticker_data.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in ticker_data.columns]
            else:
                ticker_data.columns = [c.lower() for c in ticker_data.columns]

            last = ticker_data.dropna(subset=["close"]).iloc[-1]
            close = float(last["close"])

            # Previous close for change
            valid_closes = ticker_data.dropna(subset=["close"])
            if len(valid_closes) >= 2:
                prev_close = float(valid_closes.iloc[-2]["close"])
                change = close - prev_close
                change_pct = (change / prev_close) * 100 if prev_close != 0 else 0
            else:
                change = 0
                change_pct = 0

            results[name] = {
                "ticker": ticker,
                "close": round(close, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "volume": int(last.get("volume", 0)) if not pd.isna(last.get("volume", 0)) else 0,
            }

        except Exception as e:
            logger.debug("Failed to fetch %s (%s): %s", name, ticker, e)

    return results


def detect_active_themes(market_data: dict) -> list[dict]:
    """Detect which Korean stock themes are currently active based on market signals.

    Analyzes US/global market movements to identify relevant Korean themes.
    """
    active_themes = []

    # US tech strong → AI/semiconductor theme
    sp500 = market_data.get("S&P 500", {})
    nasdaq = market_data.get("나스닥", {})
    vix = market_data.get("VIX", {})

    for theme_name, theme_info in THEME_STOCK_MAP.items():
        relevance_score = 0
        signals = []

        # Check market-related triggers
        if theme_name == "AI/반도체":
            nasdaq_chg = nasdaq.get("change_pct", 0)
            if nasdaq_chg > 1:
                relevance_score += 3
                signals.append(f"나스닥 +{nasdaq_chg:.1f}% 강세")
            elif nasdaq_chg < -1:
                relevance_score += 2
                signals.append(f"나스닥 {nasdaq_chg:.1f}% 약세 — 반도체 영향 주시")

        elif theme_name == "2차전지/배터리":
            copper = market_data.get("구리", {})
            if copper.get("change_pct", 0) > 1:
                relevance_score += 2
                signals.append(f"구리 +{copper['change_pct']:.1f}% (EV 수요 신호)")

        elif theme_name == "원자력/에너지":
            gas = market_data.get("천연가스", {})
            oil = market_data.get("WTI 원유", {})
            if gas.get("change_pct", 0) > 2:
                relevance_score += 2
                signals.append(f"천연가스 +{gas['change_pct']:.1f}% (에너지 수요)")
            if oil.get("change_pct", 0) > 2:
                relevance_score += 1
                signals.append(f"WTI +{oil['change_pct']:.1f}%")

        elif theme_name == "금융/은행":
            tnx = market_data.get("미국10Y금리", {})
            if abs(tnx.get("change_pct", 0)) > 2:
                relevance_score += 2
                signals.append(f"미국10Y금리 변동 {tnx['change_pct']:+.1f}%")

        elif theme_name == "조선/해양":
            oil = market_data.get("WTI 원유", {})
            brent = market_data.get("브렌트유", {})
            if oil.get("change_pct", 0) > 2 or brent.get("change_pct", 0) > 2:
                relevance_score += 2
                signals.append("유가 강세 → 해양플랜트 수주 기대")

        elif theme_name == "방산/우주항공":
            # Defense usually rises on geopolitical events, not directly correlated to market data
            # Always keep it as low relevance for monitoring
            relevance_score += 1
            signals.append("상시 모니터링")

        # VIX spike affects all themes
        vix_val = vix.get("close", 0)
        if vix_val > 25:
            signals.append(f"VIX {vix_val:.0f} — 변동성 확대 주의")
            relevance_score = max(relevance_score, 2)

        # FX impact
        krw = market_data.get("USD/KRW", {})
        if krw.get("change_pct", 0) > 0.5:
            if theme_name in ["AI/반도체", "자동차/모빌리티"]:
                signals.append(f"원/달러 {krw['change_pct']:+.1f}% — 수출주 환율효과")
                relevance_score += 1

        # General market momentum
        sp_chg = sp500.get("change_pct", 0)
        if abs(sp_chg) > 1.5:
            signals.append(f"S&P500 {sp_chg:+.1f}% — 글로벌 리스크온/오프")
            relevance_score += 1

        if relevance_score >= 2:
            active_themes.append({
                "name": theme_name,
                "relevance_score": relevance_score,
                "signals": signals,
                "leader_stocks": theme_info["leader"],
                "follower_stocks": theme_info["follower"],
            })

    # Sort by relevance
    active_themes.sort(key=lambda x: x["relevance_score"], reverse=True)
    return active_themes


def build_market_fact_sheet(market_data: dict, themes: list[dict]) -> str:
    """Build a concise fact sheet for DeepSeek AI analysis."""
    lines = []
    now = datetime.now()
    dow_kr = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}

    lines.append("[일일 시장 인텔리전스 팩트시트]")
    lines.append(f"기준일: {now.strftime('%Y-%m-%d')} ({dow_kr.get(now.weekday(), '')}요일)")
    lines.append("")

    # US Markets
    lines.append("■ 미국 증시")
    for name in ["S&P 500", "나스닥", "다우존스", "러셀2000"]:
        d = market_data.get(name, {})
        if d:
            lines.append(f"  {name}: {d['close']:,.2f} ({d['change_pct']:+.2f}%)")

    # Futures
    lines.append("")
    lines.append("■ 선물 (한국시간 기준)")
    for name in ["S&P500선물", "나스닥선물"]:
        d = market_data.get(name, {})
        if d:
            lines.append(f"  {name}: {d['close']:,.2f} ({d['change_pct']:+.2f}%)")

    # Asia
    lines.append("")
    lines.append("■ 아시아 증시")
    for name in ["코스피", "코스닥", "닛케이225", "항셍", "상해종합"]:
        d = market_data.get(name, {})
        if d:
            lines.append(f"  {name}: {d['close']:,.2f} ({d['change_pct']:+.2f}%)")

    # Europe
    lines.append("")
    lines.append("■ 유럽 증시")
    for name in ["DAX", "FTSE100"]:
        d = market_data.get(name, {})
        if d:
            lines.append(f"  {name}: {d['close']:,.2f} ({d['change_pct']:+.2f}%)")

    # VIX + Bonds
    lines.append("")
    lines.append("■ 변동성 & 금리")
    vix = market_data.get("VIX", {})
    if vix:
        level = "안정" if vix["close"] < 15 else "보통" if vix["close"] < 25 else "경고" if vix["close"] < 35 else "공포"
        lines.append(f"  VIX: {vix['close']:.1f} ({vix['change_pct']:+.1f}%) [{level}]")
    for name in ["미국2Y금리", "미국10Y금리", "미국30Y금리"]:
        d = market_data.get(name, {})
        if d:
            lines.append(f"  {name}: {d['close']:.3f}% ({d['change_pct']:+.2f}%)")
    # Yield curve
    y2 = market_data.get("미국2Y금리", {}).get("close", 0)
    y10 = market_data.get("미국10Y금리", {}).get("close", 0)
    if y2 and y10:
        spread = y10 - y2
        status = "정상" if spread > 0 else "역전 (경기침체 신호)"
        lines.append(f"  10Y-2Y 스프레드: {spread:+.3f}% [{status}]")

    # Commodities
    lines.append("")
    lines.append("■ 원자재 & 에너지")
    for name in ["WTI 원유", "브렌트유", "금", "은", "구리", "천연가스"]:
        d = market_data.get(name, {})
        if d:
            lines.append(f"  {name}: ${d['close']:,.2f} ({d['change_pct']:+.2f}%)")

    # FX
    lines.append("")
    lines.append("■ 환율")
    for name in ["USD/KRW", "달러인덱스", "EUR/USD", "USD/JPY"]:
        d = market_data.get(name, {})
        if d:
            lines.append(f"  {name}: {d['close']:,.2f} ({d['change_pct']:+.2f}%)")

    # Active Themes
    if themes:
        lines.append("")
        lines.append("■ 활성 테마 (한국 대장주)")
        for t in themes[:5]:
            lines.append(f"  [{t['name']}] 관련도: {t['relevance_score']}/10")
            for sig in t["signals"][:3]:
                lines.append(f"    - {sig}")
            leaders = ", ".join(f"{name}({code})" for code, name in t["leader_stocks"])
            lines.append(f"    대장주: {leaders}")

    lines.append("")
    lines.append("→ 위 데이터를 기반으로 오늘의 한국 증시 전망과 투자 전략을 작성하세요.")

    return "\n".join(lines)


async def generate_ai_briefing(fact_sheet: str, api_key: str) -> dict:
    """Generate AI daily briefing using DeepSeek."""
    from openai import AsyncOpenAI

    system_prompt = """당신은 ABLE 플랫폼의 데일리 시장 분석가입니다.

역할:
- 글로벌 시장 데이터를 해석하여 한국 증시 전망을 제시합니다
- 테마/섹터 분석과 대장주를 추천합니다
- 투자자가 아침에 빠르게 읽을 수 있도록 핵심만 전달합니다

응답 형식 (반드시 준수):
1. 오늘의 시장 한줄 요약 (20자 이내)
2. 시장 심리: 탐욕 / 중립 / 공포
3. 코스피 예상 방향: 상승 / 보합 / 하락
4. 핵심 이슈 3가지 (각 2줄 이내, 숫자 인용)
5. 주목 테마 & 대장주 (상위 3개)
6. 리스크 요인 2가지
7. 오늘의 투자 전략 (3줄 이내)

간결하고 실전적으로. 한국어로."""

    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )

        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": fact_sheet},
            ],
            temperature=0.3,
            max_tokens=1200,
        )

        ai_text = response.choices[0].message.content or ""
        usage = response.usage

        # Parse structured response
        parsed = _parse_briefing(ai_text)
        parsed["raw_text"] = ai_text
        parsed["tokens_used"] = {
            "prompt": usage.prompt_tokens if usage else 0,
            "completion": usage.completion_tokens if usage else 0,
            "total": usage.total_tokens if usage else 0,
        }

        logger.info("Daily briefing generated (tokens: %s)", parsed["tokens_used"]["total"])
        return parsed

    except Exception as e:
        logger.error("DeepSeek daily briefing failed: %s", e)
        return {
            "error": str(e),
            "headline": "AI 브리핑 생성 실패",
            "market_sentiment": "중립",
            "kospi_direction": "보합",
            "raw_text": "",
        }


def _parse_briefing(text: str) -> dict:
    """Parse the AI briefing response into structured fields."""
    result = {
        "headline": "",
        "market_sentiment": "중립",
        "kospi_direction": "보합",
        "key_issues": [],
        "top_themes": [],
        "risks": [],
        "strategy": "",
    }

    lines = text.strip().split("\n")
    current_section = None

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Headline
        if "한줄 요약" in line_stripped or "한줄요약" in line_stripped:
            parts = line_stripped.split(":", 1) if ":" in line_stripped else line_stripped.split("：", 1)
            if len(parts) > 1:
                result["headline"] = parts[1].strip().strip("*").strip()
            current_section = "headline"
            continue

        # Market sentiment
        if "시장 심리" in line_stripped or "시장심리" in line_stripped:
            if "탐욕" in line_stripped:
                result["market_sentiment"] = "탐욕"
            elif "공포" in line_stripped:
                result["market_sentiment"] = "공포"
            else:
                result["market_sentiment"] = "중립"
            current_section = "sentiment"
            continue

        # KOSPI direction
        if "코스피" in line_stripped and ("예상" in line_stripped or "방향" in line_stripped):
            if "상승" in line_stripped:
                result["kospi_direction"] = "상승"
            elif "하락" in line_stripped:
                result["kospi_direction"] = "하락"
            else:
                result["kospi_direction"] = "보합"
            current_section = "kospi"
            continue

        # Key issues
        if "핵심 이슈" in line_stripped or "핵심이슈" in line_stripped:
            current_section = "issues"
            continue

        # Themes
        if "주목 테마" in line_stripped or "테마" in line_stripped and "대장주" in line_stripped:
            current_section = "themes"
            continue

        # Risks
        if "리스크" in line_stripped:
            current_section = "risks"
            continue

        # Strategy
        if "투자 전략" in line_stripped or "투자전략" in line_stripped:
            current_section = "strategy"
            continue

        # Collect content based on current section
        if current_section == "issues" and (line_stripped.startswith("-") or line_stripped[0:1].isdigit()):
            result["key_issues"].append(line_stripped.lstrip("-").lstrip("0123456789.").strip())
        elif current_section == "themes" and (line_stripped.startswith("-") or line_stripped[0:1].isdigit()):
            result["top_themes"].append(line_stripped.lstrip("-").lstrip("0123456789.").strip())
        elif current_section == "risks" and (line_stripped.startswith("-") or line_stripped[0:1].isdigit()):
            result["risks"].append(line_stripped.lstrip("-").lstrip("0123456789.").strip())
        elif current_section == "strategy":
            result["strategy"] += line_stripped + " "

    result["strategy"] = result["strategy"].strip()

    # Fallback: if headline empty, use first meaningful line
    if not result["headline"]:
        for l in lines:
            if l.strip() and len(l.strip()) > 5:
                result["headline"] = l.strip()[:50]
                break

    return result


async def generate_daily_report() -> dict:
    """Main entry point: fetch data, analyze themes, generate AI briefing, save to DB."""
    from app.config import get_settings
    from app.db.session import async_session_factory
    from app.models.daily_report import DailyMarketReport
    from sqlalchemy import select

    settings = get_settings()
    today = date.today()

    logger.info("Starting daily market intelligence for %s", today)

    # Check if already generated today
    async with async_session_factory() as db:
        existing = await db.execute(
            select(DailyMarketReport).where(DailyMarketReport.report_date == today)
        )
        if existing.scalar_one_or_none():
            logger.info("Daily report already exists for %s, skipping", today)
            return {"status": "already_exists", "date": str(today)}

    # Step 1: Fetch global market data (synchronous yfinance)
    import asyncio
    market_data = await asyncio.to_thread(fetch_global_market_data)
    logger.info("Fetched %d market data points", len(market_data))

    # Step 2: Detect active themes
    themes = detect_active_themes(market_data)
    logger.info("Detected %d active themes", len(themes))

    # Step 3: Build fact sheet for AI
    fact_sheet = build_market_fact_sheet(market_data, themes)

    # Step 4: Generate AI briefing
    api_key = settings.deepseek_api_key
    ai_summary = {}
    ai_raw_text = ""

    if api_key:
        ai_summary = await generate_ai_briefing(fact_sheet, api_key)
        ai_raw_text = ai_summary.pop("raw_text", "")
    else:
        ai_summary = {
            "headline": "AI 키 미설정 — 시장 데이터만 제공",
            "market_sentiment": "중립",
            "kospi_direction": "보합",
        }
        logger.warning("No DeepSeek API key configured, skipping AI briefing")

    # Step 5: Save to DB
    async with async_session_factory() as db:
        report = DailyMarketReport(
            report_date=today,
            status="completed",
            market_data=market_data,
            themes=[
                {
                    "name": t["name"],
                    "relevance_score": t["relevance_score"],
                    "signals": t["signals"],
                    "leader_stocks": [{"code": c, "name": n} for c, n in t["leader_stocks"]],
                    "follower_stocks": [{"code": c, "name": n} for c, n in t["follower_stocks"]],
                }
                for t in themes
            ],
            ai_summary=ai_summary,
            ai_raw_text=ai_raw_text,
        )
        db.add(report)
        await db.commit()
        logger.info("Daily market report saved for %s", today)

    return {
        "status": "completed",
        "date": str(today),
        "market_data_count": len(market_data),
        "active_themes": len(themes),
        "ai_headline": ai_summary.get("headline", ""),
    }
