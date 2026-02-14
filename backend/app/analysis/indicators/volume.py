import pandas as pd
import numpy as np
from app.analysis.indicators.registry import register_indicator


@register_indicator("OBV")
def obv(df: pd.DataFrame) -> pd.DataFrame:
    direction = np.sign(df["close"].diff())
    df["OBV"] = (direction * df["volume"]).cumsum()
    return df


@register_indicator("VWAP")
def vwap(df: pd.DataFrame) -> pd.DataFrame:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    cum_tp_vol = (tp * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum()
    df["VWAP"] = cum_tp_vol / cum_vol
    return df


@register_indicator("CMF")
def chaikin_money_flow(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    mf_multiplier = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / (df["high"] - df["low"])
    mf_multiplier = mf_multiplier.fillna(0)
    mf_volume = mf_multiplier * df["volume"]
    df[f"CMF_{period}"] = mf_volume.rolling(period).sum() / df["volume"].rolling(period).sum()
    return df


@register_indicator("AD")
def accumulation_distribution(df: pd.DataFrame) -> pd.DataFrame:
    mf_multiplier = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / (df["high"] - df["low"])
    mf_multiplier = mf_multiplier.fillna(0)
    df["AD"] = (mf_multiplier * df["volume"]).cumsum()
    return df


@register_indicator("VOLSMA")
def volume_sma(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    df[f"VOL_SMA_{period}"] = df["volume"].rolling(period).mean()
    return df


@register_indicator("FI")
def force_index(df: pd.DataFrame, period: int = 13) -> pd.DataFrame:
    fi = df["close"].diff() * df["volume"]
    df[f"FI_{period}"] = fi.ewm(span=period, adjust=False).mean()
    return df


@register_indicator("EOM")
def ease_of_movement(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    mid = (df["high"] + df["low"]) / 2
    mid_diff = mid.diff()
    box_ratio = (df["volume"] / (df["high"] - df["low"])).replace([np.inf, -np.inf], np.nan)
    eom = (mid_diff / box_ratio).replace([np.inf, -np.inf], np.nan)
    df[f"EOM_{period}"] = eom.rolling(period).mean()
    return df


@register_indicator("VROC")
def vroc(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    prev_vol = df["volume"].shift(period)
    df[f"VROC_{period}"] = ((df["volume"] - prev_vol) / prev_vol) * 100
    return df


@register_indicator("KLINGER")
def klinger(df: pd.DataFrame, fast: int = 34, slow: int = 55, signal: int = 13) -> pd.DataFrame:
    hlc = df["high"] + df["low"] + df["close"]
    prev_hlc = hlc.shift(1)
    trend = np.where(hlc > prev_hlc, 1, -1).astype(float)
    dm = df["high"] - df["low"]
    cm = pd.Series(np.nan, index=df.index, dtype=float)
    cm.iloc[0] = dm.iloc[0]
    for i in range(1, len(df)):
        if trend[i] == trend[i - 1]:
            cm.iloc[i] = cm.iloc[i - 1] + dm.iloc[i]
        else:
            cm.iloc[i] = dm.iloc[i]
    cm = cm.replace(0, np.nan)
    vf = df["volume"] * abs(2 * dm / cm - 1) * trend
    vf = vf.replace([np.inf, -np.inf], np.nan).fillna(0)
    kvo = vf.ewm(span=fast, adjust=False).mean() - vf.ewm(span=slow, adjust=False).mean()
    df["KVO"] = kvo
    df["KVO_signal"] = kvo.ewm(span=signal, adjust=False).mean()
    return df


@register_indicator("NVI")
def nvi(df: pd.DataFrame) -> pd.DataFrame:
    price_change_pct = df["close"].pct_change()
    vol_decrease = df["volume"] < df["volume"].shift(1)
    nvi_series = pd.Series(0.0, index=df.index)
    nvi_series.iloc[0] = 1000.0
    for i in range(1, len(df)):
        if vol_decrease.iloc[i]:
            nvi_series.iloc[i] = nvi_series.iloc[i - 1] * (1 + price_change_pct.iloc[i])
        else:
            nvi_series.iloc[i] = nvi_series.iloc[i - 1]
    df["NVI"] = nvi_series
    return df


@register_indicator("PVI")
def pvi(df: pd.DataFrame) -> pd.DataFrame:
    price_change_pct = df["close"].pct_change()
    vol_increase = df["volume"] > df["volume"].shift(1)
    pvi_series = pd.Series(0.0, index=df.index)
    pvi_series.iloc[0] = 1000.0
    for i in range(1, len(df)):
        if vol_increase.iloc[i]:
            pvi_series.iloc[i] = pvi_series.iloc[i - 1] * (1 + price_change_pct.iloc[i])
        else:
            pvi_series.iloc[i] = pvi_series.iloc[i - 1]
    df["PVI"] = pvi_series
    return df


@register_indicator("ADOSC")
def ad_oscillator(df: pd.DataFrame, fast: int = 3, slow: int = 10) -> pd.DataFrame:
    mf_multiplier = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / (df["high"] - df["low"])
    mf_multiplier = mf_multiplier.fillna(0)
    ad = (mf_multiplier * df["volume"]).cumsum()
    df["ADOSC"] = ad.ewm(span=fast, adjust=False).mean() - ad.ewm(span=slow, adjust=False).mean()
    return df


@register_indicator("EMV")
def emv(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    mid_diff = ((df["high"] + df["low"]) / 2).diff()
    box_ratio = ((df["volume"] / 10000) / (df["high"] - df["low"])).replace([np.inf, -np.inf], np.nan)
    emv_raw = (mid_diff / box_ratio).replace([np.inf, -np.inf], np.nan)
    df[f"EMV_{period}"] = emv_raw.rolling(period).mean()
    return df


@register_indicator("VOSC")
def volume_oscillator(df: pd.DataFrame, fast: int = 12, slow: int = 26) -> pd.DataFrame:
    vol_ema_fast = df["volume"].ewm(span=fast, adjust=False).mean()
    vol_ema_slow = df["volume"].ewm(span=slow, adjust=False).mean()
    df["VOSC"] = ((vol_ema_fast - vol_ema_slow) / vol_ema_slow) * 100
    return df
