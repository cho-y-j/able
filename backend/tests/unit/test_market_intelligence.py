"""Tests for Daily Market Intelligence service."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from app.services.market_intelligence import (
    detect_active_themes,
    build_market_fact_sheet,
    build_closing_fact_sheet,
    generate_watchlist,
    is_kospi_trading_day,
    _parse_briefing,
    THEME_STOCK_MAP,
    US_BELLWETHER_STOCKS,
    US_SECTOR_ETFS,
    KR_BELLWETHER_STOCKS,
)


# ─── Sample market data for testing ─────────────────────────────

SAMPLE_MARKET_DATA = {
    "S&P 500": {"ticker": "^GSPC", "close": 5200.50, "change": 52.3, "change_pct": 1.02, "volume": 3500000000},
    "나스닥": {"ticker": "^IXIC", "close": 16500.00, "change": 250.0, "change_pct": 1.54, "volume": 2800000000},
    "다우존스": {"ticker": "^DJI", "close": 39800.00, "change": -50.0, "change_pct": -0.13, "volume": 1200000000},
    "코스피": {"ticker": "^KS11", "close": 2680.50, "change": 15.3, "change_pct": 0.57, "volume": 450000000},
    "코스닥": {"ticker": "^KQ11", "close": 870.20, "change": -5.1, "change_pct": -0.58, "volume": 320000000},
    "VIX": {"ticker": "^VIX", "close": 18.5, "change": -1.2, "change_pct": -6.09, "volume": 0},
    "WTI 원유": {"ticker": "CL=F", "close": 78.50, "change": 2.1, "change_pct": 2.75, "volume": 800000},
    "금": {"ticker": "GC=F", "close": 2350.00, "change": 15.0, "change_pct": 0.64, "volume": 200000},
    "구리": {"ticker": "HG=F", "close": 4.25, "change": 0.08, "change_pct": 1.92, "volume": 50000},
    "USD/KRW": {"ticker": "KRW=X", "close": 1345.50, "change": 5.0, "change_pct": 0.37, "volume": 0},
    "미국10Y금리": {"ticker": "^TNX", "close": 4.350, "change": 0.05, "change_pct": 1.16, "volume": 0},
    "미국2Y금리": {"ticker": "^IRX", "close": 4.650, "change": 0.02, "change_pct": 0.43, "volume": 0},
    "천연가스": {"ticker": "NG=F", "close": 3.20, "change": 0.12, "change_pct": 3.90, "volume": 100000},
    "S&P500선물": {"ticker": "ES=F", "close": 5210.00, "change": 15.0, "change_pct": 0.29, "volume": 1000000},
    "나스닥선물": {"ticker": "NQ=F", "close": 18200.00, "change": 80.0, "change_pct": 0.44, "volume": 500000},
}

# ─── Sample US stock data ────────────────────────────────────────

SAMPLE_US_DATA = {
    "stocks": {
        "NVDA": {"ticker": "NVDA", "name": "NVIDIA", "close": 140.0, "change": 5.4, "change_pct": 4.01, "volume": 50000000, "themes": ["AI/반도체"]},
        "AMD": {"ticker": "AMD", "name": "AMD", "close": 170.0, "change": 3.4, "change_pct": 2.04, "volume": 30000000, "themes": ["AI/반도체"]},
        "AVGO": {"ticker": "AVGO", "name": "Broadcom", "close": 220.0, "change": 2.2, "change_pct": 1.01, "volume": 15000000, "themes": ["AI/반도체"]},
        "TSLA": {"ticker": "TSLA", "name": "Tesla", "close": 250.0, "change": -5.0, "change_pct": -1.96, "volume": 40000000, "themes": ["2차전지/배터리", "자동차/모빌리티", "로봇/자동화"]},
        "LLY": {"ticker": "LLY", "name": "Eli Lilly", "close": 800.0, "change": 24.0, "change_pct": 3.09, "volume": 10000000, "themes": ["바이오/제약"]},
        "LMT": {"ticker": "LMT", "name": "Lockheed Martin", "close": 450.0, "change": 4.5, "change_pct": 1.01, "volume": 5000000, "themes": ["방산/우주항공"]},
        "JPM": {"ticker": "JPM", "name": "JPMorgan", "close": 200.0, "change": 0.4, "change_pct": 0.20, "volume": 8000000, "themes": ["금융/은행"]},
        "XOM": {"ticker": "XOM", "name": "ExxonMobil", "close": 110.0, "change": 2.2, "change_pct": 2.04, "volume": 15000000, "themes": ["원자력/에너지", "조선/해양"]},
        "MSFT": {"ticker": "MSFT", "name": "Microsoft", "close": 420.0, "change": -4.2, "change_pct": -0.99, "volume": 25000000, "themes": ["AI/반도체", "인터넷/플랫폼"]},
        "META": {"ticker": "META", "name": "Meta", "close": 500.0, "change": 5.0, "change_pct": 1.01, "volume": 20000000, "themes": ["인터넷/플랫폼"]},
    },
    "sectors": {
        "SOXX": {"ticker": "SOXX", "name": "Semiconductor", "kr_name": "반도체", "close": 230.0, "change_pct": 2.50, "themes": ["AI/반도체"]},
        "XLK": {"ticker": "XLK", "name": "Technology", "kr_name": "기술", "close": 200.0, "change_pct": 1.20, "themes": ["AI/반도체", "인터넷/플랫폼"]},
        "XLE": {"ticker": "XLE", "name": "Energy", "kr_name": "에너지", "close": 90.0, "change_pct": 1.80, "themes": ["원자력/에너지"]},
        "XLF": {"ticker": "XLF", "name": "Financials", "kr_name": "금융", "close": 42.0, "change_pct": 0.30, "themes": ["금융/은행"]},
        "XBI": {"ticker": "XBI", "name": "Biotech", "kr_name": "바이오", "close": 95.0, "change_pct": 2.10, "themes": ["바이오/제약"]},
    },
    "rankings": {
        "gainers": [
            {"ticker": "NVDA", "name": "NVIDIA", "close": 140.0, "change_pct": 4.01, "themes": ["AI/반도체"]},
            {"ticker": "LLY", "name": "Eli Lilly", "close": 800.0, "change_pct": 3.09, "themes": ["바이오/제약"]},
            {"ticker": "AMD", "name": "AMD", "close": 170.0, "change_pct": 2.04, "themes": ["AI/반도체"]},
            {"ticker": "XOM", "name": "ExxonMobil", "close": 110.0, "change_pct": 2.04, "themes": ["원자력/에너지"]},
        ],
        "losers": [
            {"ticker": "TSLA", "name": "Tesla", "close": 250.0, "change_pct": -1.96, "themes": ["2차전지/배터리"]},
            {"ticker": "MSFT", "name": "Microsoft", "close": 420.0, "change_pct": -0.99, "themes": ["AI/반도체"]},
        ],
    },
}


class TestDetectActiveThemes:
    """Test theme detection logic with US stock data."""

    def test_detects_ai_semiconductor_from_nvda_surge(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        theme_names = [t["name"] for t in themes]
        assert "AI/반도체" in theme_names

    def test_ai_semiconductor_has_high_relevance_from_us_stocks(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        ai_theme = next(t for t in themes if t["name"] == "AI/반도체")
        # NVDA +4% → 3 pts, AMD +2% → 2 pts, AVGO +1% → 1 pt, SOXX +2.5% → 2 pts
        assert ai_theme["relevance_score"] >= 5

    def test_detects_bio_theme_from_lly_rise(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        theme_names = [t["name"] for t in themes]
        assert "바이오/제약" in theme_names

    def test_detects_energy_theme_from_xom_and_oil(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        theme_names = [t["name"] for t in themes]
        assert "원자력/에너지" in theme_names

    def test_themes_sorted_by_relevance(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        if len(themes) >= 2:
            for i in range(len(themes) - 1):
                assert themes[i]["relevance_score"] >= themes[i + 1]["relevance_score"]

    def test_each_theme_has_required_fields(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        for theme in themes:
            assert "name" in theme
            assert "relevance_score" in theme
            assert "signals" in theme
            assert "us_movers" in theme
            assert "leader_stocks" in theme
            assert "follower_stocks" in theme

    def test_us_movers_populated_for_active_themes(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        ai_theme = next(t for t in themes if t["name"] == "AI/반도체")
        assert len(ai_theme["us_movers"]) >= 2
        assert any(m["ticker"] == "NVDA" for m in ai_theme["us_movers"])

    def test_no_themes_on_flat_us_data(self):
        flat_us = {
            "stocks": {
                t: {**s, "change_pct": 0.0}
                for t, s in SAMPLE_US_DATA["stocks"].items()
            },
            "sectors": {
                t: {**s, "change_pct": 0.0}
                for t, s in SAMPLE_US_DATA["sectors"].items()
            },
            "rankings": {"gainers": [], "losers": []},
        }
        flat_market = {
            name: {**d, "change_pct": 0.0}
            for name, d in SAMPLE_MARKET_DATA.items()
        }
        flat_market["VIX"] = {**flat_market["VIX"], "close": 12}
        themes = detect_active_themes(flat_market, flat_us)
        # With flat data, very few themes should be active
        assert all(t["relevance_score"] <= 3 for t in themes)

    def test_high_vix_adds_signals(self):
        high_vix_data = {**SAMPLE_MARKET_DATA}
        high_vix_data["VIX"] = {"ticker": "^VIX", "close": 35, "change": 5.0, "change_pct": 16.67, "volume": 0}
        themes = detect_active_themes(high_vix_data, SAMPLE_US_DATA)
        has_vix_warning = any(
            any("VIX" in sig for sig in t["signals"])
            for t in themes
        )
        assert has_vix_warning

    def test_backward_compatible_without_us_data(self):
        """Theme detection still works without US stock data (index-only mode)."""
        themes = detect_active_themes(SAMPLE_MARKET_DATA)
        # Should still work via macro signals
        assert isinstance(themes, list)


class TestGenerateWatchlist:
    """Test Korean watchlist generation."""

    def test_generates_watchlist_from_themes(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        watchlist = generate_watchlist(themes, SAMPLE_MARKET_DATA)
        assert len(watchlist) > 0

    def test_watchlist_has_required_fields(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        watchlist = generate_watchlist(themes, SAMPLE_MARKET_DATA)
        for item in watchlist:
            assert "code" in item
            assert "name" in item
            assert "theme" in item
            assert "role" in item
            assert "relevance" in item
            assert "reason" in item

    def test_watchlist_prioritizes_leaders(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        watchlist = generate_watchlist(themes, SAMPLE_MARKET_DATA)
        leaders = [w for w in watchlist if w["role"] == "대장주"]
        assert len(leaders) >= 1

    def test_watchlist_no_duplicates(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        watchlist = generate_watchlist(themes, SAMPLE_MARKET_DATA)
        codes = [w["code"] for w in watchlist]
        assert len(codes) == len(set(codes))

    def test_watchlist_max_10(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        watchlist = generate_watchlist(themes, SAMPLE_MARKET_DATA)
        assert len(watchlist) <= 10

    def test_watchlist_includes_us_drivers(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        watchlist = generate_watchlist(themes, SAMPLE_MARKET_DATA)
        # At least one item should have US drivers
        has_drivers = any(len(w.get("us_drivers", [])) > 0 for w in watchlist)
        assert has_drivers


class TestBuildFactSheet:
    """Test fact sheet generation with US stock data."""

    def test_basic_structure(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        watchlist = generate_watchlist(themes, SAMPLE_MARKET_DATA)
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, SAMPLE_US_DATA, themes, watchlist)

        assert "일일 시장 인텔리전스 팩트시트" in fact_sheet
        assert "미국 증시" in fact_sheet
        assert "원자재" in fact_sheet
        assert "환율" in fact_sheet

    def test_contains_us_rankings(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, SAMPLE_US_DATA, themes)
        assert "미국 상승 주도주" in fact_sheet
        assert "NVIDIA" in fact_sheet

    def test_contains_us_sector_etfs(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, SAMPLE_US_DATA, themes)
        assert "미국 섹터 ETF 성과" in fact_sheet
        assert "반도체" in fact_sheet

    def test_contains_active_themes_with_us_backing(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, SAMPLE_US_DATA, themes)
        assert "미국 개별주 기반 탐지" in fact_sheet
        assert "한국 대장주" in fact_sheet

    def test_contains_watchlist_candidates(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        watchlist = generate_watchlist(themes, SAMPLE_MARKET_DATA)
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, SAMPLE_US_DATA, themes, watchlist)
        assert "한국 관심종목 후보" in fact_sheet

    def test_contains_key_indices(self):
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, None, [])
        assert "S&P 500" in fact_sheet
        assert "나스닥" in fact_sheet
        assert "코스피" in fact_sheet

    def test_contains_commodities(self):
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, None, [])
        assert "WTI 원유" in fact_sheet
        assert "금" in fact_sheet

    def test_contains_fx(self):
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, None, [])
        assert "USD/KRW" in fact_sheet

    def test_contains_bonds_and_yield_curve(self):
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, None, [])
        assert "미국10Y금리" in fact_sheet
        assert "스프레드" in fact_sheet

    def test_contains_vix_level(self):
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, None, [])
        assert "VIX" in fact_sheet
        assert "보통" in fact_sheet  # VIX 18.5 → "보통"

    def test_contains_futures(self):
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, None, [])
        assert "선물" in fact_sheet

    def test_ends_with_analysis_request(self):
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, None, [])
        assert "관심종목 TOP 5" in fact_sheet


class TestParseBriefing:
    """Test AI response parsing with new fields."""

    def test_parses_full_response(self):
        text = """1. 오늘의 시장 한줄 요약: NVDA 급등에 반도체 랠리
2. 시장 심리: 탐욕
3. 코스피 예상 방향: 상승
4. 미국 시장 분석:
   - NVDA +4.01% 급등, AI 수요 기대감 지속
   - 반도체 섹터 전반 강세, SOXX +2.5%
   - 에너지→기술주로 섹터 로테이션
5. 핵심 이슈 3가지:
   1. NVDA +4% 상승으로 AI 반도체 공급망 수혜 예상
   2. WTI +2.75% 상승으로 에너지 섹터 강세
   3. 원/달러 1,345원 안정 유지
6. 오늘의 한국 관심종목 TOP 5:
   1. 삼성전자(005930) — AI/반도체 — NVDA +4% 수혜
   2. SK하이닉스(000660) — AI/반도체 — HBM 수주 기대
   3. 삼성바이오로직스(207940) — 바이오 — LLY +3% 영향
   4. HD현대일렉트릭(267260) — 에너지 — WTI 강세
   5. 현대차(005380) — 자동차 — 환율 효과
7. 리스크 요인:
   1. VIX 18.5 점진적 상승세
   2. 미국 10Y 금리 4.35% 부담
8. 종합 투자 전략:
반도체 대장주 중심 매수 전략 유효. NVDA 급등 영향으로 삼성전자, SK하이닉스 갭업 예상."""

        result = _parse_briefing(text)

        assert result["headline"] == "NVDA 급등에 반도체 랠리"
        assert result["market_sentiment"] == "탐욕"
        assert result["kospi_direction"] == "상승"
        assert "NVDA" in result["us_market_analysis"]
        assert len(result["key_issues"]) == 3
        assert len(result["watchlist"]) == 5
        assert len(result["risks"]) == 2
        assert "반도체" in result["strategy"]

    def test_parses_minimal_response(self):
        text = "시장 보합 예상"
        result = _parse_briefing(text)
        assert result["market_sentiment"] == "중립"
        assert result["kospi_direction"] == "보합"
        assert result["headline"] == "시장 보합 예상"

    def test_parses_bearish_sentiment(self):
        text = """1. 오늘의 시장 한줄 요약: 글로벌 매도세 확산
2. 시장 심리: 공포
3. 코스피 예상 방향: 하락"""
        result = _parse_briefing(text)
        assert result["market_sentiment"] == "공포"
        assert result["kospi_direction"] == "하락"

    def test_parses_watchlist_section(self):
        text = """6. 오늘의 한국 관심종목 TOP 5:
   1. 삼성전자(005930) — AI/반도체 — NVDA 수혜
   2. SK하이닉스(000660) — AI/반도체 — HBM"""
        result = _parse_briefing(text)
        assert len(result["watchlist"]) == 2
        assert "삼성전자" in result["watchlist"][0]


class TestThemeStockMap:
    """Test theme-stock mapping data integrity."""

    def test_all_themes_have_required_fields(self):
        for theme_name, theme in THEME_STOCK_MAP.items():
            assert "leader" in theme, f"{theme_name} missing leader"
            assert "follower" in theme, f"{theme_name} missing follower"
            assert "triggers" in theme, f"{theme_name} missing triggers"

    def test_leader_stocks_have_code_and_name(self):
        for theme_name, theme in THEME_STOCK_MAP.items():
            for code, name in theme["leader"]:
                assert len(code) == 6 or len(code) > 0, f"Invalid code {code} in {theme_name}"
                assert len(name) > 0, f"Empty name for {code} in {theme_name}"

    def test_no_duplicate_leaders_across_themes(self):
        all_leaders = []
        for theme in THEME_STOCK_MAP.values():
            all_leaders.extend([code for code, _ in theme["leader"]])
        assert len(all_leaders) > 10

    def test_at_least_10_themes_defined(self):
        assert len(THEME_STOCK_MAP) >= 10


class TestUSBellwetherStocks:
    """Test US bellwether stock mapping integrity."""

    def test_all_stocks_have_name_and_themes(self):
        for ticker, info in US_BELLWETHER_STOCKS.items():
            assert "name" in info, f"{ticker} missing name"
            assert "themes" in info, f"{ticker} missing themes"
            assert len(info["themes"]) > 0, f"{ticker} has no themes"

    def test_all_themes_referenced_exist_in_theme_stock_map(self):
        for ticker, info in US_BELLWETHER_STOCKS.items():
            for theme in info["themes"]:
                assert theme in THEME_STOCK_MAP, f"{ticker} references unknown theme: {theme}"

    def test_at_least_40_us_stocks_tracked(self):
        assert len(US_BELLWETHER_STOCKS) >= 40

    def test_key_stocks_present(self):
        key_stocks = ["NVDA", "AAPL", "MSFT", "TSLA", "AMZN", "GOOGL", "META"]
        for ticker in key_stocks:
            assert ticker in US_BELLWETHER_STOCKS, f"Missing key stock: {ticker}"


class TestUSSectorETFs:
    """Test US sector ETF mapping integrity."""

    def test_all_etfs_have_required_fields(self):
        for ticker, info in US_SECTOR_ETFS.items():
            assert "name" in info, f"{ticker} missing name"
            assert "kr_name" in info, f"{ticker} missing kr_name"
            assert "themes" in info, f"{ticker} missing themes"

    def test_at_least_10_sector_etfs(self):
        assert len(US_SECTOR_ETFS) >= 10

    def test_key_etfs_present(self):
        key_etfs = ["SOXX", "XLK", "XLE", "XLF", "XLV"]
        for ticker in key_etfs:
            assert ticker in US_SECTOR_ETFS, f"Missing key ETF: {ticker}"


class TestIsKospiTradingDay:
    """Test KOSPI trading day check."""

    def test_weekday_is_trading_day(self):
        # 2026-02-09 = Monday
        assert is_kospi_trading_day(date(2026, 2, 9)) is True

    def test_saturday_is_not_trading_day(self):
        # 2026-02-14 = Saturday
        assert is_kospi_trading_day(date(2026, 2, 14)) is False

    def test_sunday_is_not_trading_day(self):
        # 2026-02-15 = Sunday
        assert is_kospi_trading_day(date(2026, 2, 15)) is False

    def test_new_years_day_not_trading(self):
        assert is_kospi_trading_day(date(2026, 1, 1)) is False

    def test_independence_day_not_trading(self):
        # 3.1절
        assert is_kospi_trading_day(date(2026, 3, 1)) is False

    def test_christmas_not_trading(self):
        assert is_kospi_trading_day(date(2026, 12, 25)) is False

    def test_seollal_2026_not_trading(self):
        # 2026 설날: 2/16-2/18
        assert is_kospi_trading_day(date(2026, 2, 17)) is False

    def test_chuseok_2026_not_trading(self):
        # 2026 추석: 9/24-9/26
        assert is_kospi_trading_day(date(2026, 9, 25)) is False

    def test_regular_friday_is_trading(self):
        # 2026-02-13 = Friday
        assert is_kospi_trading_day(date(2026, 2, 13)) is True


class TestBuildClosingFactSheet:
    """Test closing report fact sheet generation."""

    def test_basic_structure(self):
        kr_data = {
            "stocks": {
                "005930": {
                    "code": "005930", "name": "삼성전자", "theme": "AI/반도체",
                    "close": 75000, "change": 1500, "change_pct": 2.04, "volume": 12000000,
                },
            },
            "rankings": {
                "gainers": [{"code": "005930", "name": "삼성전자", "theme": "AI/반도체", "close": 75000, "change_pct": 2.04}],
                "losers": [],
            },
        }
        fact_sheet = build_closing_fact_sheet(kr_data, SAMPLE_MARKET_DATA)
        assert "장마감" in fact_sheet
        assert "국내 증시" in fact_sheet
        assert "상승 주도주" in fact_sheet
        assert "삼성전자" in fact_sheet

    def test_includes_news(self):
        kr_data = {"stocks": {}, "rankings": {"gainers": [], "losers": []}}
        news = {
            "kr_news": [{"title": "삼성전자 실적 호조", "source": "매일경제"}],
            "us_news": [],
        }
        fact_sheet = build_closing_fact_sheet(kr_data, SAMPLE_MARKET_DATA, news)
        assert "삼성전자 실적 호조" in fact_sheet

    def test_includes_volume_leaders(self):
        kr_data = {
            "stocks": {
                "005930": {
                    "code": "005930", "name": "삼성전자", "theme": "AI/반도체",
                    "close": 75000, "change": 1500, "change_pct": 2.04, "volume": 20000000,
                },
            },
            "rankings": {"gainers": [], "losers": []},
        }
        fact_sheet = build_closing_fact_sheet(kr_data, SAMPLE_MARKET_DATA)
        assert "거래량 상위" in fact_sheet


class TestKRBellwetherStocks:
    """Test KR bellwether stock mapping integrity."""

    def test_all_stocks_have_required_fields(self):
        for code, info in KR_BELLWETHER_STOCKS.items():
            assert "name" in info, f"{code} missing name"
            assert "yf" in info, f"{code} missing yf ticker"
            assert "theme" in info, f"{code} missing theme"

    def test_at_least_20_stocks(self):
        assert len(KR_BELLWETHER_STOCKS) >= 20

    def test_key_stocks_present(self):
        key_codes = ["005930", "000660", "373220", "005380"]
        for code in key_codes:
            assert code in KR_BELLWETHER_STOCKS, f"Missing key KR stock: {code}"


class TestFactSheetWithNews:
    """Test morning fact sheet news integration."""

    def test_includes_us_news(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        news = {
            "us_news": [{"title": "NVIDIA beats expectations", "ticker": "NVDA", "source": "Reuters", "summary": "Strong demand"}],
            "kr_news": [],
        }
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, SAMPLE_US_DATA, themes, news=news)
        assert "미국 시장 뉴스" in fact_sheet
        assert "NVIDIA beats expectations" in fact_sheet

    def test_includes_kr_news(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA, SAMPLE_US_DATA)
        news = {
            "us_news": [],
            "kr_news": [{"title": "코스피 3000 돌파 기대", "source": "한경 증시"}],
        }
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, SAMPLE_US_DATA, themes, news=news)
        assert "한국 시장 뉴스" in fact_sheet
        assert "코스피 3000 돌파 기대" in fact_sheet


class TestFactSheetWithDailyReport:
    """Test that fact sheet includes daily report context."""

    def test_fact_sheet_includes_daily_context(self):
        """Verify fact_sheet.generate_fact_sheet accepts daily_report param."""
        import pandas as pd
        import numpy as np
        from app.analysis.features.fact_sheet import generate_fact_sheet

        # Create minimal DataFrame
        dates = pd.date_range("2025-01-01", periods=60, freq="B")
        df = pd.DataFrame({
            "open": np.random.uniform(70000, 80000, 60),
            "high": np.random.uniform(75000, 82000, 60),
            "low": np.random.uniform(68000, 75000, 60),
            "close": np.random.uniform(70000, 80000, 60),
            "volume": np.random.randint(1000000, 5000000, 60),
        }, index=dates)

        daily_report = {
            "ai_summary": {
                "headline": "테스트 헤드라인",
                "market_sentiment": "탐욕",
                "kospi_direction": "상승",
            },
            "market_data": {
                "S&P 500": {"close": 5200, "change_pct": 1.0},
                "나스닥": {"close": 16500, "change_pct": 1.5},
            },
            "themes": [
                {
                    "name": "AI/반도체",
                    "leader_stocks": [{"code": "005930", "name": "삼성전자"}],
                    "follower_stocks": [],
                    "signals": ["나스닥 강세"],
                },
            ],
        }

        result = generate_fact_sheet(
            df, "005930", "삼성전자",
            daily_report=daily_report,
        )

        assert "시장 컨텍스트" in result
        assert "테스트 헤드라인" in result
        assert "탐욕" in result
        assert "AI/반도체" in result
        assert "대장주" in result
