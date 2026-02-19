"""Tests for market rankings service."""

import pytest
from app.services.market_rankings import compute_interest_score, build_interest_stocks


class TestComputeInterestScore:
    def test_top_ranked_stock(self):
        score, reasons = compute_interest_score(
            ranking_position=1,
            total_ranked=30,
        )
        assert score > 2.5
        assert any("상승률" in r for r in reasons)

    def test_active_theme_adds_score(self):
        score1, _ = compute_interest_score()
        score2, reasons = compute_interest_score(has_active_theme=True)
        assert score2 > score1
        assert "활성 테마 소속" in reasons

    def test_rsi_reversal(self):
        score, reasons = compute_interest_score(
            factor_signals={"rsi_14": 30.0},
        )
        assert score > 0
        assert "RSI 반등 구간" in reasons

    def test_macd_golden_cross(self):
        score, reasons = compute_interest_score(
            factor_signals={"macd_signal_cross": 1.0},
        )
        assert "MACD 골든크로스" in reasons

    def test_foreign_buying(self):
        score, reasons = compute_interest_score(
            foreign_net_buy=50000,
        )
        assert "외국인 순매수" in reasons

    def test_institutional_buying(self):
        score, reasons = compute_interest_score(
            institutional_net_buy=30000,
        )
        assert "기관 순매수" in reasons

    def test_max_score_capped_at_10(self):
        score, _ = compute_interest_score(
            ranking_position=1,
            has_active_theme=True,
            factor_signals={"rsi_14": 30, "macd_signal_cross": 1.0, "close_vs_low_20": 1.1},
            foreign_net_buy=100000,
            institutional_net_buy=100000,
        )
        assert score <= 10.0

    def test_no_inputs_returns_zero(self):
        score, reasons = compute_interest_score()
        assert score == 0.0
        assert reasons == []


class TestBuildInterestStocks:
    def test_combines_rankings(self):
        price_data = [
            {"rank": 1, "stock_code": "005930", "stock_name": "삼성전자",
             "price": 78000, "change_pct": 5.0, "volume": 15000000},
        ]
        volume_data = [
            {"rank": 1, "stock_code": "000660", "stock_name": "SK하이닉스",
             "price": 195000, "change_pct": 3.0, "volume": 8000000},
        ]
        results = build_interest_stocks(price_data, volume_data)
        assert len(results) == 2
        codes = {r["stock_code"] for r in results}
        assert "005930" in codes
        assert "000660" in codes

    def test_sorted_by_score(self):
        data = [
            {"rank": 1, "stock_code": "A", "stock_name": "Top",
             "price": 1000, "change_pct": 10.0, "volume": 100},
            {"rank": 30, "stock_code": "B", "stock_name": "Bottom",
             "price": 500, "change_pct": 0.1, "volume": 50},
        ]
        results = build_interest_stocks(data, [])
        assert results[0]["stock_code"] == "A"
        assert results[0]["score"] >= results[1]["score"]

    def test_limit_respected(self):
        data = [
            {"rank": i, "stock_code": f"S{i:04d}", "stock_name": f"Stock{i}",
             "price": 1000, "change_pct": 1.0, "volume": 100}
            for i in range(1, 30)
        ]
        results = build_interest_stocks(data, [], limit=5)
        assert len(results) == 5

    def test_empty_input(self):
        results = build_interest_stocks([], [])
        assert results == []

    def test_deduplication(self):
        """Same stock in both rankings should appear only once."""
        item = {"rank": 1, "stock_code": "005930", "stock_name": "삼성전자",
                "price": 78000, "change_pct": 5.0, "volume": 15000000}
        results = build_interest_stocks([item], [item])
        assert len(results) == 1

    def test_themes_included(self):
        data = [{"rank": 1, "stock_code": "005930", "stock_name": "삼성전자",
                 "price": 78000, "change_pct": 5.0, "volume": 15000000}]
        results = build_interest_stocks(
            data, [],
            stock_themes={"005930": ["AI/반도체"]},
        )
        assert results[0]["themes"] == ["AI/반도체"]

    def test_reasons_included(self):
        data = [{"rank": 1, "stock_code": "005930", "stock_name": "삼성전자",
                 "price": 78000, "change_pct": 5.0, "volume": 15000000}]
        results = build_interest_stocks(
            data, [],
            stock_flows={"005930": {"foreign_net_buy_qty": 10000}},
        )
        assert any("외국인" in r for r in results[0]["reasons"])
