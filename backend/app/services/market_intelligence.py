"""Daily Market Intelligence Service.

Two report types:
  Morning (프리마켓) — 06:30 KST:
    1. Fetch global indices + commodities + FX + bonds
    2. Fetch individual US bellwether stocks + sector ETFs
    3. Rank US stocks by daily performance (top gainers/losers)
    4. Detect active Korean themes from US stock movements
    5. Generate Korean watchlist (관심종목) based on theme scores
    6. Fetch market news (US + Korean)
    7. Build rich fact sheet → AI analysis (GPT-4o)
    8. Save to DB

  Closing (장마감) — 16:00 KST:
    1. Fetch Korean market actual results
    2. Detect Korean top movers + unusual volume
    3. Fetch Korean market news
    4. Build closing fact sheet → AI analysis
    5. Save to DB

No user API key required — uses system AI key.
"""

import logging
from datetime import datetime, date
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger("able.market_intel")


# ─── KOSPI Trading Day Check ──────────────────────────────────────────

# Korean public holidays (fixed dates, approximate — need yearly updates)
# format: (month, day)
KR_FIXED_HOLIDAYS = [
    (1, 1),    # 신정
    (3, 1),    # 삼일절
    (5, 1),    # 근로자의 날 (stock market closed)
    (5, 5),    # 어린이날
    (6, 6),    # 현충일
    (8, 15),   # 광복절
    (10, 3),   # 개천절
    (10, 9),   # 한글날
    (12, 25),  # 크리스마스
    (12, 31),  # 연말 (거래소 휴장)
]

# Lunar holidays vary by year — these are approximate 2025-2027 dates
# In production, use a proper KRX holiday API or calendar
KR_LUNAR_HOLIDAYS = {
    # 2025: 설날 1/28-1/30, 추석 10/5-10/7, 부처님오신날 5/5
    2025: [(1, 28), (1, 29), (1, 30), (5, 5), (10, 5), (10, 6), (10, 7)],
    # 2026: 설날 2/16-2/18, 추석 9/24-9/26, 부처님오신날 5/24
    2026: [(2, 16), (2, 17), (2, 18), (5, 24), (9, 24), (9, 25), (9, 26)],
    # 2027: 설날 2/5-2/7, 추석 10/13-10/15, 부처님오신날 5/13
    2027: [(2, 5), (2, 6), (2, 7), (5, 13), (10, 13), (10, 14), (10, 15)],
}


def is_kospi_trading_day(d: date | None = None) -> bool:
    """Check if the given date is a KOSPI trading day.

    Returns False for weekends and Korean public holidays.
    """
    if d is None:
        d = date.today()

    # Weekend check
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    # Fixed holidays
    if (d.month, d.day) in KR_FIXED_HOLIDAYS:
        return False

    # Lunar holidays (year-specific)
    lunar = KR_LUNAR_HOLIDAYS.get(d.year, [])
    if (d.month, d.day) in lunar:
        return False

    return True

# ─── Global Market Tickers ──────────────────────────────────────────

GLOBAL_MARKETS = {
    "S&P 500": "^GSPC",
    "나스닥": "^IXIC",
    "다우존스": "^DJI",
    "러셀2000": "^RUT",
    "코스피": "^KS11",
    "코스닥": "^KQ11",
    "닛케이225": "^N225",
    "항셍": "^HSI",
    "상해종합": "000001.SS",
    "DAX": "^GDAXI",
    "FTSE100": "^FTSE",
    "VIX": "^VIX",
}

COMMODITIES_FX = {
    "WTI 원유": "CL=F",
    "브렌트유": "BZ=F",
    "금": "GC=F",
    "은": "SI=F",
    "구리": "HG=F",
    "천연가스": "NG=F",
    "USD/KRW": "KRW=X",
    "달러인덱스": "DX-Y.NYB",
    "EUR/USD": "EURUSD=X",
    "USD/JPY": "JPY=X",
    "미국2Y금리": "^IRX",
    "미국10Y금리": "^TNX",
    "미국30Y금리": "^TYX",
    "S&P500선물": "ES=F",
    "나스닥선물": "NQ=F",
}

# ─── US Sector ETFs → Korean Theme Mapping ───────────────────────────

US_SECTOR_ETFS = {
    "SOXX": {"name": "Semiconductor", "kr_name": "반도체", "themes": ["AI/반도체"]},
    "XLK": {"name": "Technology", "kr_name": "기술", "themes": ["AI/반도체", "인터넷/플랫폼"]},
    "XLE": {"name": "Energy", "kr_name": "에너지", "themes": ["원자력/에너지"]},
    "XLF": {"name": "Financials", "kr_name": "금융", "themes": ["금융/은행"]},
    "XLV": {"name": "Healthcare", "kr_name": "헬스케어", "themes": ["바이오/제약"]},
    "XLI": {"name": "Industrials", "kr_name": "산업재", "themes": ["방산/우주항공", "로봇/자동화"]},
    "XLC": {"name": "Communication", "kr_name": "커뮤니케이션", "themes": ["인터넷/플랫폼"]},
    "XLY": {"name": "Consumer Disc.", "kr_name": "임의소비재", "themes": ["자동차/모빌리티"]},
    "XBI": {"name": "Biotech", "kr_name": "바이오", "themes": ["바이오/제약"]},
    "ITA": {"name": "Aerospace & Defense", "kr_name": "방산/항공", "themes": ["방산/우주항공"]},
    "XLB": {"name": "Materials", "kr_name": "소재", "themes": ["2차전지/배터리"]},
}

# ─── US Bellwether Stocks → Korean Theme Mapping ─────────────────────

US_BELLWETHER_STOCKS = {
    # AI / Semiconductor
    "NVDA": {"name": "NVIDIA", "themes": ["AI/반도체"]},
    "AMD": {"name": "AMD", "themes": ["AI/반도체"]},
    "AVGO": {"name": "Broadcom", "themes": ["AI/반도체"]},
    "TSM": {"name": "TSMC", "themes": ["AI/반도체"]},
    "ASML": {"name": "ASML", "themes": ["AI/반도체"]},
    "MU": {"name": "Micron", "themes": ["AI/반도체"]},
    "INTC": {"name": "Intel", "themes": ["AI/반도체"]},
    "QCOM": {"name": "Qualcomm", "themes": ["AI/반도체"]},
    "AMAT": {"name": "Applied Materials", "themes": ["AI/반도체"]},
    "LRCX": {"name": "Lam Research", "themes": ["AI/반도체"]},
    "KLAC": {"name": "KLA Corp", "themes": ["AI/반도체"]},
    # Big Tech
    "MSFT": {"name": "Microsoft", "themes": ["AI/반도체", "인터넷/플랫폼"]},
    "AAPL": {"name": "Apple", "themes": ["AI/반도체"]},
    "GOOGL": {"name": "Alphabet", "themes": ["AI/반도체", "인터넷/플랫폼"]},
    "META": {"name": "Meta", "themes": ["인터넷/플랫폼"]},
    "AMZN": {"name": "Amazon", "themes": ["인터넷/플랫폼"]},
    "NFLX": {"name": "Netflix", "themes": ["인터넷/플랫폼"]},
    "ORCL": {"name": "Oracle", "themes": ["AI/반도체"]},
    "CRM": {"name": "Salesforce", "themes": ["AI/반도체"]},
    "PLTR": {"name": "Palantir", "themes": ["AI/반도체"]},
    # EV / Battery
    "TSLA": {"name": "Tesla", "themes": ["2차전지/배터리", "자동차/모빌리티", "로봇/자동화"]},
    "RIVN": {"name": "Rivian", "themes": ["2차전지/배터리"]},
    "LI": {"name": "Li Auto", "themes": ["2차전지/배터리"]},
    "NIO": {"name": "NIO", "themes": ["2차전지/배터리"]},
    "ALB": {"name": "Albemarle", "themes": ["2차전지/배터리"]},
    # Energy / Nuclear
    "XOM": {"name": "ExxonMobil", "themes": ["원자력/에너지", "조선/해양"]},
    "CVX": {"name": "Chevron", "themes": ["원자력/에너지", "조선/해양"]},
    "COP": {"name": "ConocoPhillips", "themes": ["원자력/에너지"]},
    "CEG": {"name": "Constellation Energy", "themes": ["원자력/에너지"]},
    "VST": {"name": "Vistra", "themes": ["원자력/에너지"]},
    # Defense / Aerospace
    "LMT": {"name": "Lockheed Martin", "themes": ["방산/우주항공"]},
    "RTX": {"name": "RTX Corp", "themes": ["방산/우주항공"]},
    "NOC": {"name": "Northrop Grumman", "themes": ["방산/우주항공"]},
    "GD": {"name": "General Dynamics", "themes": ["방산/우주항공"]},
    "BA": {"name": "Boeing", "themes": ["방산/우주항공"]},
    # Biotech / Pharma
    "LLY": {"name": "Eli Lilly", "themes": ["바이오/제약"]},
    "NVO": {"name": "Novo Nordisk", "themes": ["바이오/제약"]},
    "AMGN": {"name": "Amgen", "themes": ["바이오/제약"]},
    "MRNA": {"name": "Moderna", "themes": ["바이오/제약"]},
    # Finance
    "JPM": {"name": "JPMorgan", "themes": ["금융/은행"]},
    "GS": {"name": "Goldman Sachs", "themes": ["금융/은행"]},
    "BAC": {"name": "Bank of America", "themes": ["금융/은행"]},
    "MS": {"name": "Morgan Stanley", "themes": ["금융/은행"]},
    # Robot / Automation
    "ISRG": {"name": "Intuitive Surgical", "themes": ["로봇/자동화"]},
    # Marine / Shipbuilding adjacent
    "SLB": {"name": "SLB", "themes": ["조선/해양"]},
    "HAL": {"name": "Halliburton", "themes": ["조선/해양"]},
    # Auto
    "GM": {"name": "General Motors", "themes": ["자동차/모빌리티"]},
    "F": {"name": "Ford", "themes": ["자동차/모빌리티"]},
}

# ─── Korean Theme → Leader Stock Mapping ─────────────────────────────

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


# ─── Korean Bellwether Stocks (for closing report) ─────────────────────

KR_BELLWETHER_STOCKS = {
    # AI/반도체
    "005930": {"name": "삼성전자", "yf": "005930.KS", "theme": "AI/반도체"},
    "000660": {"name": "SK하이닉스", "yf": "000660.KS", "theme": "AI/반도체"},
    "042700": {"name": "한미반도체", "yf": "042700.KS", "theme": "AI/반도체"},
    # 2차전지
    "373220": {"name": "LG에너지솔루션", "yf": "373220.KS", "theme": "2차전지/배터리"},
    "006400": {"name": "삼성SDI", "yf": "006400.KS", "theme": "2차전지/배터리"},
    "247540": {"name": "에코프로비엠", "yf": "247540.KQ", "theme": "2차전지/배터리"},
    "086520": {"name": "에코프로", "yf": "086520.KQ", "theme": "2차전지/배터리"},
    # 바이오
    "207940": {"name": "삼성바이오로직스", "yf": "207940.KS", "theme": "바이오/제약"},
    "068270": {"name": "셀트리온", "yf": "068270.KS", "theme": "바이오/제약"},
    # 방산
    "012450": {"name": "한화에어로스페이스", "yf": "012450.KS", "theme": "방산/우주항공"},
    "047810": {"name": "한국항공우주", "yf": "047810.KS", "theme": "방산/우주항공"},
    # 자동차
    "005380": {"name": "현대차", "yf": "005380.KS", "theme": "자동차/모빌리티"},
    "000270": {"name": "기아", "yf": "000270.KS", "theme": "자동차/모빌리티"},
    # 인터넷
    "035420": {"name": "NAVER", "yf": "035420.KS", "theme": "인터넷/플랫폼"},
    "035720": {"name": "카카오", "yf": "035720.KS", "theme": "인터넷/플랫폼"},
    # 금융
    "105560": {"name": "KB금융", "yf": "105560.KS", "theme": "금융/은행"},
    "055550": {"name": "신한지주", "yf": "055550.KS", "theme": "금융/은행"},
    # 조선/에너지
    "329180": {"name": "HD현대중공업", "yf": "329180.KS", "theme": "조선/해양"},
    "009540": {"name": "HD한국조선해양", "yf": "009540.KS", "theme": "조선/해양"},
    # 원자력
    "034020": {"name": "두산에너빌리티", "yf": "034020.KS", "theme": "원자력/에너지"},
    # 로봇
    "090460": {"name": "비에이치", "yf": "090460.KQ", "theme": "로봇/자동화"},
    "336570": {"name": "원텍", "yf": "336570.KQ", "theme": "바이오/제약"},
    # 대형주
    "051910": {"name": "LG화학", "yf": "051910.KS", "theme": "2차전지/배터리"},
    "028260": {"name": "삼성물산", "yf": "028260.KS", "theme": "금융/은행"},
    "003670": {"name": "포스코퓨처엠", "yf": "003670.KS", "theme": "2차전지/배터리"},
}

# ─── Korean News RSS Sources ──────────────────────────────────────────

KR_NEWS_RSS = {
    "매일경제 증시": "https://www.mk.co.kr/rss/30100041/",
    "한경 증시": "https://www.hankyung.com/feed/stock",
    "연합뉴스 경제": "https://www.yna.co.kr/rss/economy.xml",
}


def _bulk_download_tickers(tickers: dict[str, str]) -> dict[str, dict]:
    """Download data for multiple tickers via yfinance bulk download.

    Returns dict of {name: {ticker, close, change, change_pct, volume}}.
    """
    import yfinance as yf

    if not tickers:
        return {}

    ticker_list = list(tickers.values())
    results = {}

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
        return {}

    for name, ticker in tickers.items():
        try:
            if len(ticker_list) == 1:
                ticker_data = data
            else:
                ticker_data = data[ticker] if ticker in data.columns.get_level_values(0) else pd.DataFrame()

            if ticker_data.empty or len(ticker_data) < 1:
                continue

            if hasattr(ticker_data.columns, "levels"):
                ticker_data.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in ticker_data.columns]
            else:
                ticker_data.columns = [c.lower() for c in ticker_data.columns]

            last = ticker_data.dropna(subset=["close"]).iloc[-1]
            close = float(last["close"])

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


def fetch_global_market_data() -> dict[str, Any]:
    """Fetch all global indices + commodities + FX + bonds data."""
    all_tickers = {**GLOBAL_MARKETS, **COMMODITIES_FX}
    return _bulk_download_tickers(all_tickers)


def fetch_us_stock_data() -> dict[str, Any]:
    """Fetch individual US bellwether stocks + sector ETFs.

    Returns:
        {
            "stocks": {ticker: {name, close, change, change_pct, volume, themes}},
            "sectors": {ticker: {name, kr_name, close, change_pct, themes}},
            "rankings": {"gainers": [...top 10], "losers": [...top 10]},
        }
    """
    # Build ticker maps
    stock_tickers = {ticker: ticker for ticker in US_BELLWETHER_STOCKS}
    etf_tickers = {ticker: ticker for ticker in US_SECTOR_ETFS}

    # Bulk download all US stocks + ETFs together
    all_tickers = {**stock_tickers, **etf_tickers}
    raw = _bulk_download_tickers(all_tickers)

    # Separate stocks and sectors
    stocks = {}
    for ticker, info in US_BELLWETHER_STOCKS.items():
        d = raw.get(ticker)
        if d:
            stocks[ticker] = {
                **d,
                "name": info["name"],
                "themes": info["themes"],
            }

    sectors = {}
    for ticker, info in US_SECTOR_ETFS.items():
        d = raw.get(ticker)
        if d:
            sectors[ticker] = {
                **d,
                "name": info["name"],
                "kr_name": info["kr_name"],
                "themes": info["themes"],
            }

    # Rank stocks by change_pct
    sorted_stocks = sorted(stocks.items(), key=lambda x: x[1]["change_pct"], reverse=True)
    gainers = [
        {"ticker": t, "name": s["name"], "close": s["close"], "change_pct": s["change_pct"], "themes": s["themes"]}
        for t, s in sorted_stocks[:10] if s["change_pct"] > 0
    ]
    losers = [
        {"ticker": t, "name": s["name"], "close": s["close"], "change_pct": s["change_pct"], "themes": s["themes"]}
        for t, s in sorted_stocks[-10:][::-1] if s["change_pct"] < 0
    ]
    # Sort losers by most negative first
    losers.sort(key=lambda x: x["change_pct"])

    return {
        "stocks": stocks,
        "sectors": sectors,
        "rankings": {"gainers": gainers, "losers": losers},
    }


def detect_active_themes(market_data: dict, us_data: dict | None = None) -> list[dict]:
    """Detect active Korean stock themes from US stock movements.

    NEW: Uses individual US stock performance for dynamic theme detection,
    not just index-level rules.
    """
    theme_scores: dict[str, dict] = {}

    for theme_name, theme_info in THEME_STOCK_MAP.items():
        theme_scores[theme_name] = {
            "relevance_score": 0,
            "signals": [],
            "us_movers": [],
        }

    # ── Phase 1: Score from individual US stocks ────────────────
    if us_data:
        stocks = us_data.get("stocks", {})
        for ticker, stock in stocks.items():
            chg = stock.get("change_pct", 0)
            if abs(chg) < 0.5:
                continue  # Skip small moves

            for theme_name in stock.get("themes", []):
                if theme_name not in theme_scores:
                    continue
                ts = theme_scores[theme_name]

                # Score based on magnitude: bigger moves = higher relevance
                if abs(chg) >= 3:
                    ts["relevance_score"] += 3
                elif abs(chg) >= 2:
                    ts["relevance_score"] += 2
                elif abs(chg) >= 1:
                    ts["relevance_score"] += 1

                direction = "상승" if chg > 0 else "하락"
                ts["us_movers"].append({
                    "ticker": ticker,
                    "name": stock["name"],
                    "change_pct": chg,
                })
                ts["signals"].append(f"{stock['name']}({ticker}) {chg:+.1f}% {direction}")

        # ── Phase 1b: Score from sector ETFs ────────────────────
        sectors = us_data.get("sectors", {})
        for etf_ticker, sector in sectors.items():
            chg = sector.get("change_pct", 0)
            if abs(chg) < 0.5:
                continue

            for theme_name in sector.get("themes", []):
                if theme_name not in theme_scores:
                    continue
                ts = theme_scores[theme_name]
                if abs(chg) >= 2:
                    ts["relevance_score"] += 2
                elif abs(chg) >= 1:
                    ts["relevance_score"] += 1
                ts["signals"].append(f"{sector['kr_name']} ETF({etf_ticker}) {chg:+.1f}%")

    # ── Phase 2: Additional signals from macro data ─────────────
    vix = market_data.get("VIX", {})
    krw = market_data.get("USD/KRW", {})
    oil = market_data.get("WTI 원유", {})
    gas = market_data.get("천연가스", {})
    copper = market_data.get("구리", {})
    tnx = market_data.get("미국10Y금리", {})

    # VIX spike — warn all themes
    vix_val = vix.get("close", 0)
    if vix_val > 25:
        for ts in theme_scores.values():
            ts["signals"].append(f"VIX {vix_val:.0f} — 변동성 확대 주의")
            ts["relevance_score"] = max(ts["relevance_score"], 2)

    # FX impact on exporters
    if krw.get("change_pct", 0) > 0.5:
        for name in ["AI/반도체", "자동차/모빌리티"]:
            if name in theme_scores:
                theme_scores[name]["signals"].append(f"원/달러 {krw['change_pct']:+.1f}% — 수출주 환율효과")
                theme_scores[name]["relevance_score"] += 1

    # Commodity-specific boosts
    if oil.get("change_pct", 0) > 2:
        for name in ["원자력/에너지", "조선/해양"]:
            if name in theme_scores:
                theme_scores[name]["signals"].append(f"WTI {oil['change_pct']:+.1f}%")
                theme_scores[name]["relevance_score"] += 1

    if copper.get("change_pct", 0) > 1.5:
        if "2차전지/배터리" in theme_scores:
            theme_scores["2차전지/배터리"]["signals"].append(f"구리 {copper['change_pct']:+.1f}% (EV 수요 신호)")
            theme_scores["2차전지/배터리"]["relevance_score"] += 1

    if abs(tnx.get("change_pct", 0)) > 2:
        if "금융/은행" in theme_scores:
            theme_scores["금융/은행"]["signals"].append(f"미국10Y금리 {tnx['change_pct']:+.1f}%")
            theme_scores["금융/은행"]["relevance_score"] += 1

    # ── Phase 3: Build result list ──────────────────────────────
    active_themes = []
    for theme_name, ts in theme_scores.items():
        if ts["relevance_score"] < 2:
            continue

        theme_info = THEME_STOCK_MAP[theme_name]
        # Sort us_movers by absolute change
        us_movers = sorted(ts["us_movers"], key=lambda x: abs(x["change_pct"]), reverse=True)

        active_themes.append({
            "name": theme_name,
            "relevance_score": min(ts["relevance_score"], 10),
            "signals": ts["signals"][:5],
            "us_movers": us_movers[:5],
            "leader_stocks": theme_info["leader"],
            "follower_stocks": theme_info["follower"],
        })

    active_themes.sort(key=lambda x: x["relevance_score"], reverse=True)
    return active_themes


def generate_watchlist(themes: list[dict], market_data: dict) -> list[dict]:
    """Generate Korean watchlist (관심종목) from active themes.

    Direction-aware: only recommends stocks from BULLISH themes.
    Bearish themes are flagged as risk/watch, not buy recommendations.
    """
    watchlist = []
    seen_codes = set()

    for theme in themes[:7]:
        if theme["relevance_score"] < 3:
            continue

        # Determine theme direction: are the US movers mostly up or down?
        us_movers = theme.get("us_movers", [])
        avg_change = 0.0
        if us_movers:
            avg_change = sum(m["change_pct"] for m in us_movers) / len(us_movers)

        # Skip bearish themes for buy recommendations
        # (these go into risk factors, not watchlist)
        if avg_change < -1.0:
            continue

        # Determine recommendation type based on strength
        if avg_change > 2.0:
            action = "강세 수혜"
        elif avg_change > 0.5:
            action = "소폭 상승"
        else:
            action = "모멘텀 관찰"

        # Pick leaders first, then followers
        for code, name in theme["leader_stocks"][:2]:
            if code in seen_codes:
                continue
            seen_codes.add(code)

            us_reasons = []
            for m in us_movers[:3]:
                us_reasons.append(f"{m['name']} {m['change_pct']:+.1f}%")

            reason_parts = [f"{theme['name']} 테마 ({action})"]
            if us_reasons:
                reason_parts.append(" — " + ", ".join(us_reasons))

            watchlist.append({
                "code": code,
                "name": name,
                "theme": theme["name"],
                "role": "대장주",
                "relevance": theme["relevance_score"],
                "us_drivers": us_reasons,
                "reason": "".join(reason_parts),
            })

        # Add one follower per theme (only for strong themes)
        if avg_change > 1.0:
            for code, name in theme["follower_stocks"][:1]:
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                watchlist.append({
                    "code": code,
                    "name": name,
                    "theme": theme["name"],
                    "role": "수혜주",
                    "relevance": theme["relevance_score"],
                    "us_drivers": [],
                    "reason": f"{theme['name']} 수혜주 ({action})",
                })

    # Sort by relevance
    watchlist.sort(key=lambda x: x["relevance"], reverse=True)
    return watchlist[:10]


# ─── News Fetching ──────────────────────────────────────────────────

def fetch_market_news() -> dict:
    """Fetch market news from US stocks (yfinance) and Korean RSS feeds.

    Returns: {"us_news": [...], "kr_news": [...]}
    """
    us_news = _fetch_us_news()
    kr_news = _fetch_kr_news()
    return {"us_news": us_news, "kr_news": kr_news}


def _fetch_us_news() -> list[dict]:
    """Fetch news for top US market movers via yfinance."""
    import yfinance as yf

    news_items = []
    # Fetch news for key market-moving tickers
    key_tickers = ["NVDA", "AAPL", "TSLA", "MSFT", "AMZN", "META", "SPY"]

    for ticker_symbol in key_tickers:
        try:
            ticker = yf.Ticker(ticker_symbol)
            ticker_news = ticker.news or []
            for item in ticker_news[:2]:  # Max 2 per ticker
                content = item.get("content", {})
                title = content.get("title", "")
                summary = content.get("summary", "")
                provider = content.get("provider", {}).get("displayName", "")
                pub_date = content.get("pubDate", "")

                if title and title not in [n["title"] for n in news_items]:
                    news_items.append({
                        "title": title,
                        "summary": summary[:200] if summary else "",
                        "source": provider,
                        "published": pub_date,
                        "ticker": ticker_symbol,
                    })
        except Exception as e:
            logger.debug("Failed to fetch news for %s: %s", ticker_symbol, e)

    return news_items[:15]


def _fetch_kr_news() -> list[dict]:
    """Fetch Korean financial news via RSS feeds."""
    import feedparser

    news_items = []

    for source_name, rss_url in KR_NEWS_RSS.items():
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:5]:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                link = entry.get("link", "")
                published = entry.get("published", "")

                if title and title not in [n["title"] for n in news_items]:
                    news_items.append({
                        "title": title,
                        "summary": summary[:200] if summary else "",
                        "source": source_name,
                        "link": link,
                        "published": published,
                    })
        except Exception as e:
            logger.debug("Failed to fetch %s RSS: %s", source_name, e)

    return news_items[:20]


# ─── Korean Market Data (for Closing Report) ────────────────────────

def fetch_kr_market_data() -> dict:
    """Fetch Korean bellwether stock data for closing report.

    Returns: {"stocks": {...}, "rankings": {"gainers": [...], "losers": [...]}}
    """
    import yfinance as yf

    tickers_map = {info["yf"]: code for code, info in KR_BELLWETHER_STOCKS.items()}
    ticker_list = list(tickers_map.keys())
    stocks = {}

    try:
        data = yf.download(
            ticker_list,
            period="5d",
            group_by="ticker",
            threads=True,
            progress=False,
        )

        for yf_ticker, stock_code in tickers_map.items():
            info = KR_BELLWETHER_STOCKS[stock_code]
            try:
                if len(ticker_list) == 1:
                    ticker_data = data
                else:
                    ticker_data = data[yf_ticker]

                ticker_data = ticker_data.dropna()
                if len(ticker_data) < 2:
                    continue

                current = ticker_data.iloc[-1]
                prev = ticker_data.iloc[-2]

                close_val = float(current["Close"])
                prev_close = float(prev["Close"])
                change = close_val - prev_close
                change_pct = (change / prev_close * 100) if prev_close != 0 else 0
                volume = int(current["Volume"])

                stocks[stock_code] = {
                    "code": stock_code,
                    "name": info["name"],
                    "theme": info["theme"],
                    "close": close_val,
                    "change": round(change, 0),
                    "change_pct": round(change_pct, 2),
                    "volume": volume,
                }
            except Exception as e:
                logger.debug("Failed to process KR stock %s: %s", stock_code, e)

    except Exception as e:
        logger.error("Failed to download KR bellwether data: %s", e)

    # Build rankings
    stock_list = list(stocks.values())
    stock_list.sort(key=lambda x: x["change_pct"], reverse=True)

    gainers = [s for s in stock_list if s["change_pct"] > 0][:10]
    losers = [s for s in reversed(stock_list) if s["change_pct"] < 0][:10]

    return {
        "stocks": stocks,
        "rankings": {"gainers": gainers, "losers": losers},
    }


def build_market_fact_sheet(
    market_data: dict,
    us_data: dict | None,
    themes: list[dict],
    watchlist: list[dict] | None = None,
    news: dict | None = None,
) -> str:
    """Build a comprehensive fact sheet for AI analysis.

    Includes: indices, US stock rankings, sector performance,
    commodities/FX/bonds, active themes, watchlist candidates, and news.
    """
    lines = []
    now = datetime.now()
    dow_kr = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}

    lines.append("[일일 시장 인텔리전스 팩트시트]")
    lines.append(f"기준일: {now.strftime('%Y-%m-%d')} ({dow_kr.get(now.weekday(), '')}요일)")
    lines.append("")

    # ── US Markets ───────────────────────────────────────────────
    lines.append("■ 미국 증시")
    for name in ["S&P 500", "나스닥", "다우존스", "러셀2000"]:
        d = market_data.get(name, {})
        if d:
            lines.append(f"  {name}: {d['close']:,.2f} ({d['change_pct']:+.2f}%)")

    # ── US Top Gainers / Losers ──────────────────────────────────
    if us_data:
        rankings = us_data.get("rankings", {})
        gainers = rankings.get("gainers", [])
        losers = rankings.get("losers", [])

        if gainers:
            lines.append("")
            lines.append("■ 미국 상승 주도주 (Top Gainers)")
            for i, g in enumerate(gainers[:10], 1):
                theme_str = ", ".join(g.get("themes", []))
                lines.append(f"  {i}. {g['name']}({g['ticker']}) ${g['close']:,.2f} {g['change_pct']:+.2f}% → [{theme_str}]")

        if losers:
            lines.append("")
            lines.append("■ 미국 하락 주도주 (Top Losers)")
            for i, l in enumerate(losers[:10], 1):
                theme_str = ", ".join(l.get("themes", []))
                lines.append(f"  {i}. {l['name']}({l['ticker']}) ${l['close']:,.2f} {l['change_pct']:+.2f}% → [{theme_str}]")

        # ── US Sector ETF Performance ────────────────────────────
        sectors = us_data.get("sectors", {})
        if sectors:
            lines.append("")
            lines.append("■ 미국 섹터 ETF 성과")
            sorted_sectors = sorted(sectors.items(), key=lambda x: x[1].get("change_pct", 0), reverse=True)
            for ticker, sec in sorted_sectors:
                lines.append(f"  {sec['kr_name']}({ticker}): {sec['change_pct']:+.2f}%")

    # ── Futures ──────────────────────────────────────────────────
    lines.append("")
    lines.append("■ 선물 (한국시간 기준)")
    for name in ["S&P500선물", "나스닥선물"]:
        d = market_data.get(name, {})
        if d:
            lines.append(f"  {name}: {d['close']:,.2f} ({d['change_pct']:+.2f}%)")

    # ── Asia ─────────────────────────────────────────────────────
    lines.append("")
    lines.append("■ 아시아 증시")
    for name in ["코스피", "코스닥", "닛케이225", "항셍", "상해종합"]:
        d = market_data.get(name, {})
        if d:
            lines.append(f"  {name}: {d['close']:,.2f} ({d['change_pct']:+.2f}%)")

    # ── Europe ───────────────────────────────────────────────────
    lines.append("")
    lines.append("■ 유럽 증시")
    for name in ["DAX", "FTSE100"]:
        d = market_data.get(name, {})
        if d:
            lines.append(f"  {name}: {d['close']:,.2f} ({d['change_pct']:+.2f}%)")

    # ── VIX + Bonds ──────────────────────────────────────────────
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
    y2 = market_data.get("미국2Y금리", {}).get("close", 0)
    y10 = market_data.get("미국10Y금리", {}).get("close", 0)
    if y2 and y10:
        spread = y10 - y2
        status = "정상" if spread > 0 else "역전 (경기침체 신호)"
        lines.append(f"  10Y-2Y 스프레드: {spread:+.3f}% [{status}]")

    # ── Commodities ──────────────────────────────────────────────
    lines.append("")
    lines.append("■ 원자재 & 에너지")
    for name in ["WTI 원유", "브렌트유", "금", "은", "구리", "천연가스"]:
        d = market_data.get(name, {})
        if d:
            lines.append(f"  {name}: ${d['close']:,.2f} ({d['change_pct']:+.2f}%)")

    # ── FX ───────────────────────────────────────────────────────
    lines.append("")
    lines.append("■ 환율")
    for name in ["USD/KRW", "달러인덱스", "EUR/USD", "USD/JPY"]:
        d = market_data.get(name, {})
        if d:
            lines.append(f"  {name}: {d['close']:,.2f} ({d['change_pct']:+.2f}%)")

    # ── Active Themes with US Backing ────────────────────────────
    if themes:
        lines.append("")
        lines.append("■ 활성 테마 (미국 개별주 기반 탐지)")
        for t in themes[:5]:
            lines.append(f"  [{t['name']}] 관련도: {t['relevance_score']}/10")
            for sig in t["signals"][:3]:
                lines.append(f"    - {sig}")
            leaders = ", ".join(f"{n}({c})" for c, n in t["leader_stocks"])
            lines.append(f"    한국 대장주: {leaders}")
            followers = ", ".join(f"{n}({c})" for c, n in t["follower_stocks"])
            lines.append(f"    한국 수혜주: {followers}")

    # ── Watchlist Candidates ─────────────────────────────────────
    if watchlist:
        lines.append("")
        lines.append("■ 한국 관심종목 후보 (테마 기반)")
        for i, w in enumerate(watchlist[:10], 1):
            lines.append(f"  {i}. {w['name']}({w['code']}) — {w['theme']} [{w['role']}]")
            if w.get("us_drivers"):
                lines.append(f"     미국 동인: {', '.join(w['us_drivers'])}")

    # ── News ──────────────────────────────────────────────────────
    if news:
        us_news = news.get("us_news", [])
        kr_news = news.get("kr_news", [])

        if us_news:
            lines.append("")
            lines.append("■ 주요 미국 시장 뉴스")
            for n in us_news[:8]:
                lines.append(f"  [{n.get('ticker', '')}] {n['title']}")
                if n.get("summary"):
                    lines.append(f"    {n['summary'][:150]}")

        if kr_news:
            lines.append("")
            lines.append("■ 주요 한국 시장 뉴스")
            for n in kr_news[:8]:
                lines.append(f"  [{n.get('source', '')}] {n['title']}")

    lines.append("")
    lines.append(
        "→ 위 데이터와 뉴스를 기반으로 분석해주세요:\n"
        "  1) 미국 시장 주도 종목 분석 (뉴스 참고하여 왜 올랐/내렸는지)\n"
        "  2) 섹터 로테이션 방향\n"
        "  3) 한국 증시 전망 + 코스피 방향\n"
        "  4) 오늘의 한국 관심종목 TOP 5 (종목코드 포함, 매매 근거)\n"
        "  5) 리스크 요인\n"
        "  6) 종합 투자 전략"
    )

    return "\n".join(lines)


async def generate_ai_briefing(fact_sheet: str, api_key: str, model: str = "gpt-4o", base_url: str | None = None) -> dict:
    """Generate AI daily briefing with configurable model (GPT-4o, DeepSeek, etc.)."""
    from openai import AsyncOpenAI

    system_prompt = """당신은 ABLE 플랫폼의 수석 시장 분석가입니다. 한국 개인투자자를 위한 전문 데일리 브리핑을 작성합니다.

핵심 원칙:
1. 논리적 일관성: 미국 시장에서 하락한 섹터의 한국 관련주를 "매수 추천"하지 마세요. 하락 테마는 "리스크/관망"으로 분류하세요.
2. 상승한 테마에서만 관심종목을 추천하세요. "반도체 조정"이면 반도체 대장주를 추천하면 안 됩니다.
3. 구체적 수치를 인용하며 팩트 기반으로 분석합니다. 추측하지 마세요.
4. 미국 종목의 등락 이유(실적, 뉴스, 정책 등)를 추론하여 설명하세요.

응답 형식 (반드시 이 형식을 정확히 따르세요):

1. 오늘의 시장 한줄 요약: (25자 이내, 핵심 포인트)

2. 시장 심리: 탐욕 / 중립 / 공포

3. 코스피 예상 방향: 상승 / 보합 / 하락

4. 미국 시장 분석:
   - 상승 주도주: 어떤 종목이 왜 올랐는지 (이벤트/실적/정책 추론)
   - 하락 주도주: 어떤 종목이 왜 내렸는지
   - 섹터 자금 흐름: 어디서 어디로 로테이션이 일어나고 있는지
   - 한국 증시에 미치는 핵심 영향

5. 핵심 이슈 3~5가지:
   1. (미국 데이터 인용 → 한국 시장 영향 분석)
   2. (미국 데이터 인용 → 한국 시장 영향 분석)
   3. (미국 데이터 인용 → 한국 시장 영향 분석)

6. 오늘의 한국 관심종목 TOP 5:
   - 반드시 미국에서 상승한 테마와 연결된 종목만 추천하세요
   - 미국에서 하락한 테마의 종목은 절대 추천하지 마세요
   형식:
   1. 종목명(종목코드) — 테마명 — 매매 근거 (미국 상승 종목과의 연결 설명)
   2. 종목명(종목코드) — 테마명 — 매매 근거
   3. 종목명(종목코드) — 테마명 — 매매 근거
   4. 종목명(종목코드) — 테마명 — 매매 근거
   5. 종목명(종목코드) — 테마명 — 매매 근거

7. 리스크 요인:
   - 미국에서 하락한 섹터/종목이 한국에 미치는 부정적 영향 포함
   1. (구체적 수치 포함)
   2. (구체적 수치 포함)
   3. (구체적 수치 포함)

8. 종합 투자 전략: (4~6줄, 구체적이고 실전적으로. 상승 테마 활용 + 하락 테마 회피 전략 포함)

중요: 팩트시트에 제공된 종목코드를 반드시 사용하세요. 추측 금지.
한국어로 답변하세요. 간결하되 구체적으로."""

    try:
        client_kwargs: dict = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = AsyncOpenAI(**client_kwargs)

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": fact_sheet},
            ],
            temperature=0.3,
            max_tokens=3000,
        )

        ai_text = response.choices[0].message.content or ""
        usage = response.usage

        parsed = _parse_briefing(ai_text)
        parsed["raw_text"] = ai_text
        parsed["model"] = model
        parsed["tokens_used"] = {
            "prompt": usage.prompt_tokens if usage else 0,
            "completion": usage.completion_tokens if usage else 0,
            "total": usage.total_tokens if usage else 0,
        }

        logger.info("Daily briefing generated with %s (tokens: %s)", model, parsed["tokens_used"]["total"])
        return parsed

    except Exception as e:
        logger.error("AI briefing failed (model=%s): %s", model, e)
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
        "us_market_analysis": "",
        "key_issues": [],
        "watchlist": [],
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

        # US market analysis
        if "미국 시장 분석" in line_stripped or "미국시장분석" in line_stripped:
            current_section = "us_analysis"
            continue

        # Key issues
        if "핵심 이슈" in line_stripped or "핵심이슈" in line_stripped:
            current_section = "issues"
            continue

        # Watchlist
        if "관심종목" in line_stripped and ("TOP" in line_stripped or "top" in line_stripped or "5" in line_stripped):
            current_section = "watchlist"
            continue

        # Risks
        if "리스크" in line_stripped:
            current_section = "risks"
            continue

        # Strategy
        if "투자 전략" in line_stripped or "투자전략" in line_stripped or "종합 투자" in line_stripped:
            current_section = "strategy"
            continue

        # Collect content by section
        if current_section == "us_analysis":
            if line_stripped.startswith("-") or line_stripped.startswith("·"):
                result["us_market_analysis"] += line_stripped.lstrip("-·").strip() + "\n"
            elif not any(kw in line_stripped for kw in ["핵심", "관심종목", "리스크", "투자 전략"]):
                result["us_market_analysis"] += line_stripped + "\n"

        elif current_section == "issues" and (line_stripped.startswith("-") or line_stripped[0:1].isdigit()):
            result["key_issues"].append(line_stripped.lstrip("-").lstrip("0123456789.").strip())

        elif current_section == "watchlist" and (line_stripped.startswith("-") or line_stripped[0:1].isdigit()):
            entry = line_stripped.lstrip("-").lstrip("0123456789.").strip()
            result["watchlist"].append(entry)

        elif current_section == "risks" and (line_stripped.startswith("-") or line_stripped[0:1].isdigit()):
            result["risks"].append(line_stripped.lstrip("-").lstrip("0123456789.").strip())

        elif current_section == "strategy":
            result["strategy"] += line_stripped + " "

    result["strategy"] = result["strategy"].strip()
    result["us_market_analysis"] = result["us_market_analysis"].strip()

    # Fallback headline
    if not result["headline"]:
        for l in lines:
            if l.strip() and len(l.strip()) > 5:
                result["headline"] = l.strip()[:50]
                break

    return result


async def generate_daily_report(force: bool = False) -> dict:
    """Main entry point: fetch data → analyze → AI briefing → save to DB.

    Args:
        force: If True, delete existing report for today and regenerate.
    """
    from app.config import get_settings
    from app.db.session import async_session_factory
    from app.models.daily_report import DailyMarketReport
    from sqlalchemy import select, delete
    import asyncio

    settings = get_settings()
    today = date.today()

    logger.info("Starting daily market intelligence for %s (force=%s)", today, force)

    # Check / handle existing report
    async with async_session_factory() as db:
        existing = await db.execute(
            select(DailyMarketReport).where(
                DailyMarketReport.report_date == today,
                DailyMarketReport.report_type == "morning",
            )
        )
        existing_report = existing.scalar_one_or_none()
        if existing_report:
            if not force:
                logger.info("Morning report already exists for %s, skipping", today)
                return {"status": "already_exists", "date": str(today)}
            await db.execute(
                delete(DailyMarketReport).where(
                    DailyMarketReport.report_date == today,
                    DailyMarketReport.report_type == "morning",
                )
            )
            await db.commit()
            logger.info("Deleted existing morning report for %s (force regeneration)", today)

    # Step 1: Fetch global market data
    market_data = await asyncio.to_thread(fetch_global_market_data)
    logger.info("Fetched %d global market data points", len(market_data))

    # Step 2: Fetch US individual stocks + sector ETFs
    us_data = await asyncio.to_thread(fetch_us_stock_data)
    us_stock_count = len(us_data.get("stocks", {}))
    us_sector_count = len(us_data.get("sectors", {}))
    logger.info("Fetched %d US stocks + %d sector ETFs", us_stock_count, us_sector_count)

    # Step 3: Detect active themes (using US stock data)
    themes = detect_active_themes(market_data, us_data)
    logger.info("Detected %d active themes", len(themes))

    # Step 4: Generate watchlist candidates
    watchlist = generate_watchlist(themes, market_data)
    logger.info("Generated %d watchlist candidates", len(watchlist))

    # Step 5: Fetch market news
    news = await asyncio.to_thread(fetch_market_news)
    us_news_count = len(news.get("us_news", []))
    kr_news_count = len(news.get("kr_news", []))
    logger.info("Fetched %d US news + %d KR news", us_news_count, kr_news_count)

    # Step 6: Build comprehensive fact sheet for AI
    fact_sheet = build_market_fact_sheet(market_data, us_data, themes, watchlist, news)

    # Step 7: Generate AI briefing (configurable model)
    model = settings.daily_report_model or "gpt-4o"
    ai_summary = {}
    ai_raw_text = ""

    # Determine API key and base_url based on model
    if model.startswith("deepseek"):
        api_key = settings.deepseek_api_key
        base_url: str | None = "https://api.deepseek.com"
    else:
        # GPT-4o or other OpenAI models
        api_key = settings.openai_api_key
        base_url = None

    if api_key:
        ai_summary = await generate_ai_briefing(fact_sheet, api_key, model=model, base_url=base_url)
        ai_raw_text = ai_summary.pop("raw_text", "")
    else:
        ai_summary = {
            "headline": "AI 키 미설정 — 시장 데이터만 제공",
            "market_sentiment": "중립",
            "kospi_direction": "보합",
        }
        logger.warning("No AI API key configured for model=%s, skipping briefing", model)

    # Merge programmatic watchlist into ai_summary if AI didn't provide one
    if not ai_summary.get("watchlist") and watchlist:
        ai_summary["watchlist_data"] = watchlist

    # Step 8: Save to DB
    async with async_session_factory() as db:
        serialized_themes = []
        for t in themes:
            serialized_themes.append({
                "name": t["name"],
                "relevance_score": t["relevance_score"],
                "signals": t["signals"],
                "us_movers": t.get("us_movers", []),
                "leader_stocks": [{"code": c, "name": n} for c, n in t["leader_stocks"]],
                "follower_stocks": [{"code": c, "name": n} for c, n in t["follower_stocks"]],
            })

        report = DailyMarketReport(
            report_date=today,
            report_type="morning",
            status="completed",
            market_data={
                **market_data,
                "us_stocks": {
                    t: {k: v for k, v in s.items() if k != "themes"}
                    for t, s in us_data.get("stocks", {}).items()
                },
                "us_sectors": {
                    t: {k: v for k, v in s.items() if k != "themes"}
                    for t, s in us_data.get("sectors", {}).items()
                },
                "us_rankings": us_data.get("rankings", {}),
            },
            themes=serialized_themes,
            ai_summary={
                **ai_summary,
                "watchlist_data": watchlist,
                "news": news,
            },
            ai_raw_text=ai_raw_text,
        )
        db.add(report)
        await db.commit()
        logger.info("Morning market report saved for %s", today)

    return {
        "status": "completed",
        "date": str(today),
        "market_data_count": len(market_data),
        "us_stocks_count": us_stock_count,
        "us_sectors_count": us_sector_count,
        "active_themes": len(themes),
        "watchlist_count": len(watchlist),
        "ai_headline": ai_summary.get("headline", ""),
    }


# ─── Closing Report (장마감 리포트) ─────────────────────────────────────


def build_closing_fact_sheet(
    kr_data: dict,
    market_data: dict,
    news: dict | None = None,
) -> str:
    """Build fact sheet for the closing (장마감) report."""
    lines = []
    now = datetime.now()
    dow_kr = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}

    lines.append("[장마감 시장 정리 리포트]")
    lines.append(f"기준일: {now.strftime('%Y-%m-%d')} ({dow_kr.get(now.weekday(), '')}요일)")
    lines.append("")

    # KOSPI / KOSDAQ
    lines.append("■ 국내 증시 마감")
    for name in ["코스피", "코스닥"]:
        d = market_data.get(name, {})
        if d:
            lines.append(f"  {name}: {d['close']:,.2f} ({d['change_pct']:+.2f}%)")

    # Korean Stock Rankings
    rankings = kr_data.get("rankings", {})
    gainers = rankings.get("gainers", [])
    losers = rankings.get("losers", [])

    if gainers:
        lines.append("")
        lines.append("■ 오늘의 상승 주도주 (국내)")
        for i, g in enumerate(gainers[:10], 1):
            lines.append(
                f"  {i}. {g['name']}({g['code']}) "
                f"₩{g['close']:,.0f} ({g['change_pct']:+.2f}%) "
                f"테마: {g.get('theme', '')}"
            )

    if losers:
        lines.append("")
        lines.append("■ 오늘의 하락 주도주 (국내)")
        for i, l in enumerate(losers[:10], 1):
            lines.append(
                f"  {i}. {l['name']}({l['code']}) "
                f"₩{l['close']:,.0f} ({l['change_pct']:+.2f}%) "
                f"테마: {l.get('theme', '')}"
            )

    # Volume leaders
    all_stocks = list(kr_data.get("stocks", {}).values())
    all_stocks.sort(key=lambda x: x.get("volume", 0), reverse=True)
    if all_stocks:
        lines.append("")
        lines.append("■ 거래량 상위 종목")
        for s in all_stocks[:5]:
            lines.append(f"  {s['name']}({s['code']}) 거래량: {s['volume']:,} ({s['change_pct']:+.2f}%)")

    # Global context
    lines.append("")
    lines.append("■ 글로벌 참고 지표")
    for name in ["S&P 500", "나스닥", "VIX", "USD/KRW", "WTI 원유"]:
        d = market_data.get(name, {})
        if d and isinstance(d, dict) and "close" in d:
            lines.append(f"  {name}: {d['close']:,.2f} ({d['change_pct']:+.2f}%)")

    # News
    if news:
        kr_news = news.get("kr_news", [])
        if kr_news:
            lines.append("")
            lines.append("■ 오늘의 주요 뉴스")
            for n in kr_news[:10]:
                lines.append(f"  [{n.get('source', '')}] {n['title']}")

    lines.append("")
    lines.append(
        "→ 위 데이터와 뉴스를 기반으로 장마감 정리를 작성해주세요:\n"
        "  1) 오늘 국내 증시 한줄 요약\n"
        "  2) 상승 주도 테마 분석 (어떤 테마가 왜 강했는지, 뉴스 연결)\n"
        "  3) 하락 주도 테마 분석 (어떤 테마가 왜 약했는지)\n"
        "  4) 주목할 특이 종목 (거래량 급증, 이상 급등/급락)\n"
        "  5) 내일 전망 (글로벌 흐름 참고)\n"
        "  6) 투자자 액션 플랜"
    )

    return "\n".join(lines)


async def generate_closing_ai_briefing(fact_sheet: str, api_key: str, model: str = "gpt-4o", base_url: str | None = None) -> dict:
    """Generate closing report AI analysis."""
    from openai import AsyncOpenAI

    system_prompt = """당신은 ABLE 플랫폼의 장마감 분석가입니다. 한국 증시 마감 후 하루를 정리하는 전문 리포트를 작성합니다.

핵심 원칙:
1. 오늘 실제로 일어난 일만 분석합니다 (추측 금지)
2. 상승/하락 주도 종목의 이유를 뉴스와 연결하여 설명합니다
3. 거래량이 급증한 종목은 반드시 언급합니다
4. 내일 주목할 포인트를 구체적으로 제시합니다

응답 형식 (반드시 준수):

1. 오늘의 시장 한줄 요약: (25자 이내)

2. 시장 심리: 탐욕 / 중립 / 공포

3. 오늘의 시장 분석:
   - 상승 주도 테마 + 핵심 종목 (왜 올랐는지 뉴스/이벤트 연결)
   - 하락 주도 테마 + 핵심 종목 (왜 내렸는지)
   - 섹터 자금 흐름

4. 핵심 이슈 3~5가지:
   1. (실제 종목명 + 등락률 + 이유)
   2. (실제 종목명 + 등락률 + 이유)
   3. (실제 종목명 + 등락률 + 이유)

5. 주목 종목 (특이 움직임):
   1. 종목명(종목코드) — 등락률 — 이유 (거래량 급증, 뉴스 등)
   2. 종목명(종목코드) — 등락률 — 이유
   3. 종목명(종목코드) — 등락률 — 이유

6. 리스크 요인:
   1. (구체적 수치)
   2. (구체적 수치)

7. 내일 전망 + 투자 전략: (4~6줄)

한국어로 답변하세요. 간결하되 구체적으로."""

    try:
        client_kwargs: dict = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = AsyncOpenAI(**client_kwargs)

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": fact_sheet},
            ],
            temperature=0.3,
            max_tokens=3000,
        )

        ai_text = response.choices[0].message.content or ""
        parsed = _parse_briefing(ai_text)
        parsed["raw_text"] = ai_text
        parsed["model"] = model

        usage = response.usage
        parsed["tokens_used"] = {
            "prompt": usage.prompt_tokens if usage else 0,
            "completion": usage.completion_tokens if usage else 0,
            "total": usage.total_tokens if usage else 0,
        }

        logger.info("Closing briefing generated with %s (tokens: %s)", model, parsed["tokens_used"]["total"])
        return parsed

    except Exception as e:
        logger.error("Closing AI briefing failed (model=%s): %s", model, e)
        return {
            "error": str(e),
            "headline": "장마감 AI 브리핑 생성 실패",
            "market_sentiment": "중립",
            "raw_text": "",
        }


async def generate_closing_report(force: bool = False) -> dict:
    """Generate closing (장마감) report after Korean market close.

    Pipeline:
      1. Fetch Korean bellwether stock data
      2. Fetch global market data (for context)
      3. Fetch Korean news
      4. Build closing fact sheet → AI analysis
      5. Save to DB
    """
    from app.config import get_settings
    from app.db.session import async_session_factory
    from app.models.daily_report import DailyMarketReport
    from sqlalchemy import select, delete
    import asyncio

    settings = get_settings()
    today = date.today()

    logger.info("Starting closing report for %s (force=%s)", today, force)

    # KOSPI trading day check (skip weekends + Korean holidays)
    if not force and not is_kospi_trading_day(today):
        logger.info("Skipping closing report — %s is not a KOSPI trading day", today)
        return {"status": "skipped", "date": str(today), "reason": "not_trading_day"}

    # Check existing
    async with async_session_factory() as db:
        existing = await db.execute(
            select(DailyMarketReport).where(
                DailyMarketReport.report_date == today,
                DailyMarketReport.report_type == "closing",
            )
        )
        existing_report = existing.scalar_one_or_none()
        if existing_report:
            if not force:
                return {"status": "already_exists", "date": str(today), "type": "closing"}
            await db.execute(
                delete(DailyMarketReport).where(
                    DailyMarketReport.report_date == today,
                    DailyMarketReport.report_type == "closing",
                )
            )
            await db.commit()
            logger.info("Deleted existing closing report for %s", today)

    # Step 1: Fetch Korean market data
    kr_data = await asyncio.to_thread(fetch_kr_market_data)
    logger.info("Fetched %d Korean stocks", len(kr_data.get("stocks", {})))

    # Step 2: Fetch global market data (for context)
    market_data = await asyncio.to_thread(fetch_global_market_data)

    # Step 3: Fetch Korean news
    news = await asyncio.to_thread(fetch_market_news)
    logger.info("Fetched %d KR news items", len(news.get("kr_news", [])))

    # Step 4: Build fact sheet
    fact_sheet = build_closing_fact_sheet(kr_data, market_data, news)

    # Step 5: AI analysis
    model = settings.daily_report_model or "gpt-4o"
    ai_summary = {}
    ai_raw_text = ""

    if model.startswith("deepseek"):
        api_key = settings.deepseek_api_key
        base_url: str | None = "https://api.deepseek.com"
    else:
        api_key = settings.openai_api_key
        base_url = None

    if api_key:
        ai_summary = await generate_closing_ai_briefing(fact_sheet, api_key, model=model, base_url=base_url)
        ai_raw_text = ai_summary.pop("raw_text", "")

    # Step 6: Save to DB
    async with async_session_factory() as db:
        kr_rankings = kr_data.get("rankings", {})

        report = DailyMarketReport(
            report_date=today,
            report_type="closing",
            status="completed",
            market_data={
                "kr_stocks": kr_data.get("stocks", {}),
                "kr_rankings": kr_rankings,
                **{k: v for k, v in market_data.items()
                   if k in ["코스피", "코스닥", "S&P 500", "나스닥", "VIX", "USD/KRW"]},
            },
            themes=[],  # Closing report doesn't use theme system
            ai_summary={
                **ai_summary,
                "news": news,
            },
            ai_raw_text=ai_raw_text,
        )
        db.add(report)
        await db.commit()
        logger.info("Closing report saved for %s", today)

    return {
        "status": "completed",
        "date": str(today),
        "type": "closing",
        "kr_stocks_count": len(kr_data.get("stocks", {})),
        "kr_gainers": len(kr_rankings.get("gainers", [])),
        "kr_losers": len(kr_rankings.get("losers", [])),
        "ai_headline": ai_summary.get("headline", ""),
    }
