"""Fetch KRX (KOSPI + KOSDAQ) stock list and save as JSON.

Usage:
    python scripts/fetch_krx_stocks.py
"""

import json
from pathlib import Path
from pykrx import stock as krx

OUTPUT = Path(__file__).parent.parent / "app" / "data" / "krx_stocks.json"


def fetch_all_stocks() -> list[dict]:
    """Fetch all KOSPI + KOSDAQ stocks via pykrx."""
    stocks = []

    for market, market_name in [("KOSPI", "KOSPI"), ("KOSDAQ", "KOSDAQ")]:
        print(f"Fetching {market} stocks...")
        tickers = krx.get_market_ticker_list(market=market)
        for code in tickers:
            name = krx.get_market_ticker_name(code)
            stocks.append({
                "code": code,
                "name": name,
                "market": market_name,
                "sector": "",
            })
        print(f"  -> {len(tickers)} stocks")

    # Try to add sector info from KOSPI/KOSDAQ sector data
    try:
        for market in ["KOSPI", "KOSDAQ"]:
            tickers = krx.get_market_ticker_list(market=market)
            for code in tickers:
                try:
                    info = krx.get_stock_sector_info(code)
                    if info:
                        for s in stocks:
                            if s["code"] == code:
                                s["sector"] = info
                                break
                except Exception:
                    pass
    except Exception:
        pass  # Sector info is optional

    stocks.sort(key=lambda x: x["code"])
    return stocks


def main():
    all_stocks = fetch_all_stocks()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(all_stocks, f, ensure_ascii=False, indent=None, separators=(",", ":"))

    print(f"\nSaved {len(all_stocks)} stocks to {OUTPUT}")
    print(f"File size: {OUTPUT.stat().st_size / 1024:.1f} KB")

    # Quick check
    snt = [s for s in all_stocks if "SNT" in s["name"].upper()]
    print(f"SNT stocks found: {snt}")


if __name__ == "__main__":
    main()
