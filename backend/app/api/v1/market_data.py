"""Market data endpoints - connected to KIS API + Daily Market Intelligence."""

import logging
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.daily_report import DailyMarketReport
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


@router.get("/minute/{stock_code}",
             summary="Fetch intraday minute OHLCV data")
async def get_minute_data(
    stock_code: str,
    interval: int = 1,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetch intraday minute-candle OHLCV from KIS API.

    Supported intervals: 1, 3, 5, 10, 15, 30, 60 minutes.
    """
    try:
        kis = await get_kis_client(user.id, db)
        data = await kis.get_minute_ohlcv(stock_code, interval=interval)
        return {
            "stock_code": stock_code,
            "interval": f"{interval}min",
            "count": len(data),
            "data": data,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"KIS minute data fetch failed for {stock_code}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch minute data: {str(e)}")


@router.get("/mtf/{stock_code}",
             summary="Multi-timeframe analysis (5min, 15min, 1h, daily)")
async def get_mtf_analysis(
    stock_code: str,
    period: str = "1y",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run multi-timeframe trend/momentum analysis combining minute and daily data."""
    import pandas as pd
    from app.analysis.indicators.multi_timeframe import multi_timeframe_analysis

    try:
        kis = await get_kis_client(user.id, db)

        # Fetch minute data (latest session)
        minute_raw = await kis.get_minute_ohlcv(stock_code, interval=1)

        # Fetch daily data for higher timeframe
        end_date = datetime.now()
        period_map = {"3m": timedelta(days=90), "6m": timedelta(days=180), "1y": timedelta(days=365)}
        delta = period_map.get(period, timedelta(days=365))
        start_date = end_date - delta

        daily_raw = await kis.get_daily_ohlcv(
            stock_code, period_code="D",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )

        # Build DataFrames
        minute_df = pd.DataFrame()
        if minute_raw:
            minute_df = pd.DataFrame(minute_raw)
            minute_df["datetime"] = pd.to_datetime(minute_df["time"], format="%H%M%S", errors="coerce")
            minute_df = minute_df.dropna(subset=["datetime"])
            # Set today's date for the time
            today = pd.Timestamp.now().normalize()
            minute_df["datetime"] = today + pd.to_timedelta(
                minute_df["datetime"].dt.hour * 3600 +
                minute_df["datetime"].dt.minute * 60 +
                minute_df["datetime"].dt.second,
                unit="s",
            )
            minute_df = minute_df.set_index("datetime").sort_index()

        daily_df = None
        if daily_raw:
            daily_df = pd.DataFrame(daily_raw)
            daily_df["date"] = pd.to_datetime(daily_df["date"], format="%Y%m%d", errors="coerce")
            daily_df = daily_df.dropna(subset=["date"]).set_index("date").sort_index()

        result = multi_timeframe_analysis(minute_df, daily_df)

        return {
            "stock_code": stock_code,
            "consensus": result.consensus,
            "consensus_score": result.consensus_score,
            "alignment": result.alignment,
            "dominant_timeframe": result.dominant_timeframe,
            "recommendation": result.recommendation,
            "signals": {
                tf: {
                    "trend": sig.trend,
                    "strength": sig.strength,
                    "sma_20": sig.sma_20,
                    "sma_50": sig.sma_50,
                    "rsi_14": sig.rsi_14,
                    "macd_signal": sig.macd_signal,
                    "volume_trend": sig.volume_trend,
                }
                for tf, sig in result.signals.items()
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"MTF analysis failed for {stock_code}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to run MTF analysis: {str(e)}")


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
        kospi = await kis.get_index_price("0001")  # KOSPI
        kosdaq = await kis.get_index_price("1001")  # KOSDAQ
        return {
            "indices": [
                {"code": "KOSPI", "name": "코스피", "stock_code": "0001", **kospi},
                {"code": "KOSDAQ", "name": "코스닥", "stock_code": "1001", **kosdaq},
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


# ─── Daily Market Intelligence ──────────────────────────────────────


@router.get("/daily-report")
async def get_daily_report(
    report_date: str = Query(None, description="Date in YYYY-MM-DD format (default: today)"),
    report_type: str = Query("morning", description="Report type: morning | closing"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the daily market intelligence report.

    Free for all users — no token cost.
    Returns the latest report or a specific date's report.
    """
    target_date = date.today()
    if report_date:
        try:
            target_date = date.fromisoformat(report_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    result = await db.execute(
        select(DailyMarketReport).where(
            DailyMarketReport.report_date == target_date,
            DailyMarketReport.report_type == report_type,
        )
    )
    report = result.scalar_one_or_none()

    if not report:
        # Try to find the most recent report of this type
        result = await db.execute(
            select(DailyMarketReport)
            .where(
                DailyMarketReport.status == "completed",
                DailyMarketReport.report_type == report_type,
            )
            .order_by(DailyMarketReport.report_date.desc())
            .limit(1)
        )
        report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="아직 생성된 리포트가 없습니다.")

    return {
        "id": str(report.id),
        "report_date": str(report.report_date),
        "report_type": report.report_type,
        "status": report.status,
        "market_data": report.market_data,
        "themes": report.themes,
        "ai_summary": report.ai_summary,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.get("/daily-reports")
async def list_daily_reports(
    limit: int = Query(7, ge=1, le=30),
    report_type: str = Query("morning", description="Report type: morning | closing"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List recent daily market intelligence reports."""
    result = await db.execute(
        select(DailyMarketReport)
        .where(
            DailyMarketReport.status == "completed",
            DailyMarketReport.report_type == report_type,
        )
        .order_by(DailyMarketReport.report_date.desc())
        .limit(limit)
    )
    reports = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "report_date": str(r.report_date),
            "report_type": r.report_type,
            "headline": r.ai_summary.get("headline", "") if r.ai_summary else "",
            "market_sentiment": r.ai_summary.get("market_sentiment", "중립") if r.ai_summary else "중립",
            "kospi_direction": r.ai_summary.get("kospi_direction", "보합") if r.ai_summary else "보합",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reports
    ]


@router.post("/daily-report/generate")
async def trigger_daily_report(
    force: bool = Query(False, description="Force regeneration even if report exists"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Manually trigger morning report generation."""
    from app.services.market_intelligence import generate_daily_report

    try:
        result = await generate_daily_report(force=force)
        return result
    except Exception as e:
        logger.error("Manual daily report generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"리포트 생성 실패: {str(e)}")


@router.post("/closing-report/generate")
async def trigger_closing_report(
    force: bool = Query(False, description="Force regeneration even if report exists"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Manually trigger closing (장마감) report generation."""
    from app.services.market_intelligence import generate_closing_report

    try:
        result = await generate_closing_report(force=force)
        return result
    except Exception as e:
        logger.error("Manual closing report generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"장마감 리포트 생성 실패: {str(e)}")
