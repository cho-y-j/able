"""Tests for KIS investor trend, volume ranking, and price ranking API methods."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.integrations.kis.client import KISClient


@pytest.fixture
def kis_client():
    client = KISClient(
        app_key="test_key",
        app_secret="test_secret",
        account_number="50162896-01",
        is_paper=True,
    )
    return client


class TestGetInvestorTrends:
    @pytest.mark.asyncio
    async def test_parses_response(self, kis_client):
        mock_response = {
            "output": [{
                "frgn_ntby_qty": "50000",
                "orgn_ntby_qty": "-30000",
                "prsn_ntby_qty": "-20000",
                "frgn_ntby_tr_pbmn": "5000000000",
                "orgn_ntby_tr_pbmn": "-3000000000",
            }]
        }
        kis_client._request = AsyncMock(return_value=mock_response)

        result = await kis_client.get_investor_trends("005930")
        assert result["foreign_net_buy_qty"] == 50000
        assert result["institutional_net_buy_qty"] == -30000
        assert result["individual_net_buy_qty"] == -20000
        assert result["foreign_net_buy_amt"] == 5000000000

    @pytest.mark.asyncio
    async def test_empty_response(self, kis_client):
        kis_client._request = AsyncMock(return_value={"output": []})

        result = await kis_client.get_investor_trends("005930")
        assert result["foreign_net_buy_qty"] == 0
        assert result["institutional_net_buy_qty"] == 0

    @pytest.mark.asyncio
    async def test_request_params(self, kis_client):
        kis_client._request = AsyncMock(return_value={"output": []})

        await kis_client.get_investor_trends("005930")
        call_args = kis_client._request.call_args
        assert call_args[1]["params"]["FID_INPUT_ISCD"] == "005930"
        assert call_args[1]["params"]["FID_COND_MRKT_DIV_CODE"] == "J"


class TestGetVolumeRanking:
    @pytest.mark.asyncio
    async def test_parses_ranking(self, kis_client):
        mock_response = {
            "output": [
                {
                    "mksc_shrn_iscd": "005930",
                    "hts_kor_isnm": "삼성전자",
                    "stck_prpr": "78000",
                    "prdy_ctrt": "2.50",
                    "acml_vol": "15000000",
                },
                {
                    "mksc_shrn_iscd": "000660",
                    "hts_kor_isnm": "SK하이닉스",
                    "stck_prpr": "195000",
                    "prdy_ctrt": "3.20",
                    "acml_vol": "8000000",
                },
            ]
        }
        kis_client._request = AsyncMock(return_value=mock_response)

        result = await kis_client.get_volume_ranking(limit=10)
        assert len(result) == 2
        assert result[0]["rank"] == 1
        assert result[0]["stock_code"] == "005930"
        assert result[0]["stock_name"] == "삼성전자"
        assert result[0]["price"] == 78000
        assert result[0]["volume"] == 15000000

    @pytest.mark.asyncio
    async def test_limit_respected(self, kis_client):
        items = [
            {"mksc_shrn_iscd": f"00{i:04d}", "hts_kor_isnm": f"종목{i}",
             "stck_prpr": "1000", "prdy_ctrt": "1.0", "acml_vol": "100000"}
            for i in range(50)
        ]
        kis_client._request = AsyncMock(return_value={"output": items})

        result = await kis_client.get_volume_ranking(limit=5)
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_empty_response(self, kis_client):
        kis_client._request = AsyncMock(return_value={"output": []})
        result = await kis_client.get_volume_ranking()
        assert result == []


class TestGetPriceRanking:
    @pytest.mark.asyncio
    async def test_gainers(self, kis_client):
        mock_response = {
            "output": [{
                "stck_shrn_iscd": "005930",
                "hts_kor_isnm": "삼성전자",
                "stck_prpr": "78000",
                "prdy_ctrt": "5.20",
                "acml_vol": "20000000",
            }]
        }
        kis_client._request = AsyncMock(return_value=mock_response)

        result = await kis_client.get_price_ranking(direction="up")
        assert len(result) == 1
        assert result[0]["change_pct"] == 5.20

    @pytest.mark.asyncio
    async def test_losers_sort_code(self, kis_client):
        kis_client._request = AsyncMock(return_value={"output": []})

        await kis_client.get_price_ranking(direction="down")
        call_args = kis_client._request.call_args
        assert call_args[1]["params"]["FID_RANK_SORT_CLS_CODE"] == "1"

    @pytest.mark.asyncio
    async def test_gainers_sort_code(self, kis_client):
        kis_client._request = AsyncMock(return_value={"output": []})

        await kis_client.get_price_ranking(direction="up")
        call_args = kis_client._request.call_args
        assert call_args[1]["params"]["FID_RANK_SORT_CLS_CODE"] == "0"
