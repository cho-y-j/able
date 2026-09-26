#!/usr/bin/env python3
"""L-0001 증거 재현 스크립트 — 백테스트 엔진의 룩어헤드·비용 미반영 실측.

목적: 알파가 존재할 수 없는 순수 랜덤워크 데이터를 현재 엔진에 넣고,
      보고되는 성과가 진짜인지 확인한다.

기대 결과(수정 전): 엔진이 Sharpe 10 이상, MDD 0.00% 를 보고한다 → 결함 증거
기대 결과(수정 후): |Sharpe| < 0.5, MDD < 0 → 정상

실행:
    cd backend && .venv/bin/python ../docs/research/scripts/proof_lookahead.py

근거: docs/research/LEDGER.md L-0001, docs/research/QUEUE.md Q-001
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# backend/ 를 import 경로에 추가 (저장소 어디서 실행해도 동작)
_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "backend"))

from app.analysis.backtest.engine import run_backtest  # noqa: E402

SEED = 7
N_BARS = 1000
DAILY_VOL = 0.02  # 코스닥 중소형주 수준


def make_random_walk(seed: int = SEED, n: int = N_BARS, vol: float = DAILY_VOL) -> pd.DataFrame:
    """드리프트 0의 기하 브라운 운동. 알파가 존재할 수 없는 데이터."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0, vol, n)
    close = 10_000 * np.exp(np.cumsum(rets))
    idx = pd.date_range("2022-01-03", periods=n, freq="B")
    return pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close, "volume": 1e6},
        index=idx,
    )


def true_sharpe_with_shift(df: pd.DataFrame, entry: pd.Series) -> tuple[float, float]:
    """룩어헤드를 제거한(1봉 시프트) 진짜 Sharpe와 총수익."""
    pos = entry.astype(float).shift(1).fillna(0.0).to_numpy()
    rets = df["close"].pct_change().fillna(0.0).to_numpy()
    sr = pd.Series(pos * rets)
    sharpe = float(sr.mean() / sr.std() * np.sqrt(252)) if sr.std() > 0 else 0.0
    total = float((1 + sr).cumprod().iloc[-1] - 1)
    return sharpe, total


def main() -> int:
    df = make_random_walk()

    # 전략 A: 당일 상승봉이면 보유. 미래 정보를 쓰지 않으므로 기대수익은 0이어야 한다.
    up = df["close"].pct_change().fillna(0) > 0
    res = run_backtest(df, up, ~up)
    fixed_sharpe, fixed_total = true_sharpe_with_shift(df, up)
    trade_avg = float(np.mean([t["pnl_percent"] for t in res.trade_log])) if res.trade_log else 0.0

    print("=" * 72)
    print("L-0001 재현: 랜덤워크(알파 0) + 당일봉 방향 신호")
    print("=" * 72)
    print(f"  엔진 보고   연수익 {res.annual_return:>10.2f}%  Sharpe {res.sharpe_ratio:>7.2f}"
          f"  MDD {res.max_drawdown:>7.2f}%  거래 {res.total_trades}회")
    print(f"  거래로그    평균손익 {trade_avg:>8.4f}%  (비용이 반영된 유일한 숫자)")
    print(f"  시프트 수정 총수익 {fixed_total * 100:>10.2f}%  Sharpe {fixed_sharpe:>7.2f}  <- 진짜 값")

    # 비용 정합성: equity 곡선과 거래로그가 같은 결론을 내는가
    print("\n비용 정합성")
    print(f"  거래 {res.total_trades}회 × 모델 왕복비용 0.23% = {res.total_trades * 0.23:.1f}% 비용 발생해야 함")
    print(f"  equity 기반 총수익 {res.total_return:.2f}%")
    equity_sign = "양수" if res.total_return > 0 else "음수"
    trade_sign = "양수" if trade_avg > 0 else "음수"
    consistent = (res.total_return > 0) == (trade_avg > 0)
    print(f"  equity {equity_sign} vs 거래로그 {trade_sign} → 부호 일치: {'예' if consistent else '아니오 (결함)'}")

    # 판정
    print("\n" + "=" * 72)
    defects = []
    if abs(res.sharpe_ratio) >= 0.5:
        defects.append(f"룩어헤드: 알파 0 데이터에서 Sharpe {res.sharpe_ratio:.2f} (기준 |0.5| 미만)")
    if res.max_drawdown == 0.0 and res.total_trades > 0:
        defects.append("MDD 0.00%: 거래가 있는데 낙폭이 0 — 계산 오류")
    if not consistent:
        defects.append("비용 정합성: equity 곡선과 거래로그의 부호 불일치")

    if defects:
        print("판정: 결함 확인 (L-0001 증거 재현됨)")
        for d in defects:
            print(f"  - {d}")
        return 1
    print("판정: 결함 없음 — 엔진이 수정되었다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
