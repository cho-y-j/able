import pandas as pd
import numpy as np
from app.analysis.indicators.registry import register_indicator


@register_indicator("RSI")
def rsi(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.DataFrame:
    delta = df[column].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df[f"RSI_{period}"] = 100 - (100 / (1 + rs))
    return df


@register_indicator("STOCH")
def stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    low_min = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    df[f"STOCH_K_{k_period}"] = 100 * (df["close"] - low_min) / (high_max - low_min)
    df[f"STOCH_D_{k_period}"] = df[f"STOCH_K_{k_period}"].rolling(d_period).mean()
    return df


@register_indicator("STOCHRSI")
def stochastic_rsi(df: pd.DataFrame, rsi_period: int = 14, stoch_period: int = 14,
                    k_period: int = 3, d_period: int = 3) -> pd.DataFrame:
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1 / rsi_period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / rsi_period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))

    rsi_min = rsi_val.rolling(stoch_period).min()
    rsi_max = rsi_val.rolling(stoch_period).max()
    stoch_rsi = (rsi_val - rsi_min) / (rsi_max - rsi_min)

    df[f"STOCHRSI_K"] = stoch_rsi.rolling(k_period).mean()
    df[f"STOCHRSI_D"] = df["STOCHRSI_K"].rolling(d_period).mean()
    return df


@register_indicator("CCI")
def cci(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    df[f"CCI_{period}"] = (tp - sma) / (0.015 * mad)
    return df


@register_indicator("WILLR")
def williams_r(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high_max = df["high"].rolling(period).max()
    low_min = df["low"].rolling(period).min()
    df[f"WILLR_{period}"] = -100 * (high_max - df["close"]) / (high_max - low_min)
    return df


@register_indicator("ROC")
def roc(df: pd.DataFrame, period: int = 12, column: str = "close") -> pd.DataFrame:
    df[f"ROC_{period}"] = 100 * (df[column] - df[column].shift(period)) / df[column].shift(period)
    return df


@register_indicator("MFI")
def mfi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    mf = tp * df["volume"]
    positive = mf.where(tp > tp.shift(), 0).rolling(period).sum()
    negative = mf.where(tp < tp.shift(), 0).rolling(period).sum()
    ratio = positive / negative.replace(0, np.nan)
    df[f"MFI_{period}"] = 100 - (100 / (1 + ratio))
    return df


@register_indicator("UO")
def ultimate_oscillator(df: pd.DataFrame, p1: int = 7, p2: int = 14, p3: int = 28) -> pd.DataFrame:
    close_prev = df["close"].shift()
    bp = df["close"] - pd.concat([df["low"], close_prev], axis=1).min(axis=1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - close_prev).abs(),
        (df["low"] - close_prev).abs(),
    ], axis=1).max(axis=1)

    avg1 = bp.rolling(p1).sum() / tr.rolling(p1).sum()
    avg2 = bp.rolling(p2).sum() / tr.rolling(p2).sum()
    avg3 = bp.rolling(p3).sum() / tr.rolling(p3).sum()

    df["UO"] = 100 * (4 * avg1 + 2 * avg2 + avg3) / 7
    return df


@register_indicator("AO")
def awesome_oscillator(df: pd.DataFrame) -> pd.DataFrame:
    median = (df["high"] + df["low"]) / 2
    df["AO"] = median.rolling(5).mean() - median.rolling(34).mean()
    return df


@register_indicator("PPO")
def ppo(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["PPO"] = ((ema_fast - ema_slow) / ema_slow) * 100
    df["PPO_signal"] = df["PPO"].ewm(span=signal, adjust=False).mean()
    df["PPO_hist"] = df["PPO"] - df["PPO_signal"]
    return df


@register_indicator("TRIX")
def trix(df: pd.DataFrame, period: int = 15) -> pd.DataFrame:
    ema1 = df["close"].ewm(span=period, adjust=False).mean()
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    ema3 = ema2.ewm(span=period, adjust=False).mean()
    df[f"TRIX_{period}"] = ema3.pct_change() * 100
    return df


@register_indicator("CONNORSRSI")
def connors_rsi(df: pd.DataFrame, rsi_period: int = 3, streak_period: int = 2,
                pct_rank_period: int = 100) -> pd.DataFrame:
    # RSI of close
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1 / rsi_period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / rsi_period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_close = 100 - (100 / (1 + rs))

    # Streak calculation
    streak = pd.Series(0.0, index=df.index)
    for i in range(1, len(df)):
        if df["close"].iloc[i] > df["close"].iloc[i - 1]:
            streak.iloc[i] = max(streak.iloc[i - 1], 0) + 1
        elif df["close"].iloc[i] < df["close"].iloc[i - 1]:
            streak.iloc[i] = min(streak.iloc[i - 1], 0) - 1
        else:
            streak.iloc[i] = 0

    # RSI of streak
    streak_delta = streak.diff()
    streak_gain = streak_delta.where(streak_delta > 0, 0).ewm(alpha=1 / streak_period, adjust=False).mean()
    streak_loss = (-streak_delta.where(streak_delta < 0, 0)).ewm(alpha=1 / streak_period, adjust=False).mean()
    streak_rs = streak_gain / streak_loss.replace(0, np.nan)
    rsi_streak = 100 - (100 / (1 + streak_rs))

    # Percent rank of ROC(1)
    roc_1 = df["close"].pct_change() * 100
    pct_rank = roc_1.rolling(pct_rank_period).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100, raw=False
    )

    df["CRSI"] = (rsi_close + rsi_streak + pct_rank) / 3
    return df


@register_indicator("CMO")
def cmo(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    delta = df["close"].diff()
    sum_up = delta.where(delta > 0, 0).rolling(period).sum()
    sum_down = (-delta.where(delta < 0, 0)).rolling(period).sum()
    df[f"CMO_{period}"] = ((sum_up - sum_down) / (sum_up + sum_down)) * 100
    return df


@register_indicator("DPO")
def dpo(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    shift = period // 2 + 1
    sma = df["close"].rolling(period).mean()
    df[f"DPO_{period}"] = df["close"] - sma.shift(shift)
    return df


@register_indicator("KST")
def kst(df: pd.DataFrame) -> pd.DataFrame:
    roc1 = df["close"].pct_change(periods=10) * 100
    roc2 = df["close"].pct_change(periods=15) * 100
    roc3 = df["close"].pct_change(periods=20) * 100
    roc4 = df["close"].pct_change(periods=30) * 100

    smooth1 = roc1.rolling(10).mean()
    smooth2 = roc2.rolling(10).mean()
    smooth3 = roc3.rolling(10).mean()
    smooth4 = roc4.rolling(15).mean()

    df["KST"] = smooth1 * 1 + smooth2 * 2 + smooth3 * 3 + smooth4 * 4
    df["KST_signal"] = df["KST"].rolling(9).mean()
    return df


@register_indicator("TSI")
def tsi(df: pd.DataFrame, long: int = 25, short: int = 13, signal: int = 13) -> pd.DataFrame:
    price_change = df["close"].diff()
    double_smooth_pc = price_change.ewm(span=long, adjust=False).mean().ewm(span=short, adjust=False).mean()
    double_smooth_abs = price_change.abs().ewm(span=long, adjust=False).mean().ewm(span=short, adjust=False).mean()
    df["TSI"] = (double_smooth_pc / double_smooth_abs.replace(0, np.nan)) * 100
    df["TSI_signal"] = df["TSI"].ewm(span=signal, adjust=False).mean()
    return df


@register_indicator("FISHER")
def fisher_transform(df: pd.DataFrame, period: int = 9) -> pd.DataFrame:
    hl2 = (df["high"] + df["low"]) / 2
    highest = hl2.rolling(period).max()
    lowest = hl2.rolling(period).min()
    raw = 2 * ((hl2 - lowest) / (highest - lowest).replace(0, np.nan)) - 1
    raw = raw.clip(-0.999, 0.999)

    fisher = pd.Series(0.0, index=df.index)
    for i in range(1, len(df)):
        val = 0.5 * raw.iloc[i] + 0.5 * (fisher.iloc[i - 1] if not np.isnan(fisher.iloc[i - 1]) else 0.0)
        val = np.clip(val, -0.999, 0.999)
        fisher.iloc[i] = 0.5 * np.log((1 + val) / (1 - val))

    df[f"FISHER_{period}"] = fisher
    df[f"FISHER_signal_{period}"] = fisher.shift(1)
    return df


@register_indicator("ELDER_RAY")
def elder_ray(df: pd.DataFrame, period: int = 13) -> pd.DataFrame:
    ema = df["close"].ewm(span=period, adjust=False).mean()
    df[f"BULL_POWER_{period}"] = df["high"] - ema
    df[f"BEAR_POWER_{period}"] = df["low"] - ema
    return df


@register_indicator("RVGI")
def rvgi(df: pd.DataFrame, period: int = 10) -> pd.DataFrame:
    close_open = df["close"] - df["open"]
    high_low = df["high"] - df["low"]

    # Symmetric weighted moving average (weights: 1, 2, 2, 1)
    num = (close_open + 2 * close_open.shift(1) + 2 * close_open.shift(2) + close_open.shift(3)) / 6
    den = (high_low + 2 * high_low.shift(1) + 2 * high_low.shift(2) + high_low.shift(3)) / 6

    rvgi_val = num.rolling(period).mean() / den.rolling(period).mean().replace(0, np.nan)
    df[f"RVGI_{period}"] = rvgi_val

    # Signal: symmetric weighted MA of RVGI
    df[f"RVGI_signal_{period}"] = (
        rvgi_val + 2 * rvgi_val.shift(1) + 2 * rvgi_val.shift(2) + rvgi_val.shift(3)
    ) / 6
    return df


@register_indicator("SMI")
def smi(df: pd.DataFrame, k_period: int = 14, d_period: int = 3, smooth: int = 3) -> pd.DataFrame:
    highest = df["high"].rolling(k_period).max()
    lowest = df["low"].rolling(k_period).min()
    midpoint = (highest + lowest) / 2
    distance = df["close"] - midpoint
    hl_range = highest - lowest

    smooth_distance = distance.ewm(span=d_period, adjust=False).mean().ewm(span=smooth, adjust=False).mean()
    smooth_range = hl_range.ewm(span=d_period, adjust=False).mean().ewm(span=smooth, adjust=False).mean()

    df["SMI"] = (smooth_distance / (smooth_range / 2).replace(0, np.nan)) * 100
    df["SMI_signal"] = df["SMI"].ewm(span=d_period, adjust=False).mean()
    return df


@register_indicator("CHANDE_FORECAST")
def chande_forecast(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    forecast = df["close"].rolling(period).apply(
        lambda x: np.polyval(np.polyfit(np.arange(len(x)), x, 1), len(x)),
        raw=True,
    )
    df[f"CFO_{period}"] = ((df["close"] - forecast) / df["close"]) * 100
    return df


@register_indicator("STC")
def schaff_trend_cycle(df: pd.DataFrame, fast: int = 23, slow: int = 50,
                       cycle: int = 10, factor: float = 0.5) -> pd.DataFrame:
    macd_line = df["close"].ewm(span=fast, adjust=False).mean() - df["close"].ewm(span=slow, adjust=False).mean()

    # First stochastic of MACD
    lowest_macd = macd_line.rolling(cycle).min()
    highest_macd = macd_line.rolling(cycle).max()
    stoch1 = ((macd_line - lowest_macd) / (highest_macd - lowest_macd).replace(0, np.nan)) * 100

    # Smooth stoch1 with EMA-like factor
    pf = pd.Series(np.nan, index=df.index)
    for i in range(len(df)):
        if np.isnan(stoch1.iloc[i]):
            continue
        if np.isnan(pf.iloc[i - 1]) if i > 0 else True:
            pf.iloc[i] = stoch1.iloc[i]
        else:
            pf.iloc[i] = pf.iloc[i - 1] + factor * (stoch1.iloc[i] - pf.iloc[i - 1])

    # Second stochastic of smoothed values
    lowest_pf = pf.rolling(cycle).min()
    highest_pf = pf.rolling(cycle).max()
    stoch2 = ((pf - lowest_pf) / (highest_pf - lowest_pf).replace(0, np.nan)) * 100

    # Smooth stoch2
    stc = pd.Series(np.nan, index=df.index)
    for i in range(len(df)):
        if np.isnan(stoch2.iloc[i]):
            continue
        if np.isnan(stc.iloc[i - 1]) if i > 0 else True:
            stc.iloc[i] = stoch2.iloc[i]
        else:
            stc.iloc[i] = stc.iloc[i - 1] + factor * (stoch2.iloc[i] - stc.iloc[i - 1])

    df["STC"] = stc
    return df
