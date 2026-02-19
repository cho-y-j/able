"""Tests for theme classifier service."""

import pytest
from app.services.theme_classifier import (
    classify_stock,
    classify_stocks_batch,
    get_theme_stocks,
    list_all_themes,
    ALL_THEMES,
)


class TestClassifyStock:
    def test_sector_based_classification(self):
        themes = classify_stock("반도체", "삼성전자")
        assert "AI/반도체" in themes

    def test_keyword_based_classification(self):
        themes = classify_stock("", "수소연료전지")
        assert "에너지/유틸리티" in themes

    def test_multiple_themes(self):
        themes = classify_stock("전자부품", "삼성전자 반도체")
        assert "AI/반도체" in themes

    def test_no_match_returns_empty(self):
        themes = classify_stock("기타", "알 수 없는 종목")
        assert themes == []

    def test_pharmaceutical(self):
        themes = classify_stock("제약", "셀트리온")
        assert "바이오/제약" in themes

    def test_auto(self):
        themes = classify_stock("자동차", "현대차")
        assert "자동차/모빌리티" in themes

    def test_finance(self):
        themes = classify_stock("은행", "KB금융")
        assert "금융/은행" in themes

    def test_keyword_override(self):
        """Stock name keywords should classify even without matching sector."""
        themes = classify_stock("기타서비스", "AI로봇솔루션")
        assert "AI/소프트웨어" in themes or "로봇/자동화" in themes

    def test_returns_sorted(self):
        themes = classify_stock("반도체", "AI반도체")
        assert themes == sorted(themes)


class TestClassifyStocksBatch:
    def test_batch_classification(self):
        stocks = [
            {"code": "005930", "name": "삼성전자", "sector": "반도체"},
            {"code": "035720", "name": "카카오", "sector": "인터넷"},
            {"code": "000660", "name": "SK하이닉스", "sector": "반도체"},
        ]
        result = classify_stocks_batch(stocks)
        assert "005930" in result
        assert "AI/반도체" in result["005930"]
        assert "035720" in result
        assert "통신/인터넷" in result["035720"]

    def test_empty_input(self):
        assert classify_stocks_batch([]) == {}


class TestGetThemeStocks:
    def test_groups_by_theme(self):
        stocks = [
            {"code": "005930", "name": "삼성전자", "sector": "반도체"},
            {"code": "000660", "name": "SK하이닉스", "sector": "반도체"},
            {"code": "035720", "name": "카카오", "sector": "인터넷"},
        ]
        themes = get_theme_stocks(stocks)
        assert "AI/반도체" in themes
        assert len(themes["AI/반도체"]) == 2

    def test_empty_input(self):
        assert get_theme_stocks([]) == {}


class TestListAllThemes:
    def test_returns_sorted_list(self):
        themes = list_all_themes()
        assert isinstance(themes, list)
        assert len(themes) >= 10
        assert themes == sorted(themes)

    def test_includes_major_themes(self):
        themes = list_all_themes()
        assert "AI/반도체" in themes
        assert "2차전지/배터리" in themes
        assert "바이오/제약" in themes
        assert "금융/은행" in themes
