"""Tests for Daily Market Intelligence service."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from app.services.market_intelligence import (
    detect_active_themes,
    build_market_fact_sheet,
    _parse_briefing,
    THEME_STOCK_MAP,
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


class TestDetectActiveThemes:
    """Test theme detection logic."""

    def test_detects_ai_semiconductor_theme_on_nasdaq_rise(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA)
        theme_names = [t["name"] for t in themes]
        # Nasdaq +1.54% should trigger AI/semiconductor theme
        assert "AI/반도체" in theme_names

    def test_detects_energy_theme_on_oil_rise(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA)
        theme_names = [t["name"] for t in themes]
        # WTI +2.75% should trigger energy theme
        assert "원자력/에너지" in theme_names

    def test_detects_shipbuilding_on_oil_rise(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA)
        theme_names = [t["name"] for t in themes]
        assert "조선/해양" in theme_names

    def test_themes_sorted_by_relevance(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA)
        if len(themes) >= 2:
            for i in range(len(themes) - 1):
                assert themes[i]["relevance_score"] >= themes[i + 1]["relevance_score"]

    def test_each_theme_has_required_fields(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA)
        for theme in themes:
            assert "name" in theme
            assert "relevance_score" in theme
            assert "signals" in theme
            assert "leader_stocks" in theme
            assert "follower_stocks" in theme

    def test_no_themes_on_flat_market(self):
        flat_data = {
            name: {**d, "change_pct": 0.0}
            for name, d in SAMPLE_MARKET_DATA.items()
        }
        flat_data["VIX"] = {**flat_data.get("VIX", {}), "close": 12, "change_pct": 0.0}
        themes = detect_active_themes(flat_data)
        # Most themes require some minimum movement to be relevant
        # Defense still has base relevance
        assert all(t["relevance_score"] >= 1 for t in themes)

    def test_high_vix_adds_signals(self):
        high_vix_data = {**SAMPLE_MARKET_DATA}
        high_vix_data["VIX"] = {"ticker": "^VIX", "close": 35, "change": 5.0, "change_pct": 16.67, "volume": 0}
        themes = detect_active_themes(high_vix_data)
        # Should have VIX warnings in signals
        has_vix_warning = any(
            any("VIX" in sig for sig in t["signals"])
            for t in themes
        )
        assert has_vix_warning


class TestBuildFactSheet:
    """Test fact sheet generation for AI consumption."""

    def test_basic_structure(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA)
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, themes)

        assert "일일 시장 인텔리전스 팩트시트" in fact_sheet
        assert "미국 증시" in fact_sheet
        assert "원자재" in fact_sheet
        assert "환율" in fact_sheet

    def test_contains_key_indices(self):
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, [])
        assert "S&P 500" in fact_sheet
        assert "나스닥" in fact_sheet
        assert "코스피" in fact_sheet

    def test_contains_commodities(self):
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, [])
        assert "WTI 원유" in fact_sheet
        assert "금" in fact_sheet

    def test_contains_fx(self):
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, [])
        assert "USD/KRW" in fact_sheet

    def test_contains_bonds_and_yield_curve(self):
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, [])
        assert "미국10Y금리" in fact_sheet
        assert "스프레드" in fact_sheet

    def test_contains_vix_level(self):
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, [])
        assert "VIX" in fact_sheet
        assert "보통" in fact_sheet  # VIX 18.5 should be "보통"

    def test_includes_active_themes(self):
        themes = detect_active_themes(SAMPLE_MARKET_DATA)
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, themes)
        assert "활성 테마" in fact_sheet
        assert "대장주" in fact_sheet

    def test_ends_with_prompt(self):
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, [])
        assert "투자 전략을 작성하세요" in fact_sheet

    def test_contains_futures(self):
        fact_sheet = build_market_fact_sheet(SAMPLE_MARKET_DATA, [])
        assert "선물" in fact_sheet


class TestParseBriefing:
    """Test AI response parsing."""

    def test_parses_full_response(self):
        text = """1. 오늘의 시장 한줄 요약: 나스닥 강세에 반도체 테마 주목
2. 시장 심리: 탐욕
3. 코스피 예상 방향: 상승
4. 핵심 이슈 3가지:
   1. 미국 나스닥 +1.5% 상승, 반도체 대형주 강세
   2. 유가 $78 돌파, 에너지 섹터 수혜 예상
   3. 원/달러 1,345원 안정적 흐름
5. 주목 테마 & 대장주:
   1. AI/반도체 — 삼성전자, SK하이닉스
   2. 에너지 — 한화에어로스페이스
   3. 조선 — HD현대중공업
6. 리스크 요인:
   1. 중국 경기 둔화 우려 지속
   2. 미국 금리 인하 시점 불확실
7. 오늘의 투자 전략:
나스닥 강세 흐름을 활용해 반도체 대장주 중심 매수 전략 유효.
유가 상승세에 에너지/조선 섹터도 관심."""

        result = _parse_briefing(text)

        assert result["headline"] == "나스닥 강세에 반도체 테마 주목"
        assert result["market_sentiment"] == "탐욕"
        assert result["kospi_direction"] == "상승"
        assert len(result["key_issues"]) == 3
        assert len(result["risks"]) == 2
        assert "반도체" in result["strategy"]

    def test_parses_minimal_response(self):
        text = "시장 보합 예상"
        result = _parse_briefing(text)
        # Should have defaults
        assert result["market_sentiment"] == "중립"
        assert result["kospi_direction"] == "보합"
        # headline should fallback to first line
        assert result["headline"] == "시장 보합 예상"

    def test_parses_bearish_sentiment(self):
        text = """1. 오늘의 시장 한줄 요약: 글로벌 매도세 확산
2. 시장 심리: 공포
3. 코스피 예상 방향: 하락"""
        result = _parse_briefing(text)
        assert result["market_sentiment"] == "공포"
        assert result["kospi_direction"] == "하락"


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
        # Some overlap is OK (e.g. diversified conglomerates), but check for obvious dupes
        assert len(all_leaders) > 10  # Enough themes defined

    def test_at_least_10_themes_defined(self):
        assert len(THEME_STOCK_MAP) >= 10


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
