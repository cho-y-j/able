import pandas as pd
import numpy as np
from app.analysis.indicators.registry import register_indicator


@register_indicator("BB")
def bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0,
                    column: str = "close") -> pd.DataFrame:
    sma = df[column].rolling(period).mean()
    std = df[column].rolling(period).std()
    df[f"BB_upper_{period}"] = sma + std_dev * std
    df[f"BB_middle_{period}"] = sma
    df[f"BB_lower_{period}"] = sma - std_dev * std
    df[f"BB_width_{period}"] = (df[f"BB_upper_{period}"] - df[f"BB_lower_{period}"]) / sma
    df[f"BB_pctb_{period}"] = (df[column] - df[f"BB_lower_{period}"]) / (
        df[f"BB_upper_{period}"] - df[f"BB_lower_{period}"]
    )
    return df


@register_indicator("ATR")
def atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    df[f"ATR_{period}"] = tr.ewm(alpha=1 / period, adjust=False).mean()
    return df


@register_indicator("KC")
def keltner_channel(df: pd.DataFrame, ema_period: int = 20, atr_period: int = 10,
                    multiplier: float = 1.5) -> pd.DataFrame:
    ema_val = df["close"].ewm(span=ema_period, adjust=False).mean()
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    atr_val = tr.ewm(alpha=1 / atr_period, adjust=False).mean()
    df[f"KC_upper_{ema_period}"] = ema_val + multiplier * atr_val
    df[f"KC_middle_{ema_period}"] = ema_val
    df[f"KC_lower_{ema_period}"] = ema_val - multiplier * atr_val
    return df


@register_indicator("DC")
def donchian_channel(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    df[f"DC_upper_{period}"] = df["high"].rolling(period).max()
    df[f"DC_lower_{period}"] = df["low"].rolling(period).min()
    df[f"DC_middle_{period}"] = (df[f"DC_upper_{period}"] + df[f"DC_lower_{period}"]) / 2
    return df


@register_indicator("HVOL")
def historical_volatility(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.DataFrame:
    log_returns = np.log(df[column] / df[column].shift())
    df[f"HVOL_{period}"] = log_returns.rolling(period).std() * np.sqrt(252) * 100
    return df


@register_indicator("STDDEV")
def std_deviation(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.DataFrame:
    df[f"STDDEV_{period}"] = df[column].rolling(period).std()
    return df


@register_indicator("CHAIKIN_VOL")
def chaikin_volatility(df: pd.DataFrame, ema_period: int = 10,
                       roc_period: int = 10) -> pd.DataFrame:
    hl_diff = df["high"] - df["low"]
    ema_hl = hl_diff.ewm(span=ema_period, adjust=False).mean()
    df["CHAIKIN_VOL"] = ((ema_hl - ema_hl.shift(roc_period)) / ema_hl.shift(roc_period)) * 100
    return df


@register_indicator("ULCER")
def ulcer_index(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    rolling_max = df["close"].rolling(period).max()
    pct_drawdown = ((df["close"] - rolling_max) / rolling_max) * 100
    df[f"ULCER_{period}"] = np.sqrt((pct_drawdown ** 2).rolling(period).mean())
    return df


@register_indicator("NATR")
def natr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    atr_val = tr.ewm(alpha=1 / period, adjust=False).mean()
    df[f"NATR_{period}"] = (atr_val / df["close"]) * 100
    return df


@register_indicator("RVI")
def rvi(df: pd.DataFrame, period: int = 14, smoothing: int = 14) -> pd.DataFrame:
    std = df["close"].rolling(period).std()
    change = df["close"].diff()
    up_vol = pd.Series(np.where(change > 0, std, 0), index=df.index)
    down_vol = pd.Series(np.where(change <= 0, std, 0), index=df.index)
    up_avg = up_vol.ewm(span=smoothing, adjust=False).mean()
    down_avg = down_vol.ewm(span=smoothing, adjust=False).mean()
    df[f"RVI_{period}"] = (up_avg / (up_avg + down_avg)) * 100
    return df


@register_indicator("SQUEEZE")
def squeeze(df: pd.DataFrame, bb_period: int = 20, bb_mult: float = 2.0,
            kc_period: int = 20, kc_mult: float = 1.5) -> pd.DataFrame:
    # Bollinger Bands
    bb_sma = df["close"].rolling(bb_period).mean()
    bb_std = df["close"].rolling(bb_period).std()
    bb_upper = bb_sma + bb_mult * bb_std
    bb_lower = bb_sma - bb_mult * bb_std

    # Keltner Channel
    kc_ema = df["close"].ewm(span=kc_period, adjust=False).mean()
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    kc_atr = tr.ewm(alpha=1 / kc_period, adjust=False).mean()
    kc_upper = kc_ema + kc_mult * kc_atr
    kc_lower = kc_ema - kc_mult * kc_atr

    # Squeeze on when BB is inside KC
    df["SQUEEZE_on"] = ((bb_lower > kc_lower) & (bb_upper < kc_upper)).astype(int)

    # Momentum: close - midline of Donchian Channel
    dc_high = df["high"].rolling(kc_period).max()
    dc_low = df["low"].rolling(kc_period).min()
    dc_mid = (dc_high + dc_low) / 2
    df["SQUEEZE_val"] = df["close"] - dc_mid
    return df


@register_indicator("TR")
def true_range(df: pd.DataFrame) -> pd.DataFrame:
    df["TR"] = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return df


@register_indicator("YANG_ZHANG")
def yang_zhang(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    log_oc = np.log(df["open"] / df["close"].shift())
    log_co = np.log(df["close"] / df["open"])
    log_ho = np.log(df["high"] / df["open"])
    log_lo = np.log(df["low"] / df["open"])
    log_hc = np.log(df["high"] / df["close"])
    log_lc = np.log(df["low"] / df["close"])

    # Overnight volatility
    overnight_var = log_oc.rolling(period).var()

    # Open-to-close volatility
    oc_var = log_co.rolling(period).var()

    # Rogers-Satchell volatility
    rs = log_ho * log_hc + log_lo * log_lc
    rs_var = rs.rolling(period).mean()

    k = 0.34 / (1.34 + (period + 1) / (period - 1))
    df[f"YZ_VOL_{period}"] = np.sqrt(overnight_var + k * oc_var + (1 - k) * rs_var) * np.sqrt(252) * 100
    return df


@register_indicator("GARMAN_KLASS")
def garman_klass(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    log_hl = np.log(df["high"] / df["low"])
    log_co = np.log(df["close"] / df["open"])
    gk = 0.5 * log_hl ** 2 - (2 * np.log(2) - 1) * log_co ** 2
    df[f"GK_VOL_{period}"] = np.sqrt(gk.rolling(period).mean()) * np.sqrt(252) * 100
    return df
