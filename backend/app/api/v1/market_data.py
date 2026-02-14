"""Market data endpoints - connected to KIS API."""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.api.v1.deps import get_current_user
from app.services.kis_service import get_kis_client
from app.analysis.indicators.registry import calculate_indicator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/price/{stock_code}")
async def get_price(
    stock_code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetch real-time stock price from KIS API."""
    try:
        kis = await get_kis_client(user.id, db)
        price = await kis.get_price(stock_code)
        return price
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"KIS price fetch failed for {stock_code}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch price: {str(e)}")


@router.get("/ohlcv/{stock_code}")
async def get_ohlcv(
    stock_code: str,
    period: str = "1y",
    interval: str = "1d",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetch OHLCV data from KIS API."""
    try:
        kis = await get_kis_client(user.id, db)

        # Calculate date range from period
        end_date = datetime.now()
        period_map = {
            "1m": timedelta(days=30),
            "3m": timedelta(days=90),
            "6m": timedelta(days=180),
            "1y": timedelta(days=365),
            "2y": timedelta(days=730),
            "5y": timedelta(days=1825),
        }
        delta = period_map.get(period, timedelta(days=365))
        start_date = end_date - delta

        # KIS period code: D=daily, W=weekly, M=monthly
        period_code_map = {"1d": "D", "1w": "W", "1M": "M"}
        period_code = period_code_map.get(interval, "D")

        data = await kis.get_daily_ohlcv(
            stock_code,
            period_code=period_code,
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )
        return {
            "stock_code": stock_code,
            "period": period,
            "interval": interval,
            "count": len(data),
            "data": data,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"KIS OHLCV fetch failed for {stock_code}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch OHLCV: {str(e)}")


@router.get("/indicators/{stock_code}")
async def get_indicators(
    stock_code: str,
    indicators: str = "RSI_14,SMA_20,MACD_12_26_9",
    period: str = "1y",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Calculate technical indicators from KIS OHLCV data."""
    import pandas as pd

    try:
        kis = await get_kis_client(user.id, db)

        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 if period == "1y" else 180)

        raw = await kis.get_daily_ohlcv(
            stock_code,
            period_code="D",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )

        if not raw:
            raise HTTPException(status_code=404, detail="No OHLCV data available")

        # Build DataFrame
        df = pd.DataFrame(raw)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").set_index("date")

        indicator_list = [i.strip() for i in indicators.split(",")]
        results = {}

        for ind_spec in indicator_list:
            parts = ind_spec.split("_")
            name = parts[0]
            params = [int(p) for p in parts[1:] if p.isdigit()]

            try:
                result = calculate_indicator(name.lower(), df, params)
                # Convert to serializable format (last 100 values)
                if hasattr(result, "to_dict"):
                    values = result.tail(100)
                    results[ind_spec] = {
                        "dates": [str(d.date()) for d in values.index],
                        "values": [None if pd.isna(v) else round(float(v), 4) for v in values.values],
                    }
                elif isinstance(result, dict):
                    converted = {}
                    for k, v in result.items():
                        if hasattr(v, "tail"):
                            tail = v.tail(100)
                            converted[k] = {
                                "dates": [str(d.date()) for d in tail.index],
                                "values": [None if pd.isna(val) else round(float(val), 4) for val in tail.values],
                            }
                    results[ind_spec] = converted
            except Exception as e:
                results[ind_spec] = {"error": str(e)}

        return {
            "stock_code": stock_code,
            "data_points": len(df),
            "indicators": results,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Indicator calculation failed for {stock_code}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to calculate indicators: {str(e)}")


@router.get("/balance")
async def get_balance(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetch account balance from KIS API."""
    try:
        kis = await get_kis_client(user.id, db)
        balance = await kis.get_balance()
        return balance
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"KIS balance fetch failed: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch balance: {str(e)}")


@router.get("/indices")
async def get_indices(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetch KOSPI/KOSDAQ indices from KIS API."""
    try:
        kis = await get_kis_client(user.id, db)
        kospi = await kis.get_price("0001")  # KOSPI index code
        kosdaq = await kis.get_price("1001")  # KOSDAQ index code
        return {
            "indices": [
                {"code": "KOSPI", "name": "코스피", **kospi},
                {"code": "KOSDAQ", "name": "코스닥", **kosdaq},
            ]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"KIS indices fetch failed: {e}")
        return {
            "indices": [
                {"code": "KOSPI", "name": "코스피", "current_price": 0, "change": 0, "change_percent": 0, "volume": 0},
                {"code": "KOSDAQ", "name": "코스닥", "current_price": 0, "change": 0, "change_percent": 0, "volume": 0},
            ],
            "error": str(e),
        }
