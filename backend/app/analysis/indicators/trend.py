import pandas as pd
import numpy as np
from app.analysis.indicators.registry import register_indicator


@register_indicator("SMA")
def sma(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.DataFrame:
    df[f"SMA_{period}"] = df[column].rolling(window=period).mean()
    return df


@register_indicator("EMA")
def ema(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.DataFrame:
    df[f"EMA_{period}"] = df[column].ewm(span=period, adjust=False).mean()
    return df


@register_indicator("DEMA")
def dema(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.DataFrame:
    ema1 = df[column].ewm(span=period, adjust=False).mean()
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    df[f"DEMA_{period}"] = 2 * ema1 - ema2
    return df


@register_indicator("TEMA")
def tema(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.DataFrame:
    ema1 = df[column].ewm(span=period, adjust=False).mean()
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    ema3 = ema2.ewm(span=period, adjust=False).mean()
    df[f"TEMA_{period}"] = 3 * ema1 - 3 * ema2 + ema3
    return df


@register_indicator("WMA")
def wma(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.DataFrame:
    weights = np.arange(1, period + 1)
    df[f"WMA_{period}"] = df[column].rolling(window=period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )
    return df


@register_indicator("MACD")
def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9,
         column: str = "close") -> pd.DataFrame:
    ema_fast = df[column].ewm(span=fast, adjust=False).mean()
    ema_slow = df[column].ewm(span=slow, adjust=False).mean()
    df[f"MACD_{fast}_{slow}_{signal}"] = ema_fast - ema_slow
    df[f"MACD_signal_{fast}_{slow}_{signal}"] = df[f"MACD_{fast}_{slow}_{signal}"].ewm(
        span=signal, adjust=False
    ).mean()
    df[f"MACD_hist_{fast}_{slow}_{signal}"] = (
        df[f"MACD_{fast}_{slow}_{signal}"] - df[f"MACD_signal_{fast}_{slow}_{signal}"]
    )
    return df


@register_indicator("ADX")
def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high, low, close = df["high"], df["low"], df["close"]
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))

    df[f"ADX_{period}"] = dx.ewm(alpha=1 / period, adjust=False).mean()
    df[f"+DI_{period}"] = plus_di
    df[f"-DI_{period}"] = minus_di
    return df


@register_indicator("PSAR")
def parabolic_sar(df: pd.DataFrame, af_start: float = 0.02, af_max: float = 0.2) -> pd.DataFrame:
    high, low, close = df["high"].values, df["low"].values, df["close"].values
    n = len(df)
    sar = np.zeros(n)
    trend = np.ones(n)
    af = af_start
    ep = low[0]
    sar[0] = high[0]

    for i in range(1, n):
        if trend[i - 1] == 1:  # Uptrend
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
            sar[i] = min(sar[i], low[i - 1], low[max(0, i - 2)])
            if low[i] < sar[i]:
                trend[i] = -1
                sar[i] = ep
                ep = low[i]
                af = af_start
            else:
                trend[i] = 1
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + af_start, af_max)
        else:  # Downtrend
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
            sar[i] = max(sar[i], high[i - 1], high[max(0, i - 2)])
            if high[i] > sar[i]:
                trend[i] = 1
                sar[i] = ep
                ep = high[i]
                af = af_start
            else:
                trend[i] = -1
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + af_start, af_max)

    df["PSAR"] = sar
    df["PSAR_trend"] = trend
    return df


@register_indicator("SUPERTREND")
def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    hl2 = (df["high"] + df["low"]) / 2
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr

    supertrend_val = pd.Series(np.nan, index=df.index)
    direction = pd.Series(1, index=df.index)

    for i in range(period, len(df)):
        if df["close"].iloc[i] > upper.iloc[i - 1]:
            direction.iloc[i] = 1
        elif df["close"].iloc[i] < lower.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]

        if direction.iloc[i] == 1:
            supertrend_val.iloc[i] = lower.iloc[i]
        else:
            supertrend_val.iloc[i] = upper.iloc[i]

    df[f"SUPERTREND_{period}"] = supertrend_val
    df[f"SUPERTREND_dir_{period}"] = direction
    return df


@register_indicator("ICHIMOKU")
def ichimoku(df: pd.DataFrame, tenkan: int = 9, kijun: int = 26, senkou_b: int = 52) -> pd.DataFrame:
    high, low = df["high"], df["low"]
    df["ICHI_tenkan"] = (high.rolling(tenkan).max() + low.rolling(tenkan).min()) / 2
    df["ICHI_kijun"] = (high.rolling(kijun).max() + low.rolling(kijun).min()) / 2
    df["ICHI_senkou_a"] = ((df["ICHI_tenkan"] + df["ICHI_kijun"]) / 2).shift(kijun)
    df["ICHI_senkou_b"] = ((high.rolling(senkou_b).max() + low.rolling(senkou_b).min()) / 2).shift(kijun)
    df["ICHI_chikou"] = df["close"].shift(-kijun)
    return df


@register_indicator("HULL")
def hull_ma(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.DataFrame:
    half_period = int(period / 2)
    sqrt_period = int(np.sqrt(period))
    weights_half = np.arange(1, half_period + 1)
    weights_full = np.arange(1, period + 1)
    weights_sqrt = np.arange(1, sqrt_period + 1)

    wma_half = df[column].rolling(window=half_period).apply(
        lambda x: np.dot(x, weights_half) / weights_half.sum(), raw=True
    )
    wma_full = df[column].rolling(window=period).apply(
        lambda x: np.dot(x, weights_full) / weights_full.sum(), raw=True
    )
    hull_series = 2 * wma_half - wma_full
    df[f"HMA_{period}"] = hull_series.rolling(window=sqrt_period).apply(
        lambda x: np.dot(x, weights_sqrt) / weights_sqrt.sum(), raw=True
    )
    return df


@register_indicator("VWMA")
def vwma(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    cv = df["close"] * df["volume"]
    df[f"VWMA_{period}"] = cv.rolling(window=period).sum() / df["volume"].rolling(window=period).sum()
    return df


@register_indicator("KAMA")
def kama(df: pd.DataFrame, period: int = 10, fast: int = 2, slow: int = 30) -> pd.DataFrame:
    close = df["close"]
    direction = (close - close.shift(period)).abs()
    volatility = close.diff().abs().rolling(window=period).sum()
    er = direction / volatility.replace(0, np.nan)

    fast_sc = 2.0 / (fast + 1.0)
    slow_sc = 2.0 / (slow + 1.0)
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

    kama_values = np.full(len(close), np.nan)
    first_valid = period
    while first_valid < len(close) and np.isnan(close.iloc[first_valid]):
        first_valid += 1
    if first_valid < len(close):
        kama_values[first_valid] = close.iloc[first_valid]
        for i in range(first_valid + 1, len(close)):
            sc_val = sc.iloc[i] if not np.isnan(sc.iloc[i]) else 0
            kama_values[i] = kama_values[i - 1] + sc_val * (close.iloc[i] - kama_values[i - 1])

    df[f"KAMA_{period}"] = kama_values
    return df


@register_indicator("T3")
def t3(df: pd.DataFrame, period: int = 5, v_factor: float = 0.7) -> pd.DataFrame:
    close = df["close"]
    ema1 = close.ewm(span=period, adjust=False).mean()
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    ema3 = ema2.ewm(span=period, adjust=False).mean()
    ema4 = ema3.ewm(span=period, adjust=False).mean()
    ema5 = ema4.ewm(span=period, adjust=False).mean()
    ema6 = ema5.ewm(span=period, adjust=False).mean()

    c1 = -(v_factor ** 3)
    c2 = 3 * v_factor ** 2 + 3 * v_factor ** 3
    c3 = -6 * v_factor ** 2 - 3 * v_factor - 3 * v_factor ** 3
    c4 = 1 + 3 * v_factor + v_factor ** 3 + 3 * v_factor ** 2

    df[f"T3_{period}"] = c1 * ema6 + c2 * ema5 + c3 * ema4 + c4 * ema3
    return df


@register_indicator("ZLEMA")
def zlema(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.DataFrame:
    lag = int((period - 1) / 2)
    ema_input = 2 * df[column] - df[column].shift(lag)
    df[f"ZLEMA_{period}"] = ema_input.ewm(span=period, adjust=False).mean()
    return df


@register_indicator("COPPOCK")
def coppock(df: pd.DataFrame, roc1: int = 14, roc2: int = 11, wma_period: int = 10) -> pd.DataFrame:
    close = df["close"]
    roc_long = close.pct_change(periods=roc1) * 100
    roc_short = close.pct_change(periods=roc2) * 100
    roc_sum = roc_long + roc_short

    weights = np.arange(1, wma_period + 1)
    df["COPPOCK"] = roc_sum.rolling(window=wma_period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )
    return df


@register_indicator("AROON")
def aroon(df: pd.DataFrame, period: int = 25) -> pd.DataFrame:
    high, low = df["high"], df["low"]

    aroon_up = high.rolling(window=period + 1).apply(
        lambda x: ((period - (period - np.argmax(x))) / period) * 100, raw=True
    )
    aroon_down = low.rolling(window=period + 1).apply(
        lambda x: ((period - (period - np.argmin(x))) / period) * 100, raw=True
    )

    df[f"AROON_up_{period}"] = aroon_up
    df[f"AROON_down_{period}"] = aroon_down
    df[f"AROON_osc_{period}"] = aroon_up - aroon_down
    return df


@register_indicator("VORTEX")
def vortex(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high, low, close = df["high"], df["low"], df["close"]

    vm_plus = (high - low.shift(1)).abs()
    vm_minus = (low - high.shift(1)).abs()

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    vm_plus_sum = vm_plus.rolling(window=period).sum()
    vm_minus_sum = vm_minus.rolling(window=period).sum()
    tr_sum = tr.rolling(window=period).sum()

    df[f"VI_plus_{period}"] = vm_plus_sum / tr_sum
    df[f"VI_minus_{period}"] = vm_minus_sum / tr_sum
    return df


@register_indicator("MASS_IDX")
def mass_index(df: pd.DataFrame, fast: int = 9, slow: int = 25) -> pd.DataFrame:
    high_low = df["high"] - df["low"]
    ema1 = high_low.ewm(span=fast, adjust=False).mean()
    ema2 = ema1.ewm(span=fast, adjust=False).mean()
    ratio = ema1 / ema2
    df["MASS_IDX"] = ratio.rolling(window=slow).sum()
    return df


@register_indicator("LINREG")
def linear_regression(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.DataFrame:
    values = df[column]

    def _linreg(window):
        y = np.array(window)
        x = np.arange(len(y))
        n = len(y)
        sum_x = x.sum()
        sum_y = y.sum()
        sum_xy = (x * y).sum()
        sum_x2 = (x ** 2).sum()
        sum_y2 = (y ** 2).sum()

        denom = n * sum_x2 - sum_x ** 2
        if denom == 0:
            return np.nan
        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        linreg_value = intercept + slope * (n - 1)
        return linreg_value

    def _slope(window):
        y = np.array(window)
        x = np.arange(len(y))
        n = len(y)
        sum_x = x.sum()
        sum_y = y.sum()
        sum_xy = (x * y).sum()
        sum_x2 = (x ** 2).sum()
        denom = n * sum_x2 - sum_x ** 2
        if denom == 0:
            return np.nan
        return (n * sum_xy - sum_x * sum_y) / denom

    def _r_squared(window):
        y = np.array(window)
        x = np.arange(len(y))
        n = len(y)
        sum_x = x.sum()
        sum_y = y.sum()
        sum_xy = (x * y).sum()
        sum_x2 = (x ** 2).sum()
        sum_y2 = (y ** 2).sum()

        denom = n * sum_x2 - sum_x ** 2
        denom_y = n * sum_y2 - sum_y ** 2
        if denom == 0 or denom_y == 0:
            return np.nan
        r = (n * sum_xy - sum_x * sum_y) / np.sqrt(denom * denom_y)
        return r ** 2

    df[f"LINREG_{period}"] = values.rolling(window=period).apply(_linreg, raw=True)
    df[f"LINREG_slope_{period}"] = values.rolling(window=period).apply(_slope, raw=True)
    df[f"LINREG_r2_{period}"] = values.rolling(window=period).apply(_r_squared, raw=True)
    return df
