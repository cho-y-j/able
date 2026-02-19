"""Theme classifier for KRX stocks.

Maps stock sectors and names to thematic groups for trend analysis.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Sector → theme mapping (KRX sector names → display themes)
SECTOR_THEME_MAP: dict[str, list[str]] = {
    "반도체": ["AI/반도체"],
    "전자부품": ["AI/반도체"],
    "디스플레이": ["AI/반도체"],
    "IT하드웨어": ["AI/반도체"],
    "소프트웨어": ["AI/소프트웨어"],
    "IT서비스": ["AI/소프트웨어"],
    "게임": ["AI/소프트웨어"],
    "2차전지": ["2차전지/배터리"],
    "전기장비": ["2차전지/배터리"],
    "제약": ["바이오/제약"],
    "바이오": ["바이오/제약"],
    "헬스케어": ["바이오/제약"],
    "의료기기": ["바이오/제약"],
    "조선": ["조선/해양"],
    "해운": ["조선/해양"],
    "기계": ["조선/해양"],
    "자동차": ["자동차/모빌리티"],
    "자동차부품": ["자동차/모빌리티"],
    "운송": ["자동차/모빌리티"],
    "은행": ["금융/은행"],
    "증권": ["금융/은행"],
    "보험": ["금융/은행"],
    "카드": ["금융/은행"],
    "건설": ["건설/인프라"],
    "건자재": ["건설/인프라"],
    "철강": ["건설/인프라"],
    "에너지": ["에너지/유틸리티"],
    "유틸리티": ["에너지/유틸리티"],
    "석유화학": ["에너지/유틸리티"],
    "화학": ["화학/소재"],
    "정밀화학": ["화학/소재"],
    "섬유": ["소비재/유통"],
    "유통": ["소비재/유통"],
    "음식료": ["소비재/유통"],
    "화장품": ["소비재/유통"],
    "미디어": ["엔터/미디어"],
    "엔터테인먼트": ["엔터/미디어"],
    "통신": ["통신/인터넷"],
    "인터넷": ["통신/인터넷"],
}

# Keyword-based theme matching for stock names
NAME_KEYWORD_THEMES: dict[str, str] = {
    "전지": "2차전지/배터리",
    "배터리": "2차전지/배터리",
    "리튬": "2차전지/배터리",
    "수소": "에너지/유틸리티",
    "태양": "에너지/유틸리티",
    "풍력": "에너지/유틸리티",
    "로봇": "로봇/자동화",
    "자율주행": "자동차/모빌리티",
    "AI": "AI/소프트웨어",
    "인공지능": "AI/소프트웨어",
    "바이오": "바이오/제약",
    "제약": "바이오/제약",
    "셀": "바이오/제약",
    "반도체": "AI/반도체",
    "전자": "AI/반도체",
    "조선": "조선/해양",
    "해양": "조선/해양",
    "원전": "에너지/유틸리티",
    "원자력": "에너지/유틸리티",
    "방산": "방산/우주",
    "우주": "방산/우주",
    "항공": "방산/우주",
}

# All known themes
ALL_THEMES = sorted(set(
    theme
    for themes in SECTOR_THEME_MAP.values()
    for theme in themes
) | set(NAME_KEYWORD_THEMES.values()) | {"로봇/자동화", "방산/우주"})


def classify_stock(sector: str, name: str) -> list[str]:
    """Classify a stock into themes based on sector and name.

    Returns list of matching theme names (can be multiple).
    """
    themes = set()

    # Sector-based classification
    if sector in SECTOR_THEME_MAP:
        themes.update(SECTOR_THEME_MAP[sector])

    # Keyword-based classification from stock name
    for keyword, theme in NAME_KEYWORD_THEMES.items():
        if keyword in name:
            themes.add(theme)

    return sorted(themes)


def classify_stocks_batch(stocks: list[dict[str, str]]) -> dict[str, list[str]]:
    """Classify multiple stocks. Input: [{code, name, sector}, ...].

    Returns {stock_code: [theme1, theme2, ...]}
    """
    result = {}
    for stock in stocks:
        code = stock.get("code", "")
        name = stock.get("name", "")
        sector = stock.get("sector", "")
        themes = classify_stock(sector, name)
        if themes:
            result[code] = themes
    return result


def get_theme_stocks(stocks: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    """Group stocks by theme.

    Returns {theme_name: [{code, name}, ...]}
    """
    theme_map: dict[str, list[dict[str, str]]] = {}
    for stock in stocks:
        code = stock.get("code", "")
        name = stock.get("name", "")
        sector = stock.get("sector", "")
        themes = classify_stock(sector, name)
        for theme in themes:
            theme_map.setdefault(theme, []).append({"code": code, "name": name})
    return theme_map


def list_all_themes() -> list[str]:
    """Return all known theme names."""
    return ALL_THEMES
