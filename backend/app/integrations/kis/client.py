import httpx
from typing import Any
from app.integrations.kis.auth import KISTokenManager
from app.integrations.kis.constants import (
    REAL_BASE_URL, PAPER_BASE_URL,
    STOCK_PRICE_PATH, STOCK_DAILY_PRICE_PATH, STOCK_MINUTE_PRICE_PATH,
    STOCK_ORDERBOOK_PATH,
    BALANCE_PATH,
    ORDER_PATH, ORDER_CANCEL_PATH,
    CONDITION_LIST_PATH, CONDITION_RESULT_PATH,
    TR_ID_BUY, TR_ID_SELL, TR_ID_BUY_PAPER, TR_ID_SELL_PAPER,
    TR_ID_BALANCE, TR_ID_BALANCE_PAPER, TR_ID_PRICE, TR_ID_DAILY_PRICE,
    TR_ID_MINUTE_PRICE,
    TR_ID_CONDITION_LIST, TR_ID_CONDITION_RESULT,
)


class KISClient:
    """Korea Investment Securities REST API client."""

    def __init__(self, app_key: str, app_secret: str, account_number: str, is_paper: bool = True):
        self.account_number = account_number
        # Account format: "50162896-01" → prefix="50162896", suffix="01"
        if "-" in account_number:
            self.account_prefix, self.account_suffix = account_number.split("-", 1)
        else:
            self.account_prefix = account_number[:8]
            self.account_suffix = account_number[8:]
        self.is_paper = is_paper
        self.base_url = PAPER_BASE_URL if is_paper else REAL_BASE_URL
        self.token_manager = KISTokenManager(app_key, app_secret, is_paper)

    async def _request(self, method: str, path: str, tr_id: str,
                       params: dict | None = None, body: dict | None = None) -> dict[str, Any]:
        token = await self.token_manager.get_token()
        headers = self.token_manager.headers
        headers["tr_id"] = tr_id

        async with httpx.AsyncClient() as client:
            if method == "GET":
                resp = await client.get(
                    f"{self.base_url}{path}",
                    headers=headers,
                    params=params,
                    timeout=10.0,
                )
            else:
                resp = await client.post(
                    f"{self.base_url}{path}",
                    headers=headers,
                    json=body,
                    timeout=10.0,
                )

            resp.raise_for_status()
            return resp.json()

    async def validate_credentials(self) -> bool:
        try:
            await self.token_manager.get_token()
            return True
        except Exception:
            return False

    async def get_price(self, stock_code: str) -> dict:
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
        }
        data = await self._request("GET", STOCK_PRICE_PATH, TR_ID_PRICE, params=params)
        output = data.get("output", {})
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

    async def get_orderbook(self, stock_code: str) -> dict:
        """Get order book (호가창) for spread and depth analysis."""
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
        }
        data = await self._request("GET", STOCK_ORDERBOOK_PATH, "FHKST01010200", params=params)
        output = data.get("output1", {})
        return {
            "stock_code": stock_code,
            "best_ask": float(output.get("askp1", 0)),
            "best_bid": float(output.get("bidp1", 0)),
            "ask_volume_1": int(output.get("askp_rsqn1", 0)),
            "bid_volume_1": int(output.get("bidp_rsqn1", 0)),
            "total_ask_volume": int(output.get("total_askp_rsqn", 0)),
            "total_bid_volume": int(output.get("total_bidp_rsqn", 0)),
        }

    async def get_daily_ohlcv(self, stock_code: str, period_code: str = "D",
                               start_date: str = "", end_date: str = "") -> list[dict]:
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": period_code,
            "FID_ORG_ADJ_PRC": "0",
        }
        data = await self._request("GET", STOCK_DAILY_PRICE_PATH, TR_ID_DAILY_PRICE, params=params)
        items = data.get("output2", [])
        return [{
            "date": item.get("stck_bsop_date", ""),
            "open": float(item.get("stck_oprc", 0)),
            "high": float(item.get("stck_hgpr", 0)),
            "low": float(item.get("stck_lwpr", 0)),
            "close": float(item.get("stck_clpr", 0)),
            "volume": int(item.get("acml_vol", 0)),
        } for item in items if item.get("stck_bsop_date")]

    async def get_minute_ohlcv(self, stock_code: str, interval: int = 1,
                               end_time: str = "153000") -> list[dict]:
        """Fetch intraday minute OHLCV data.

        Args:
            stock_code: Stock code (e.g. "005930")
            interval: Candle interval in minutes (1, 3, 5, 10, 15, 30, 60)
            end_time: End time in HHMMSS format (default: market close 15:30)

        Returns:
            List of OHLCV dicts with time field
        """
        params = {
            "FID_ETC_CLS_CODE": "",
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
            "FID_INPUT_HOUR_1": end_time,
            "FID_PW_DATA_INCU_YN": "Y",
        }
        data = await self._request(
            "GET", STOCK_MINUTE_PRICE_PATH, TR_ID_MINUTE_PRICE, params=params
        )
        items = data.get("output2", [])
        result = []
        for item in items:
            time_val = item.get("stck_cntg_hour", "")
            if not time_val:
                continue
            result.append({
                "time": time_val,
                "open": float(item.get("stck_oprc", 0)),
                "high": float(item.get("stck_hgpr", 0)),
                "low": float(item.get("stck_lwpr", 0)),
                "close": float(item.get("stck_prpr", 0)),
                "volume": int(item.get("cntg_vol", 0)),
            })
        return result

    async def get_balance(self) -> dict:
        tr_id = TR_ID_BALANCE_PAPER if self.is_paper else TR_ID_BALANCE
        params = {
            "CANO": self.account_prefix,
            "ACNT_PRDT_CD": self.account_suffix,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        data = await self._request("GET", BALANCE_PATH, tr_id, params=params)
        output2 = data.get("output2", [{}])
        summary = output2[0] if output2 else {}
        return {
            "total_balance": float(summary.get("tot_evlu_amt", 0)),
            "available_cash": float(summary.get("dnca_tot_amt", 0)),
            "invested_amount": float(summary.get("scts_evlu_amt", 0)),
            "total_pnl": float(summary.get("evlu_pfls_smtl_amt", 0)),
        }

    async def place_order(self, stock_code: str, side: str, quantity: int,
                          price: int = 0, order_type: str = "market") -> dict:
        if side == "buy":
            tr_id = TR_ID_BUY_PAPER if self.is_paper else TR_ID_BUY
        else:
            tr_id = TR_ID_SELL_PAPER if self.is_paper else TR_ID_SELL

        # Order type: "01" = limit, "00" = market (best)
        ord_dvsn = "01" if order_type == "limit" else "00"

        body = {
            "CANO": self.account_prefix,
            "ACNT_PRDT_CD": self.account_suffix,
            "PDNO": stock_code,
            "ORD_DVSN": ord_dvsn,
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price) if order_type == "limit" else "0",
        }
        data = await self._request("POST", ORDER_PATH, tr_id, body=body)
        output = data.get("output", {})
        return {
            "kis_order_id": output.get("ODNO", ""),
            "order_time": output.get("ORD_TMD", ""),
            "success": data.get("rt_cd") == "0",
            "message": data.get("msg1", ""),
        }

    async def cancel_order(self, order_id: str, stock_code: str, quantity: int) -> dict:
        tr_id = "VTTC0803U" if self.is_paper else "TTTC0803U"
        body = {
            "CANO": self.account_prefix,
            "ACNT_PRDT_CD": self.account_suffix,
            "KRX_FWDG_ORD_ORGNO": "",
            "ORGN_ODNO": order_id,
            "ORD_DVSN": "00",
            "RVSE_CNCL_DVSN_CD": "02",
            "ORD_QTY": str(quantity),
            "ORD_UNPR": "0",
            "QTY_ALL_ORD_YN": "Y",
        }
        data = await self._request("POST", ORDER_CANCEL_PATH, tr_id, body=body)
        return {
            "success": data.get("rt_cd") == "0",
            "message": data.get("msg1", ""),
        }

    async def get_condition_list(self) -> list[dict]:
        """Get saved condition search list (조건검색 목록 조회).

        Returns list of condition search presets saved in the KIS HTS/MTS.
        """
        params = {
            "user_id": "",
        }
        data = await self._request("GET", CONDITION_LIST_PATH, TR_ID_CONDITION_LIST, params=params)
        items = data.get("output2", [])
        return [{
            "condition_id": item.get("condition_seq", ""),
            "condition_name": item.get("condition_nm", ""),
        } for item in items if item.get("condition_seq")]

    async def run_condition_search(self, condition_id: str) -> list[dict]:
        """Execute condition search and return matching stocks (조건검색 실행).

        Args:
            condition_id: Condition sequence ID from get_condition_list

        Returns:
            List of matching stocks with code, name, price, volume info
        """
        params = {
            "user_id": "",
            "seq": condition_id,
        }
        data = await self._request("GET", CONDITION_RESULT_PATH, TR_ID_CONDITION_RESULT, params=params)
        items = data.get("output2", [])
        return [{
            "stock_code": item.get("stck_shrn_iscd", ""),
            "stock_name": item.get("hts_kor_isnm", ""),
            "current_price": float(item.get("stck_prpr", 0)),
            "change_percent": float(item.get("prdy_ctrt", 0)),
            "volume": int(item.get("acml_vol", 0)),
        } for item in items if item.get("stck_shrn_iscd")]
