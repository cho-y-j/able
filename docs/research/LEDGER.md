# ABLE 작업 원장 (LEDGER)

> **이 파일의 목적**: 중복 작업 방지와 세션 간 재개.
> 작업 **시작 전에 반드시 읽고**, 작업 **후에 반드시 추가**한다.
> 기록되지 않은 작업은 없었던 작업으로 취급되며 다음 세션이 중복 착수한다.

## 규칙

1. **추가만 한다.** 과거 항목을 삭제하거나 고치지 않는다.
   판정이 뒤집히면 새 항목을 추가하고 `대체` 필드로 이전 ID를 가리킨다.
2. `상태`는 `CLAUDE.md` 1.3절의 다섯 개만 쓴다: `미착수` `구현됨` `검증됨` `반증됨` `폐기`
3. **구현자는 `검증됨`을 쓸 수 없다.** 독립 검수 보고가 있을 때만 부여한다.
4. `증거` 필드는 비울 수 없다. 없으면 `증거없음`이라고 명시한다 — 그 자체가 정보다.
5. 최신 항목을 **맨 위에** 추가한다 (역순). 재개 시 위에서부터 읽으면 된다.

## 항목 스키마

```
### [L-NNNN] 제목
- 날짜:
- 담당: <에이전트 이름 또는 main>
- 상태: <다섯 개 중 하나>
- 대상 파일: <경로:행>
- 한 일:
- 증거: <명령 + 실제 출력 / 또는 "증거없음">
- 검수: <검수자 / 판정 / 검수 보고 요약> 또는 "미검수"
- 남은 범위:
- 다음 작업: <QUEUE.md 항목 ID 또는 서술>
- 대체: <이전 항목 ID 또는 "없음">
```

---

## 진행 중 / 차단

| ID | 제목 | 상태 | 차단 요인 |
|----|------|------|-----------|
| — | (없음) | — | — |

---

## 기록 (최신순)

### [L-0003] L-0001 증거 재현 스크립트를 저장소로 이전 + 실행 확인
- 날짜: 2026-09-27
- 담당: main
- 상태: 구현됨
- 대상 파일: `docs/research/scripts/proof_lookahead.py`
- 한 일: 세션 스크래치패드에 있던 증명 스크립트를 저장소로 이전. 판정 로직 추가(결함 시 exit 1)
- 증거:
  - 명령: `cd backend && .venv/bin/python ../docs/research/scripts/proof_lookahead.py`
  - 출력(실제): `엔진 보고 연수익 443.21%  Sharpe 9.99  MDD 0.00%  거래 251회`
    / `거래로그 평균손익 -0.3969%` / `시프트 수정 총수익 -39.38%  Sharpe -0.51`
    / `equity 기반 총수익 82413.65%` / `부호 일치: 아니오 (결함)`
  - `exit code: 1` (결함 확인)
- **L-0001과의 수치 차이 (은폐하지 않고 기록)**:
  - L-0001은 `np.random.seed(7)` (레거시 RNG), L-0003은 `np.random.default_rng(7)` 사용 →
    난수열이 달라 수치가 다르다. L-0001 `Sharpe 10.74` vs L-0003 `Sharpe 9.99`.
  - 결론은 동일: 알파 0 데이터에서 엔진이 Sharpe 10 내외, MDD 0.00% 를 보고한다.
  - **새로 발견된 사실**: 이 시드에서 시프트 수정 후 진짜 Sharpe가 `-0.51`로 `|0.5|` 경계를 넘었다.
    단일 시드 회귀 테스트는 불안정하다. → Q-001에 다중 시드 요구사항 추가함.
- 검수: 미검수 (Q-002에서 독립 재현 예정)
- 남은 범위: CI 연결 안 됨. pytest 회귀 테스트로의 전환은 Q-001 범위
- 다음 작업: Q-002 → Q-001
- 대체: 없음

### [L-0002] 작업 표준·에이전트 역할 분리·기록 체계 구축
- 날짜: 2026-09-27
- 담당: main
- 상태: 구현됨
- 대상 파일: `CLAUDE.md`, `.claude/agents/{quant-builder,quant-reviewer,ux-designer,design-reviewer}.md`, `docs/research/{LEDGER,QUEUE,DECISIONS}.md`
- 한 일:
  - 과장·추정 보고 금지 규칙과 증거 규칙을 `CLAUDE.md`에 계약으로 명문화
  - 상태 어휘 5개 도입 (`완료` 사용 금지 — 구현과 검증을 분리)
  - 에이전트 4개 정의. 검수자 2종은 `tools`에서 `Edit`/`Write` 제외
  - 검수 무결성 확인 절차 도입: 검수 전후 `git status --porcelain` 비교
  - 원장·대기열·결정기록 3파일 신설
- 증거:
  - `ls -1 .claude/agents/` → `design-reviewer.md  quant-builder.md  quant-reviewer.md  ux-designer.md`
  - `wc -l CLAUDE.md` → `156`
  - frontmatter 확인: `quant-reviewer` / `design-reviewer` 의 `tools: Read, Bash, Grep, Glob` (쓰기 도구 없음)
- 검수: 미검수 — 문서·설정 변경이며 실행 가능한 동작이 없음. 첫 실사용(L-0003)에서 실효성이 검증된다.
- 남은 범위:
  - 자동화 스케줄 미설정
  - 기존 `WORK_LOG.md`의 과거 `✅ 완료` 항목을 `구현됨`으로 재분류하지 않음 (헤더 주의문으로 대체)
- 다음 작업: Q-001
- 대체: 없음

### [L-0001] 백테스트·검증·패턴 발굴 계층 감사
- 날짜: 2026-09-26
- 담당: main
- 상태: 검증됨 (측정으로 재현 가능)
- 대상 파일: `backend/app/analysis/backtest/engine.py`, `backend/app/analysis/validation/*.py`, `backend/app/services/pattern_discovery.py`
- 한 일: 코드 감사 + 랜덤워크 실측으로 결함 11건 확인
- 증거:
  - 순수 랜덤워크(드리프트 0, 일변동성 2%, n=1000) + 당일봉 방향 신호 →
    현재 엔진 보고 `연수익 547.39% / Sharpe 10.74 / MDD 0.00% / 거래 252회`
    동일 실행의 거래로그 평균손익 `-0.1538%`
    `position.shift(1)` 적용 시 `Sharpe 0.24`
  - 원인: `engine.py:74` `strategy_returns = position * daily_returns` (1봉 룩어헤드)
  - 비용 미반영: `engine.py:73-85` — equity 곡선이 비용 없는 `daily_returns`에서 파생
  - 죽은 변수: `validation/walk_forward.py:32` `train`, `validation/out_of_sample.py:144` `train_data`
  - 이름/동작 불일치: `out_of_sample.py:144` (purge 미적용), `pattern_discovery.py:227` (전체 표본 중위값)
  - 방향 하드코딩: `pattern_discovery.py:234` `">="`
  - 체결 불가 라벨: `pattern_discovery.py:50` `future_max`
  - 세금 부재: `grep -rn "거래세\|transaction_tax" backend/app/analysis` → 결과 없음
  - 스텁 확인: `tasks/periodic_tasks.py:940`, `api/v1/patterns.py:110`
  - 재현 스크립트: `docs/research/scripts/proof_lookahead.py` (L-0003에서 저장소로 이전 예정)
- 검수: 미검수 — 자체 측정. 독립 재현 필요 (Q-002)
- 남은 범위: 수정 작업 미착수. 감사만 수행
- 다음 작업: Q-001, Q-002
- 대체: 없음
