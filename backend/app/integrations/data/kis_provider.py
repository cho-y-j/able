"""KIS (Korea Investment Securities) data provider wrapping existing KIS client."""

import logging

import httpx
import pandas as pd

from app.integrations.data.base import DataProvider
from app.integrations.kis.constants import (
    PAPER_BASE_URL, REAL_BASE_URL,
    STOCK_PRICE_PATH, STOCK_DAILY_PRICE_PATH,
    TR_ID_PRICE, TR_ID_DAILY_PRICE,
)

logger = logging.getLogger(__name__)


class KISDataProvider(DataProvider):
    """KIS API data provider (requires API credentials)."""

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        account_number: str = "",
        is_paper: bool = True,
    ):
        self.app_key = app_key
        self.app_secret = app_secret
        self.account_number = account_number
        self.is_paper = is_paper
        self.base_url = PAPER_BASE_URL if is_paper else REAL_BASE_URL
        self._access_token: str | None = None

    def _get_token(self) -> str:
        """Get OAuth access token synchronously."""
        if self._access_token:
            return self._access_token

        token_url = f"{self.base_url}/oauth2/tokenP"
        resp = httpx.post(token_url, json={
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }, timeout=10.0)
        resp.raise_for_status()
        self._access_token = resp.json()["access_token"]
        return self._access_token

    def _headers(self, tr_id: str) -> dict:
        token = self._get_token()
        return {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
        }

    def get_ohlcv(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        # Normalize dates (YYYY-MM-DD → YYYYMMDD)
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
            "FID_INPUT_DATE_1": start,
            "FID_INPUT_DATE_2": end,
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0",
        }

        resp = httpx.get(
            f"{self.base_url}{STOCK_DAILY_PRICE_PATH}",
            headers=self._headers(TR_ID_DAILY_PRICE),
            params=params,
            timeout=10.0,
        )
        resp.raise_for_status()
        items = resp.json().get("output2", [])

        rows = []
        for item in items:
            if not item.get("stck_bsop_date"):
                continue
            rows.append({
                "date": item["stck_bsop_date"],
                "open": float(item.get("stck_oprc", 0)),
                "high": float(item.get("stck_hgpr", 0)),
                "low": float(item.get("stck_lwpr", 0)),
                "close": float(item.get("stck_clpr", 0)),
                "volume": int(item.get("acml_vol", 0)),
            })

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").set_index("date")
        return df

    def get_price(self, stock_code: str) -> dict:
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
        }
        resp = httpx.get(
            f"{self.base_url}{STOCK_PRICE_PATH}",
            headers=self._headers(TR_ID_PRICE),
            params=params,
            timeout=10.0,
        )
        resp.raise_for_status()
        output = resp.json().get("output", {})
        return {
            "stock_code": stock_code,
            "current_price": float(output.get("stck_prpr", 0)),
            "change": float(output.get("prdy_vrss", 0)),
            "change_percent": float(output.get("prdy_ctrt", 0)),
            "volume": int(output.get("acml_vol", 0)),
            "high": float(output.get("stck_hgpr", 0)),
            "low": float(output.get("stck_lwpr", 0)),
            "open": float(output.get("stck_oprc", 0)),
        }

    @property
    def name(self) -> str:
        return "kis"

    @property
    def requires_credentials(self) -> bool:
        return True
