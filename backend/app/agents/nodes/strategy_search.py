"""Strategy Search Agent: Finds optimal trading strategies per stock.

Enhanced to run actual backtests using the signal generator registry,
backtest engine, and composite scoring system.
"""

import json
import logging
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from app.agents.state import TradingState
from app.analysis.signals.registry import (
    get_signal_generator,
    get_signal_param_space,
    list_signal_generators_by_category,
)
from app.analysis.backtest.engine import run_backtest
from app.analysis.validation.scoring import calculate_composite_score

logger = logging.getLogger(__name__)

# Regime → preferred signal categories + specific generators
REGIME_SIGNALS: dict[str, list[str]] = {
    "bull": [
        "sma_crossover", "ema_crossover", "macd_crossover", "supertrend",
        "adx_trend", "donchian_breakout", "multi_ma_vote",
    ],
    "bear": [
        "rsi_mean_reversion", "cci_reversal", "williams_r_signal",
        "elder_impulse", "rsi_macd_combo", "stochastic_crossover",
    ],
    "sideways": [
        "rsi_mean_reversion", "bb_bounce", "stochastic_crossover",
        "mfi_signal", "roc_momentum", "cci_reversal",
    ],
    "volatile": [
        "keltner_breakout", "squeeze_momentum", "atr_trailing_stop",
        "bb_width_breakout", "bb_bounce", "supertrend",
    ],
    "crisis": [
        "rsi_mean_reversion", "stochastic_crossover", "bb_bounce",
        "atr_trailing_stop",
    ],
}

SYSTEM_PROMPT = """You are the Strategy Search agent in an AI-powered trading team.

Your responsibilities:
1. Based on market regime and stock characteristics, propose indicator combinations
2. Define entry/exit rules using technical indicators
3. Run backtests to evaluate strategy performance
4. Apply Walk-Forward Analysis for validation
5. Score strategies using the composite scoring system

Strategy types to consider by regime:
- Bull: Trend-following (MA crossovers, Supertrend, breakout)
- Bear: Short-biased or defensive (inverse signals, tight stops)
- Sideways: Mean-reversion (RSI oversold/overbought, BB bounce)
- Volatile: Volatility breakout (Keltner breakout, ATR trailing)

Always validate with Walk-Forward Analysis before recommending.
Minimum 50 trades required for statistical significance.

Respond with strategy recommendations in JSON format:
{
    "strategies": [
        {
            "stock_code": "005930",
            "signal_name": "rsi_mean_reversion",
            "parameters": {"rsi_period": 14, "oversold": 30, "overbought": 70},
            "reasoning": "why this strategy fits"
        }
    ]
}"""

MIN_SCORE_THRESHOLD = 30
MAX_CANDIDATES_PER_STOCK = 3
MAX_TOTAL_CANDIDATES = 10


def _fetch_ohlcv(stock_code: str) -> "pd.DataFrame | None":
    """Fetch OHLCV data for backtesting using Yahoo Finance (no creds needed)."""
    try:
        from app.integrations.data.factory import get_data_provider
        provider = get_data_provider("yahoo")
        df = provider.get_ohlcv(stock_code, period="1y")
        if df is not None and len(df) >= 60:
            return df
    except Exception as e:
        logger.warning(f"Failed to fetch OHLCV for {stock_code}: {e}")
    return None


def _run_quick_backtest(
    df: "pd.DataFrame",
    signal_name: str,
    params: dict | None = None,
) -> dict | None:
    """Run a quick backtest for a single signal generator on OHLCV data."""
    import pandas as pd

    try:
        gen = get_signal_generator(signal_name)
        if params is None:
            # Use midpoints of param_space as defaults
            space = get_signal_param_space(signal_name)
            params = {}
            for key, spec in space.items():
                if "values" in spec:
                    vals = spec["values"]
                    params[key] = vals[len(vals) // 2]
                elif "low" in spec and "high" in spec:
                    params[key] = (spec["low"] + spec["high"]) // 2
                elif "min" in spec and "max" in spec:
                    params[key] = (spec["min"] + spec["max"]) // 2

        entry_signals, exit_signals = gen(df, **params)

        if entry_signals.sum() < 3:
            return None

        result = run_backtest(df, entry_signals, exit_signals)

        metrics = {
            "total_return": result.total_return,
            "annual_return": result.annual_return,
            "sharpe_ratio": result.sharpe_ratio,
            "sortino_ratio": result.sortino_ratio,
            "max_drawdown": result.max_drawdown,
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
            "total_trades": result.total_trades,
            "calmar_ratio": result.calmar_ratio,
        }

        score_result = calculate_composite_score(metrics)

        return {
            "metrics": metrics,
            "composite_score": score_result.get("composite_score", 0),
            "grade": score_result.get("grade", "F"),
            "params": params,
        }
    except Exception as e:
        logger.debug(f"Quick backtest failed for {signal_name}: {e}")
        return None


async def strategy_search_node(state: TradingState) -> dict:
    """LangGraph node: searches for optimal strategies with actual backtesting."""

    regime = state.get("market_regime", {})
    classification = regime.get("classification", "sideways") if regime else "sideways"
    watchlist = state.get("watchlist", [])

    candidates = state.get("strategy_candidates", [])

    # If candidates exist already, skip search
    if candidates:
        return {
            "messages": [AIMessage(
                content=f"[Strategy Search] {len(candidates)} existing candidates. Skipping search."
            )],
            "strategy_candidates": candidates,
            "optimization_status": "complete",
            "current_agent": "strategy_search",
        }

    # Try LLM-guided strategy selection first
    llm = state.get("_llm")
    llm_suggestions: list[dict] = []

    if llm and watchlist:
        try:
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=(
                    f"Market regime: {classification}. "
                    f"Watchlist: {', '.join(watchlist)}. "
                    f"Available signals: {', '.join(REGIME_SIGNALS.get(classification, REGIME_SIGNALS['sideways']))}. "
                    f"Propose optimal strategies for each stock."
                )),
            ]
            response = await llm.ainvoke(messages)
            text = response.content
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            parsed = json.loads(text.strip())
            llm_suggestions = parsed.get("strategies", [])
        except Exception as e:
            logger.warning(f"LLM strategy search failed, using rule-based: {e}")

    # Build candidate list: LLM suggestions + regime-based defaults
    signal_list = REGIME_SIGNALS.get(classification, REGIME_SIGNALS["sideways"])
    stocks = watchlist[:5]

    if not stocks:
        return {
            "messages": [AIMessage(
                content="[Strategy Search] No stocks in watchlist. Cannot search."
            )],
            "strategy_candidates": [],
            "optimization_status": "no_opportunities",
            "current_agent": "strategy_search",
        }

    # Phase 1: Run backtests for each stock × signal combination
    all_candidates: list[dict] = []
    tested_count = 0
    skipped_count = 0

    for stock_code in stocks:
        df = _fetch_ohlcv(stock_code)
        if df is None:
            skipped_count += 1
            logger.warning(f"No OHLCV data for {stock_code}, skipping")
            continue

        stock_results: list[dict] = []

        # Check LLM-suggested signals for this stock first
        llm_signals_for_stock = [
            s for s in llm_suggestions if s.get("stock_code") == stock_code
        ]

        for suggestion in llm_signals_for_stock:
            sig_name = suggestion.get("signal_name", "")
            params = suggestion.get("parameters")
            try:
                bt = _run_quick_backtest(df, sig_name, params)
            except ValueError:
                continue
            if bt:
                tested_count += 1
                stock_results.append({
                    "stock_code": stock_code,
                    "strategy_name": f"{sig_name}_{stock_code}",
                    "signal_name": sig_name,
                    "parameters": bt["params"],
                    "backtest_metrics": bt["metrics"],
                    "validation_scores": {"grade": bt["grade"]},
                    "composite_score": bt["composite_score"],
                    "source": "llm",
                })

        # Also try regime-appropriate signals
        tested_signals = {s.get("signal_name") for s in llm_signals_for_stock}
        for sig_name in signal_list:
            if sig_name in tested_signals:
                continue
            bt = _run_quick_backtest(df, sig_name)
            tested_count += 1
            if bt:
                stock_results.append({
                    "stock_code": stock_code,
                    "strategy_name": f"{sig_name}_{stock_code}",
                    "signal_name": sig_name,
                    "parameters": bt["params"],
                    "backtest_metrics": bt["metrics"],
                    "validation_scores": {"grade": bt["grade"]},
                    "composite_score": bt["composite_score"],
                    "source": "registry",
                })

        # Keep top N per stock by composite score
        stock_results.sort(key=lambda x: x["composite_score"], reverse=True)
        top = [r for r in stock_results if r["composite_score"] >= MIN_SCORE_THRESHOLD]
        all_candidates.extend(top[:MAX_CANDIDATES_PER_STOCK])

    # Phase 2: Rank globally and trim
    all_candidates.sort(key=lambda x: x["composite_score"], reverse=True)
    final_candidates = all_candidates[:MAX_TOTAL_CANDIDATES]

    summary_parts = []
    for c in final_candidates:
        summary_parts.append(
            f"  {c['stock_code']}/{c['signal_name']}: "
            f"score={c['composite_score']:.1f} ({c['validation_scores'].get('grade', '?')}), "
            f"return={c['backtest_metrics'].get('total_return', 0):.1%}, "
            f"sharpe={c['backtest_metrics'].get('sharpe_ratio', 0):.2f}"
        )

    msg = (
        f"[Strategy Search] Tested {tested_count} signal/stock combinations "
        f"({skipped_count} stocks skipped). "
        f"Selected {len(final_candidates)} candidates (score >= {MIN_SCORE_THRESHOLD}):\n"
        + "\n".join(summary_parts)
    )

    return {
        "messages": [AIMessage(content=msg)],
        "strategy_candidates": final_candidates,
        "optimization_status": "complete" if final_candidates else "no_opportunities",
        "current_agent": "strategy_search",
    }
