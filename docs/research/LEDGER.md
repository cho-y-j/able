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
| L-0015 | Q-020b 개인 순매수 복구 | 구현됨 | flow 모듈 프로덕션 미배선 발견 |
| L-0014 | 경쟁 지형 조사 | 구현됨 | 11축 중 10축 열위 확인 |
| L-0013 | 라벨·CV 명세 | 구현됨 | 신규 치명 결함 1건(행 정렬) |
| L-0011 | **독립 검수 반증됨** | 반증됨 | **병합 차단** — 결함 11건 수정 필요 |
| L-0012 | instrument 설계 명세 | 구현됨 | 미해결 질문 10건 |
| L-0009 | 절차 위반 기록 | 구현됨 | 검수 완료(L-0011) |
| L-0008 | .env 규칙 개정 + 유출 차단 | 검증됨 | 루틴 프롬프트 갱신 필요 |
| L-0007 | 루틴 프롬프트 v2 | 구현됨 | 첫 실행 결과 대기 |
| L-0006 | 에이전트 로드 제약 | 구현됨 | 루틴 첫 실행까지 클라우드 로드 여부 미검증 |
| L-0005 | CI 정상화 | 구현됨 | 통합 8건 수정 중 (구현 에이전트 작업) |
| L-0004 | 일일 자동 루틴 | 구현됨 | **PR #1 병합 대기** — 병합 전까지 루틴은 매일 중단만 보고 |
| Q-002 | L-0001 독립 재현 | 미착수 | 없음 (루틴 첫 착수 예정) |

---

## 기록 (최신순)

### [L-0015] Q-020b 개인 순매수 복구 — 범위 밖에서 더 큰 문제 발견
- 날짜: 2026-09-27
- 담당: 구현 에이전트(`general-purpose`, quant-builder 지시 인라이닝) / 기록·검증: main
- 상태: 구현됨
- 대상 파일: `backend/app/analysis/signals/flow_signals.py`, `backend/tests/unit/test_flow_signals.py`
- 한 일: `individual_qty` 죽은 변수 복구 + 3주체 대립 팩터 신설. 팩터 7개 추가
  (`individual_net_buy_qty/_ratio`, `smart_money_net_buy_qty/_ratio`,
   `flow_opposition_qty/_ratio/_score`)
- **범위 밖 발견 (더 심각) — 내가 직접 재확인함**:
  **`flow_signals.py` 는 프로덕션에서 한 번도 호출되지 않는다.**
  - `grep -rn "extract_flow_factors|compute_foreign_3day_trend" backend/app/` →
    **정의 2건(`:21`, `:85`)만 나오고 호출부 0건**
  - `grep -n "flow|foreign|net_buy" backend/app/analysis/signals/registry.py` → **출력 없음**
  - 유일한 호출부는 `backend/tests/unit/test_flow_signals.py` (32건)
  → ADR-0017 이 "1급 알파 모듈" 이라 부른 파일은 **배선되지 않은 상태**다.
    개인 순매수를 버리는 것보다 이것이 더 큰 문제다. **배선은 Q-020 본체 범위이므로 손대지 않음 → Q-020c 신설**
- **KIS 데이터 제약 (내가 직접 확인)**: `client.py:348-361` 이 반환하는 것은
  `foreign_net_buy_amt`, `institutional_net_buy_amt` 뿐이며 **`individual_net_buy_amt` 가 없다.**
  따라서 개인 순매수의 거래대금 정규화는 KIS 호출부 변경 없이 불가능하다 → Q-020d 신설
- **에이전트가 스스로 보고한 한계 (은폐 없음)**:
  한국 거래소 수급은 `개인+외국인+기관+기타법인 ≈ 0` 이다. 기타법인이 작은 종목에서는 `I ≈ −S` 가 되어
  `flow_opposition_score` 가 **±1 로 포화하고 강도 정보를 잃는다** —
  `compute_foreign_3day_trend` 의 3값 문제와 같은 종류의 실패.
  그래서 `score` 를 단독으로 두지 않고 `_qty`·`_ratio` 를 강도 채널로 병치했다.
  **포화 빈도는 실데이터로 미측정**
- 증거 (내가 재실행해 확인):
  - `cd backend && .venv/bin/python -m pytest tests/unit -q --no-header` → `994 passed, 148 warnings in 13.41s`
  - 기준선 `978 passed` → `994` = **+16 (에이전트가 추가한 테스트 수와 일치). 회귀 0건**
  - 반환 딕셔너리는 **순수 추가**. 기존 5개 키의 이름·값·`total_volume == 0` 동작 불변 → 깨지는 호출부 없음
- **에이전트가 지시대로 하지 않은 것 (올바른 판단)**:
  `compute_foreign_3day_trend` 를 **고치지 않고 제안만** 했다 (지시대로).
  제안 5개: `foreign_flow_persistence`(연속일수÷창, 창 파라미터화),
  `foreign_flow_intensity`(순매수합÷거래량합), `foreign_flow_acceleration`(최근 절반−이전 절반),
  `foreign_flow_zscore`(60일 분포 대비), `0`(관망)을 매도와 분리.
  **경고: 창 길이·z-score 창은 자유 파라미터이므로 도입 시 다중검정 시행횟수에 계상되어야 한다** (ADR-0016 1순위와 상호작용)
- **에이전트가 동시 작업을 감지해 경고**: 종료 시점 `git status` 에
  `backend/app/schemas/validation.py` (+72/−3, 타 에이전트의 Q-002b 작업)가 있음을 보고하고
  `CLAUDE.md` 3.2 에 따라 경로 명시 스테이징을 요구했다. **감독자가 그대로 따랐다**
- 검수: 미검수 — 병합 전 독립 검수 대상
- 남은 범위: 프로덕션 배선(Q-020c), 개인 거래대금(Q-020d), 포화 빈도 실측, ruff·타입체크 미실행
- 다음 작업: 구현 A·C 완료 대기 → 통합 독립 검수 → CI → 병합
- 대체: 없음

### [L-0014] 경쟁 지형 조사 — 11개 축 중 10개 열위. 내 문서가 내 규칙을 위반한 것 2건 발견
- 날짜: 2026-09-27
- 담당: 경쟁 조사 에이전트(`Explore`) / 기록: main
- 상태: 구현됨 (조사 문서)
- 무결성: 시작·종료 `git status --porcelain` 빈 출력 동일
- **가장 불편한 발견**: `paul00-post/kr-equity-quant-research` (1인 GitHub 프로젝트)가 우리가
  차별점으로 계획한 항목 대부분을 이미 구현하고 **2026-09-21부터 개인 자본으로 실거래 중**이다.
  검증 엄격성·비용 정확도·정직한 보고·실거래 착수 **네 축 모두에서 현재 우리보다 앞서 있다.** → ADR-0017
- **내 문서가 `CLAUDE.md` 1.1절을 위반한 것 2건 (ADR-0013)**:
  1. `arXiv:2512.23847` 의 **"상승 확률 0.9999" 는 초록에서 확인되지 않는다.**
     나는 **측정·확인하지 않은 수치를 서술했다.** 삭제 대상
  2. `arXiv:2608.31041` 인용이 원문보다 강하다. 원문은 매수보유 대비 열위를 단정하지 않는다
  - **더 강한 대체 근거를 정직하게 확보**: Agent Market Arena Table 1 — 80개 조합 중
    매수보유를 이긴 것 **13개 = 16.25%**, 그리고 **거래비용 미모델링** → 16.25% 는 상한
- **ADR-0008 세율이 낡았다 (ADR-0014)**: 2026-01-01 시행으로 KOSPI 0.15%→**0.20%**,
  KOSDAQ 0.15%→**0.20%**. 내 "왕복 0.3~0.4%" 는 과소추정. 단기→선물 논지는 **강해졌다**.
  또 "파생에 세금 없다"는 부정확 — 거래 단위 거래세가 사실상 없고 **이익에 11% 양도소득세**
  (기본공제 250만, 국내외 손익통산)
- **규제 ADR 이 0건이었다 (ADR-0015)**: 2026-04-12 금감원이 **자동매매 프로그램 제작·판매를
  미등록 투자일임업으로 적발**했다. 무죄 판례(인천지법 2017노1649)의 범위는 "소프트웨어 + 기본 설정값"이며
  **주문까지 내는 우리 구조는 그 밖일 가능성이 높다.** → 타인 배포 금지를 결정으로 못박음
- **KIS 진입장벽 소멸**: KIS 가 공식 `kis-ai-extensions`(Lean 백테스터 + MCP + 실주문)를 배포한다.
  우리 KIS 연동 880행의 장벽 가치가 상각됐다. 단 그 README 에 과최적화·비용·세금·수급·리스크 한도 언급이 전부 없다
- **유일하게 비어 있는 상위 칸**: **다중검정 보정(DSR/PBO/시행횟수 로깅).**
  네이티브 제공 리테일 플랫폼을 하나도 찾지 못했다 — QuantConnect 포함.
  장벽이 기술이 아니라 **인센티브**다 (시행횟수를 세면 자기 마케팅 숫자가 할인된다).
  우리 Q-011→Q-012→Q-014 가 이미 그 순서다. `scoring.py` 98행 규모
- **코드에서 새로 확인된 결함 2건**:
  - `flow_signals.py:30` — `individual_qty` 를 읽고 **반환하지 않는다. 죽은 변수.**
    "1급 알파" 모듈이 **뉴스 함정 필터에 필요한 개인 순매수를 버리고 있다** (ADR-0006 이 요구하는 입력)
  - `limits.py:85` — 최악손실 3% 하드코딩, 종목 변동성 무관. **선물이 붙으면 즉시 깨진다** (게이트 B 실질 근거)
- **가설 판정 (ADR-0016)**: A 부분 반증(미국에도 BJZ 2021 리테일 주문불균형이 있다, 젠포트가 수급 팩터 보유) /
  B 조건부 지지·범위 축소(빈 칸은 다중검정 보정이라는 좁은 칸) / C 지지·강화 /
  **D 불충분·부분 반증**(외부 증거 0건, 우리 원장이 반대 증거 3건 제공 — 파이프라인이 자기 결함을 생산했다)
- **문헌이 공통으로 지목하는 리테일 실패 원인은 알파 부족이 아니라 비용이다**:
  Barber-Odean(2000) 회전율 상위 20% 연 −6.5pp / 대만 36만 데이트레이더 15년 수수료 후 초과수익 1% 미만,
  개인 손실이 연 GDP 2.2% / arXiv:2607.20093 "Retail Trader's Ruin" — RSI·MACD·골든크로스가 비용 반영 후 실패.
  **그리고 우리 엔진은 그 비용을 equity 곡선에 넣지 않고 세금은 0건이다**
- 검수: 미검수 (조사 문서). 단 인용 정정 2건은 원문 대조로 확정됨
- 남은 범위: 미조사 — 젠포트 수급 팩터 구체 정의(가설 A 판정 정확도가 여기 달림),
  선물 실왕복비용, 파생상품거래세 탄력세율 현행 여부, 한국 수급 알파 최신 감쇠 측정, 코스콤 심사기준 원문
- 다음 작업: PR #1 결함 수정 → 재검수 → 병합. 그 다음 Q-001
- 대체: 없음

### [L-0013] 삼중 배리어 + Purged CV 명세 (Q-015·Q-010) — 신규 치명 결함 1건 발견
- 날짜: 2026-09-27
- 담당: 설계 조사 에이전트(`Explore`) / 기록: main
- 상태: 구현됨 (명세만. 코드 무변경)
- 무결성: 시작·종료 `git status --porcelain` 빈 출력 동일. Python 미실행(`__pycache__` 생성 없음)
- **신규 치명 결함 (원장 미기재였음) — Q-010 범위를 바꾼다**:
  `build_feature_matrix` 가 행을 `event_indices + non_event_indices` 순서로,
  라벨을 `[1]*k + [0]*m` 으로 만든다 (`pattern_discovery.py:80-81`).
  그런데 `train_classifier` 는 이 행 순서에 `TimeSeriesSplit` 을 적용한다 (`:143, :157`).
  → **행렬이 시간순이 아니라 라벨순으로 정렬되어 있다.**
  결과: ① 시간축이 무의미 ② 앞쪽 폴드가 단일 클래스(전부 1)가 되어 그 클래스만 예측
  ③ 마지막 테스트 폴드는 전부 라벨 0 → `:181-186` 의 accuracy/precision/recall/f1 은 **정렬 순서의 산물**이다.
  **`TimeSeriesSplit` 을 `PurgedKFold` 로 바꿔도 이 정렬을 고치지 않으면 CV 는 여전히 무의미하다.**
- **L-0001 을 정정·보강하는 사실**:
  - `combinatorial_purged_cv` 는 "purge 미적용"이 아니라 **학습 경로가 아예 없다**
    (`out_of_sample.py:139-152`). `train_mask`·`purge_start`·`purge_end`·`train_data` 4개가 전부 죽은 계산.
    적용할 대상 자체가 없으므로 purge 로직만 고쳐도 CV 가 되지 않는다
  - **Combinatorial 도 아니다** (`:134` 반복당 테스트 그룹 1개 → 경로 `n_splits`개).
    AFML CPCV 는 k>1 로 `C(N,k)` 분할과 `k·C(N,k)/N` 경로를 만든다. **이름이 두 가지로 틀렸다**
  - purge 가 **양방향**이고 폴드 경계에서 **행 수**로 계산됨 (`:140-142`).
    AFML 은 embargo 를 테스트 블록 **오른쪽에만**, **purge 종료 지점부터**, 라벨 종료시각 `t1` 기준으로 적용한다.
    openquant issue #134 와 동일한 알려진 결함 유형
  - `walk_forward.py:23-33` 은 `train` 미사용 문제 이전에 **윈도 구조 자체가 WFA 가 아니다** —
    5개 분리 블록이며 확장형도 롤링도 아니고 파라미터 재적합도 없다
  - 모든 예외를 삼켜 `sharpe_ratio: 0, error: True` 로 기록하고 그걸 평균에 섞는다 (`:162-179`).
    전량 실패해도 `cpcv_score: 0.0` 이 정상 응답으로 반환된다
  - **누출은 이 함수 밖에서 일어난다**: 모든 폴드가 같은 `params` 를 쓰고(`:151`),
    호출부 `api/v1/backtests.py:229-233` 이 이미 다른 곳에서 적합된 `strategy.parameters` 를 넘긴다.
    이 함수는 그 누출을 탐지할 수 없다
- **`scoring.py` 신규 결함 2건**:
  - `:48` 이 `metric_name in ("wfa_score","stability")` 로 분기하나 `SCORING_WEIGHTS` 에 `"stability"` 키가 없다 → **죽은 조건**
  - `normalize_metric` 이 [0,100] 으로 클립(`:33-37`) → **Sharpe 10(결함 신호)이 100으로 정규화돼 A+ 를 받는다.**
    ADR-0003 은 "Sharpe 2 초과는 결함 신호"로 규정했는데 현 스코어러는 결함을 **보상**한다
- **위험을 낮추는 사실**: `extract_rise_events` 는 **운영 호출부가 없다** (`periodic_tasks.py:939-961` 플레이스홀더,
  호출처는 테스트뿐). 시그니처를 바꿔도 되므로 Q-015 교체 위험이 낮다
- **엔진 제약**: `engine.py:39` 가 `close` 만 소비하고 `high`/`low` 를 쓰지 않는다 →
  **삼중 배리어 라벨의 체결 가능성을 현 엔진으로 검증할 수 없다.** Q-001/Q-017 이후에야 T22 유형 테스트가 성립
- **픽스처 제약**: `proof_lookahead.py:41` 은 OHLC 축퇴(high=low=close) → 배리어 테스트에 사용 불가.
  일중 경로를 보존하는 새 생성기 필요
- **균형 있는 반대 증거 (숨기지 않고 기록)**: 한국시장 실증연구(arXiv:2504.02249, KOSPI+KOSDAQ 전종목
  2006-2024, 8,566,617 표본)는 **고정 9%/9%** + 수직 29일로 균형 3분류 분포를 얻고 LSTM F1 0.4312
  (더미 0.1852) 를 보고했다. → "고정 %가 한국시장에서 실패한다"는 주장은 성립하지 않는다.
  결론: 두 모드를 모두 구현하고 기본값만 동적으로 한다
- **우선순위 권고**: **Q-015(삼중 배리어)를 Q-010 보다 먼저.** 단 둘 다 Q-001 뒤.
  근거: Q-010 의 올바른 purge 입력은 `t1` 이고 코드베이스에 존재하지 않는다.
  `t1` 없이 Q-010 을 만들면 상수 `purge_days` 에 기대야 하고 그것이 현재의 결함 설계 그대로다
- **위험 비대칭 논거**: Q-010 만 출하하면 "도달 불가능한 라벨을 엄밀하게 측정" — 허구에 대한 정밀 측정.
  Q-015 만 출하하면 "체결 가능한 라벨을 결함 splitter 로 측정" — 점수를 공표하지 않는 한 정직하다.
  ADR-0001 은 후자를 허용하고 전자를 허용하지 않는다
- **더 값싼 대안 (정직하게 기록)**: 목표가 "`combinatorial_purged_cv` 가 사용자를 오도하는 것을 멈추는 것"뿐이라면
  가장 값싼 조치는 `api/v1/backtests.py:222-236` 이 명시적 "미검증" 상태를 반환하게 하는 ~10행 변경이다.
  Q-001 의존도 없고 정직성 이득이 크다
- **에이전트가 스스로 표시한 무근거 수치**: `min_cost_multiple=3.0`, `ambiguous` 경고 5%,
  `avg_uniqueness` 경고 0.3, 호라이즌별 수직 배리어 5/20/120일과 pt/sl 배수 — 전부 제안값이며 문헌 근거 없음
- 검수: 미검수 (명세 문서)
- 남은 범위: 미해결 질문 10건 — KRX 가격제한폭 산출 규칙, KIS `FID_ORG_ADJ_PRC="0"` 의미,
  AFML 원서 직접 대조, 기존 라이브러리 도입 여부, `t1` 영속화 위치 등
- 다음 작업: QUEUE 재편 (Q-015a → Q-010a → Q-015b+Q-010b → Q-010c)
- 대체: 없음

### [L-0011] 독립 검수 판정 `반증됨` — 결함 11건. 병합 보류
- 날짜: 2026-09-27
- 담당: 독립 검수자(`Explore`, 쓰기 도구 없음) / 기록: main
- 상태: **반증됨**
- 대상: `chore/agent-governance` 6커밋 (`main...HEAD`, merge-base `7940262`, HEAD `5e3bb8a`, 33파일 +1352/−30)
- 검수 무결성: 검수 전/후 `git status --porcelain` 모두 빈 출력. `--untracked-files=all` 도 공백.
  HEAD 동일, `backend/.venv` mtime 불변. **검수 유효.** 검증은 전부 `git archive` 추출본 + 신규 venv 6개에서 수행
- **`높음` 2건 (병합 차단)**:
  - **D1** `pyproject.toml:13` `starlette>=0.46.0,<1.0` 이 **해롭다.** 이 범위의 0.52.1은 공표 권고 5건에 해당하고
    **전부 1.x에서만 수정**되었다(fixed 1.0.1/1.1.0/1.1.0/1.3.0/1.3.1) — `<1.0` 안에 안전한 버전이 없다.
    게다가 **불필요**: `fastapi 0.136.3 + starlette 1.7.0` 로 전체 스위트 `1102 passed in 81.81s`
  - **D2** 7개월 실패의 **인과가 거짓** → ADR-0012 로 정정
- **`중간` 4건**:
  - **D3** `bcrypt>=4.0,<4.1` 의 근거가 틀렸고 상한이 4개 마이너 과도하다.
    `__about__` AttributeError 는 `passlib/handlers/bcrypt.py:620` 에서 **트랩되어 로그 경고로 끝난다.**
    실제 치명 예외는 `:655` 의 `ValueError: password cannot be longer than 72 bytes`.
    실측: 4.0.1 OK / **4.1.0 FAIL**(`TypeError: argument 'salt'`) / 4.1.1·4.1.2·4.1.3·4.2.0·4.3.0 **전부 OK** / **5.0.0 FAIL**.
    올바른 제약은 `>=4.1.1,<5.0` 계열. 현재 핀은 비밀번호 해싱을 2022-10 릴리스에 틀린 이유로 동결한다
  - **D4** `ci.yml:69-72` 런타임 Fernet 키가 **공개 CI 로그에 평문 노출**. `gh run view 36256788463 --log` 920행에서 확인.
    저장소는 `PUBLIC`. `::add-mask::` 미사용
  - **D5** `cd92915` 커밋 메시지 불일치(L-0009 기록됨) + `aef6d4a` 가 "Fix 7 months of CI" 라 자칭했으나
    그 커밋의 런 `36255510347` 은 **failure**. 초록은 `cd92915` 부터
  - **D6** `tests/integration/test_market_api.py::TestDailyReport::test_get_balance` **순서 의존 테스트.**
    전체 스위트에서만 통과, 단독·파일단위 실행 시 실패. sqlalchemy 2.0.54/2.1.1, main/HEAD 모두 동일.
    `RecursionError` 가 traceback 포맷팅을 파괴해 원인 은폐. **이 브랜치 무관 기존 결함**
- **`낮음` 5건**: D7 `alembic.ini:4` bare URL 잔존(내 "21개 파일" 주장이 놓친 22번째, 실사용은 `env.py:16`이 덮어써 무해) /
  D8 `fastapi>=0.115.0` + `starlette>=0.46.0` 이 0.115.0–0.115.11 구간에서 해 없음(실효 하한 0.115.12) /
  D9 내 주석 "0.130까지 `<1.0.0`" 오류 — 실제로는 0.132.0까지 유지, 0.133.0에서 제거 /
  D10 `CLAUDE.md` §1.2·§4.3 이 인용한 `Sharpe 10.74 → 0.24` 가 커밋된 `proof_lookahead.py`(SEED=7) 실행값
  `9.99 / −0.51` 과 불일치 (L-0003에 차이를 기록했으나 CLAUDE.md 본문은 갱신하지 않았다) /
  D11 `frontend/.gitignore:34` `.env*` 에 negation 없어 `frontend/.env.example` 이 IGNORED
- **검수가 확인한 유효 사항 (공정 기록)**:
  - `1102 passed` 재현 — CI 로그 1086행 `1102 passed, 621 warnings in 62.70s` 와 정확히 일치
  - sqlalchemy 메커니즘 정확히 재현: `Interrupted: 2 errors during collection`, 테스트 0건 (단 **현재 시점** 조건에서)
  - fastapi `<0.137` 경계 — 휠 6종 직접 grep: 0.134.0~0.136.3 없음, **0.137.0 최초 등장**. 한 칸도 틀리지 않았다
  - `.gitignore` 반대 실험: main 규칙에서는 `git add -A` 가 `.env.bak-*`·`.env.save` 를 스테이징,
    HEAD 규칙에서는 `.env.example` 만. **누출 경로 실재했고 닫혔다**
  - `config.py` 배포 정합성: `docker-compose.yml` 3개 서비스 전부 갱신됨, bare URL 잔존 서비스 없음
  - 금융 체크리스트: `git diff main...HEAD --stat -- backend/app/analysis/` 공백 — 이 브랜치는 분석·거래 로직 무변경.
    체크리스트를 건너뛴 것이 아니라 **대상이 없음을 확인**
- **검수불가 3건**: 2026-02~09 원본 CI 로그(`HTTP 410`, 90일 보존 만료 — 시점 복원으로 대체) /
  job-level `env:` 와 `$GITHUB_ENV` 우선순위(공식 문서 미명시, 관측 조건 부재) / starlette 1.x 운영 적합성
- 검수자 권고: D1 상한 재검토, D2·D3 기록 정정, D4 `::add-mask::`, D7 정리, D6 별도 항목 분리
- **판정에 따른 조치**: `CLAUDE.md` 3.1절에 의해 **병합하지 않는다.** 수정 → 재검수 → 병합
- 남은 범위: 수정 작업 미착수
- 다음 작업: 수정 지시 → 재검수 → PR #1 병합
- 대체: 없음

### [L-0010] CI 초록 달성 (판정은 L-0011로 대체됨)
- 날짜: 2026-09-27
- 담당: main + 구현 에이전트
- 상태: 구현됨 (검수 결과 `반증됨` — L-0011 참조)
- 증거 (CI `36256788463`): `결론: success` / `1102 passed, 621 warnings in 62.70s` /
  설치 버전 `fastapi-0.136.3 starlette-0.52.1 sqlalchemy-2.0.54 bcrypt-4.0.1 psycopg2-binary-2.9.13`
- 진행 경과: `2 errors during collection`(0건 실행) → `8 failed, 1094 passed` → `1102 passed`
- 교차 확인: CI `1102 passed` = 로컬 신규 환경 `1102 passed`. 서로 다른 OS·Python·DB포트에서 독립 재현
- **원인 3(fastapi)의 발견 경로**: 감독자 가설("ENCRYPTION_KEY 부재로 라우터 import 실패")을
  구현 에이전트가 **반증**했다. 유효 키를 주입해도 실패했고, 0.136.0/0.137.0 이분 탐색으로 경계를 확정했다.
  지시서에서 가설을 검증 대상으로 명시한 것이 작동했다
- 검수: L-0011 에서 `반증됨`. 근거 서술과 상한 범위에 결함
- 다음 작업: L-0011 결함 수정

### [L-0012] `instrument` 설계 명세 (Q-016) — 내 기억 오류 2건 정정 포함
- 날짜: 2026-09-27
- 담당: 설계 조사 에이전트(`Explore`) / 기록: main
- 상태: 구현됨 (명세만. 코드 무변경)
- 무결성: 시작·종료 `git status --porcelain` 빈 출력 동일. 파일 변경 없음
- **내 기억 오류 정정**:
  1. "upsert 로직이 유니크 제약에 의존한다"는 `CLAUDE.md` 에 없다. 출처는 `PROJECT_STATUS.md:106` 과 커밋 `280d101`.
     그리고 **DB 레벨 `ON CONFLICT` upsert 가 아니다** — `strategy_search.py:269-314` 와
     `optimization_tasks.py:300-344` 의 애플리케이션 레벨 SELECT-then-INSERT 두 벌이다.
     제약의 실제 역할은 (a) Celery 병렬 워커의 경쟁 삽입 차단 (코드에 락 없음)
     (b) `scalar_one_or_none()` 이 `MultipleResultsFound` 를 던지지 않음을 보장.
     → 제약을 드롭하면 문법적으로 안 깨지고, **중복 행이 쌓인 순간부터 `MultipleResultsFound` 로 터진다**
  2. 진짜 `ON CONFLICT` 의존처는 `factor_collector.py:363-368` — 원시 SQL이 **제약명을 하드코딩**한다.
     `:373-378` per-row `except` 가 `warning` 으로 삼켜 **깨져도 조용히 전량 실패**한다
- **간과했던 차단 요인 (중요)**:
  - `Order.side` / `Trade.side` 가 `String(4)` (`order.py:26`, `trade.py:24`) — **`'short'`(5자)를 담지 못한다.**
    ADR-0008 의 핵심이 양방향 거래인데 스키마가 거부한다. `String(8)` 확장 필요
  - `quantity` 가 전부 `Integer` — 미국 fractional share 불가
  - `Numeric(15,2)` scale 2 가 FX 환율·선물 호가에 충분한지 미검증
- **백필 전제 반증**: `strategies.stock_code` 에 **미국 티커가 들어 있을 수 있다.**
  `yahoo_provider.py:91-93` 이 `market="us"` 일 때 ASCII 티커를 그대로 반환하고 `strategy_search.py:142` 가 저장하는데,
  `market` 은 영속되지 않는다(`schemas/strategy.py:56`). 또 `factor_snapshots` 에는 `'_GLOBAL'` 센티넬이 확실히 있다
  (`global_factor_collector.py:4`). → "국내 현물로 가정" 백필은 **불가**
- **위험 발견**: `alembic/versions/__pycache__/ade92cc5b58f_*.pyc` 가 있으나 대응 `.py` 가 없다(고아 리비전).
  어떤 DB가 그 값으로 stamp 되어 있으면 마이그레이션이 전혀 진행되지 않는다
- 조사된 사실: Alembic head `5df163bb88a2` / `krx_stocks.json` 2,771건(KOSDAQ 1,821 · KOSPI 950, `sector` 전부 공백) /
  `stock_code` 사용처 backend 615건(66파일) + frontend 139건 / 유니크 제약 4개 / 금액 전부 `Numeric(15,2)` /
  KIS `constants.py` 경로가 전부 `/uapi/domestic-stock/` — 해외·선물 경로 0건
- 설계 권고: `instruments` 는 **시점 무관 정적 속성만**. 시변 항목은 `tick_size_rules`·`cost_rules`·`trading_sessions`
  3개 테이블로 분리하고 **유효기간(`effective_from/to`)** 을 갖게 한다. 유동성은 `factor_snapshots` 재사용
  (스칼라로 두면 point-in-time 이 깨져 룩어헤드 재유입)
- 검수: 미검수 (명세 문서)
- 남은 범위: 미해결 질문 10건 — 선물 규정 수치, KIS 선물/해외 경로, 운영 DB 실측, `strategy_key` 생성열 승인 등
- 다음 작업: Q-016 을 Q-016a/Q-016b 로 분할 (권고 수용)
- 대체: 없음

### [L-0009] 절차 위반 — 타 에이전트 미완성 작업을 검수 전 커밋
- 날짜: 2026-09-27
- 담당: main
- 상태: 구현됨 (사고 기록 + 재발 방지)
- 대상 파일: 커밋 `cd92915`, `CLAUDE.md:3.2절`
- **무슨 일이 있었나**:
  구현 에이전트가 `backend/pyproject.toml` 과 `.github/workflows/ci.yml` 을 수정하는 동안
  감독자(main)가 `.env` 규칙 개정을 커밋하려고 `git add -A` 를 실행했다.
  그 결과 **실행 중인 에이전트의 미완성 변경이 독립 검수 없이 커밋**됐고,
  커밋 메시지는 `.env`/`.gitignore` 만 설명해 실제 내용과 불일치했다.
- 증거:
  - `git show cd92915 --stat` → `.github/workflows/ci.yml | 11 ++++-` , `backend/pyproject.toml | 7 ++++-`
  - 해당 커밋 메시지에 두 파일에 대한 설명 없음
  - 구현 에이전트는 커밋 시점에 **완료 통지 전**이었다 (작업 중)
- 영향 평가:
  `chore/agent-governance` 브랜치에만 있고 `main` 에 병합되지 않았다. 실거래 코드 영향 없음.
  독립 검수는 병합 전에 수행하므로 "검수 없이 main 진입"은 발생하지 않는다.
  이력은 정정하지 않는다(추가만 하는 원칙). 대신 이 항목이 기록이다.
- 재발 방지: `CLAUDE.md` 3.2절 신설 —
  에이전트 실행 중 `git add -A`/`git add .` 금지, 경로 명시 스테이징 의무,
  커밋 메시지가 모든 변경을 설명하는지 검토 의무
- **참고 — 커밋에 섞여 들어간 구현 에이전트 변경 요지** (검수 대상이며 아직 미검수):
  1. `ci.yml`: `ENCRYPTION_KEY: ""` job-level 선언을 **제거**하고,
     `$GITHUB_ENV` 로 일회용 Fernet 키를 주입하는 스텝 추가.
     제거 이유로 "job-level env 가 `$GITHUB_ENV` 값을 가릴 수 있음"을 주석에 기재
  2. `pyproject.toml`: `fastapi>=0.115.0,<0.137` 및 `starlette>=0.46.0,<1.0` 고정.
     주석 근거 — fastapi 0.137+ 가 `include_router` 시 실제 라우트 대신
     `path` 속성이 없는 `_IncludedRouter` 를 `app.routes` 에 등록해 라우트 introspection 이 깨진다
     (`test_app_creation` 의 `any("/api/v1" in p ...)` 실패 원인 가설)
  → 이는 ENCRYPTION_KEY 와 **다른 원인**이며, Q-007(의존성 전수 고정)의 추가 근거다.
  **이 내용은 구현 에이전트의 주장이며 검수로 확정되지 않았다.**
- 검수: 미검수 — 구현 에이전트 완료 후 독립 검수자(`Explore`)가 판정한다
- 남은 범위: 독립 검수, CI 재확인, PR #1 병합
- 다음 작업: 구현 에이전트 완료 대기 → 독립 검수 → CI 초록 확인 → 병합
- 대체: 없음

### [L-0008] `.env` 수정 규칙 개정 + gitignore 비밀값 유출 경로 차단
- 날짜: 2026-09-27
- 담당: main
- 상태: 검증됨 (실행으로 재현 가능)
- 대상 파일: `.gitignore:14-20`, `CLAUDE.md:69-93,183-190`, `.env`(추적 안 됨), `backend/.env`(추적 안 됨)
- 한 일:
  1. 사용자 지시로 `.env` 수정 금지를 해제. `CLAUDE.md` 2.3절 신설 — 수정은 허용하되
     **비밀값 출력 금지 / `.env` 계열 커밋 금지 / 새 비밀값 생성 금지** 세 조항과 5단계 절차를 명문화
  2. `.env` 와 `backend/.env` 의 `DATABASE_URL_SYNC` 를 `postgresql+psycopg2://` 로 수정 (L-0005 후속)
  3. **`.gitignore` 의 비밀값 유출 경로를 차단** (아래 사고 항목)
- 증거:
  - 수정 전: `.env:7` / `backend/.env:9` 모두 `DATABASE_URL_SYNC=postgresql://***:***@localhost:15432/able`
  - 수정 후: 둘 다 `postgresql+psycopg2://***:***@localhost:15432/able`
  - 백업 생성: `.env.bak-20260927-014323`, `backend/.env.bak-20260927-014323`
  - 동작 검증: `DATABASE_URL_SYNC 드라이버: psycopg2` / `DATABASE_URL 드라이버: asyncpg`
  - 앱 임포트: `async engine: asyncpg` / `sync engine: psycopg2` / `앱 임포트 성공`
  - 회귀 없음: `pytest tests/unit -q` → `978 passed, 148 warnings in 13.51s`
  - 변수명 무결성 확인: `backend/.env:9` 는 `DATABASE_URL_SYNC` 로 온전함.
    사용자가 선택해 보여준 `ATABASE_URL_SYNC` 는 선택 시작 열이 2열이어서 `D` 가 빠져 보인 것이며 손상이 아니다
- **사고 (내가 만들었고 즉시 차단함)**:
  `.gitignore` 가 `.env` `.env.local` `.env.production` **정확한 파일명만** 막고 있었다.
  내가 만든 `.env.bak-*` 백업 2개가 `git check-ignore` 에서 **추적 대상**으로 확인됐다.
  → `git add -A` 시 `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `SMTP_PASSWORD`, `ENCRYPTION_KEY`,
    `SECRET_KEY` 가 공개 저장소(`github.com/cho-y-j/able`)에 커밋될 상태였다.
  **자동 루틴이 `git add -A` 를 실행하므로 실제 유출로 이어질 수 있었다.**
  조치: `.gitignore` 를 `.env*` + `!.env.example` + `!.env.*.example` 로 교체.
  검증: 백업 2개와 `.env` 2개 모두 `ignore됨`, `.env.example` 2개는 `추적 유지`,
        `git status --porcelain | grep -E "\.env"` → 출력 없음
  과거 이력 확인: `git log --all --diff-filter=A --name-only` 에 `.env` 계열 추가 이력 **없음** —
  비밀값이 이력에 남은 적은 없다
- 검수: 자체 검증이나 재현 가능. `git check-ignore -q <파일>` 로 누구나 확인 가능
- 남은 범위:
  - 루틴 프롬프트의 `.env` 금지 조항을 개정된 규칙에 맞게 갱신해야 함
  - 백업 파일 2개는 보존 중 (ignore됨). 사용자가 원하면 삭제 가능
- 다음 작업: 루틴 프롬프트 갱신 → 구현 에이전트 결과 수령 → 독립 검수 → PR #1 병합
- 대체: 없음

### [L-0007] 루틴 프롬프트 v2 — 3축 격자 연결, 에이전트 폴백, 문자열 손상 수정
- 날짜: 2026-09-27
- 담당: main
- 상태: 구현됨
- 대상: 루틴 `trig_01WXgK8LSrLNGWyfZkSZVkxw` (저장소 파일 아님), `docs/research/QUEUE.md`
- 한 일:
  1. `QUEUE.md` 상단에 **목표 설계(v2) 3축 격자**를 삽입 — 호라이즌 × 자산군 × 정보원 표와
     게이트 A(측정 장치 완성 전 새 알파 탐색 금지) / 게이트 B(Q-032가 Q-033보다 선행).
     루틴이 맥락 없이도 오늘 작업이 어느 칸인지 알 수 있게 함
  2. 루틴 프롬프트에 **에이전트 폴백** 지시 추가 (L-0006 제약 대응):
     `quant-builder` 없으면 `general-purpose` + 정의 파일 인라이닝,
     `quant-reviewer` 없으면 **`Explore`** (쓰기 도구 없음). `general-purpose`를 검수자로 쓰는 것을 명시 금지
  3. 기준선 기대값을 실측값 `978 passed`로 명시. 다르면 원인 추적하도록 지시
  4. 의존성 고정(`sqlalchemy<2.1`, `bcrypt<4.1`)을 이유 없이 풀지 못하게 금지 항목 추가
- **내 실수 기록 (은폐하지 않음)**:
  1차 update에서 유니코드 이스케이프를 손으로 작성해 여러 단어가 손상됐다.
  `차단 요인` → `착단 요인`, `3축 격자` → `3축 공객`, `서브에이전트` → `서본에이전트`,
  `main 브랜치` → `main 밌치`, `기준선 대비` → `기존선 대바`, `빈손` → `번손`, `영문` → `옆문`.
  이 중 `착단 요인`과 `3축 공객`은 **기능 결함**이었다 — QUEUE.md의 실제 문자열과 불일치하므로
  루틴이 항목 선택과 격자 조회에 실패했을 것이다.
  원인: 이스케이프를 검증 없이 손으로 작성. 조치: 2차 update에서 한글을 직접 입력해 재작성하고
  저장된 프롬프트를 읽어 문자열 일치를 확인했다.
  **교훈**: 이스케이프된 텍스트를 손으로 쓰면 검증 없이는 신뢰할 수 없다. 반드시 읽어서 확인한다.
- 증거:
  - `RemoteTrigger update` → `HTTP 200`, `updated_at: 2026-09-26T16:36:53Z`
  - 저장된 프롬프트 확인: `차단 요인: 없음`, `3축 격자`, `서브에이전트`, `main 브랜치`,
    `기준선 대비`, `빈손 보고`, `Explore` 폴백 지시 모두 정상
  - `grep -c '^### \[Q-' docs/research/QUEUE.md` → `20`
- 검수: 미검수 — 첫 실행(2026-09-27 06:08 KST) 결과로 판정
- 남은 범위: Q-008(클라우드 에이전트 로드 여부)은 첫 실행에서만 확인 가능
- 다음 작업: 구현 에이전트의 CI 통합 8건 수정 결과 수령 → 독립 검수 → PR #1 병합
- 대체: 없음

### [L-0006] 에이전트 정의 등록 시점 제약 발견
- 날짜: 2026-09-27
- 담당: main
- 상태: 구현됨 (사실 기록)
- 대상: `.claude/agents/*.md`
- 한 일: L-0002에서 만든 커스텀 에이전트를 같은 세션에서 호출 시도
- 증거:
  - `Agent(subagent_type="quant-builder")` →
    `Agent type 'quant-builder' not found. Available agents: claude, claude-code-guide, Explore, general-purpose, Plan, statusline-setup`
- **확정된 사실**: `.claude/agents/` 는 **세션 시작 시점에 로드**된다. 세션 도중에 만든 정의는
  그 세션에서 사용할 수 없다. 새 세션에서는 인식된다.
- **미검증 (중요)**: 클라우드 루틴(신규 세션 + 저장소 clone)이 `.claude/agents/` 를 실제로
  로드하는지 **확인되지 않았다.** 루틴 프롬프트는 `quant-builder`/`quant-reviewer` 호출을 전제하는데,
  로드되지 않으면 루틴이 첫 단계에서 실패한다. 2026-09-27 첫 실행 결과로만 확인 가능하다.
  → 대응: 루틴 프롬프트에 폴백 지시를 추가함 (L-0007 예정)
- **이 세션의 우회 경로**: 구현은 `general-quality` 대신 `general-purpose` 에이전트에
  `quant-builder` 지시를 인라인으로 전달. 검수는 `Explore` 에이전트 사용 —
  `Explore` 의 도구 집합이 `Edit`/`Write`/`NotebookEdit` 를 제외하고 `Bash` 는 포함하므로,
  "쓰기 도구 없는 독립 검수자"라는 구조적 보장이 유지된다.
- 검수: 해당 없음 (환경 사실 기록)
- 남은 범위: 루틴의 에이전트 로드 여부 검증
- 다음 작업: 루틴 프롬프트에 폴백 추가
- 대체: 없음

### [L-0005] CI 7개월 무력화 원인 규명 및 의존성 버전 고정
- 날짜: 2026-09-27
- 담당: main
- 상태: 구현됨
- 대상 파일: `backend/pyproject.toml:12,24`, `backend/app/config.py:12`, `.github/workflows/ci.yml:45`,
  `docker-compose.yml`(3곳), `.env.example`, `backend/.env.example`, 테스트 18개 파일
- 한 일: PR #1의 CI 실패를 조사한 결과, 실패가 **제 변경과 무관하며 2026-02-19부터 계속된 것**임을 확인.
  무고정 의존성 2건이 원인이었고, 실제로는 **수집 단계에서 중단되어 테스트가 단 하나도 실행되지 않았다.**
- 증거:
  - CI 이력: `gh run list --workflow=ci.yml` → main 브랜치 최근 6회 전부 `failure`
    (2026-02-19T03:33 ~ 2026-02-20T06:30)
  - CI 실패 로그: `E ModuleNotFoundError: No module named 'psycopg'`
    / `ERROR tests/unit/test_metrics.py` / `ERROR tests/unit/test_recipe_performance.py`
    / `Interrupted: 2 errors during collection` / `2 errors in 3.12s`
  - **원인 1** — SQLAlchemy 무고정. 격리 환경(Python 3.13.12)에 `sqlalchemy[asyncio]>=2.0` 설치 →
    `2.1.1`. 스킴 해석 실측:
    `postgresql` → `psycopg` / `postgresql+psycopg2` → `psycopg2`
    `create_engine('postgresql://...')` → `실패 ModuleNotFoundError: No module named 'psycopg'`
    `create_engine('postgresql+psycopg2://...')` → `성공 (psycopg2)`
    로컬은 `2.0.46`이라 `postgresql://` → `psycopg2`로 해석되어 통과했다
  - **원인 2** — bcrypt 무고정. 신규 설치 시 `5.0.0` →
    `AttributeError: module 'bcrypt' has no attribute '__about__'` (passlib 1.7.4가 읽는 속성이 제거됨)
    → `test_strategy_search.py` 17건 오류
  - 버전 대조 실측: sqlalchemy 로컬 `2.0.46` vs 신규 `2.1.1` / bcrypt 로컬 `4.0.1` vs 신규 `5.0.0`
  - 조치 후 **완전 신규 환경**(`/tmp/ci-verify`, Python 3.13.12, `pip install ".[dev]"`) 검증:
    설치된 버전 `sqlalchemy 2.0.54 / bcrypt 4.0.1 / passlib 1.7.4 / psycopg2-binary 2.9.13`
    `pytest tests/unit -q` → `978 passed, 148 warnings in 50.41s`
  - 기존 로컬 환경 회귀 확인: `978 passed in 13.75s` (변경 전과 동일)
- **중요한 사실 (은폐하지 않고 기록)**:
  로컬이 동작했던 유일한 이유는 과거 수동으로 `pip install bcrypt==4.0.1`을 실행했기 때문이며,
  그 수정이 `pyproject.toml`에 반영되지 않았다. 따라서 **새로 clone하는 모든 환경이 깨진 상태였다** —
  CI, 클라우드 루틴, 새 PC, Docker 빌드 전부. 앞으로 "로컬에서 통과"를 검증 근거로 쓸 때
  신규 환경에서도 통과하는지 함께 확인한다.
- **SQLAlchemy 2.1 자체는 무죄**: 2.1.1 + `postgresql+psycopg2://` 조합에서 17 오류는 전부 bcrypt 문제였고
  SQLAlchemy 기인 실패는 0건이었다. `<2.1` 고정은 미검증에 대한 보수적 조치이며 영구 결정이 아니다 (Q-006)
- 검수: 미검수 — CI 자체가 이 변경의 검수자다. PR #1 재실행 결과로 판정된다
- 남은 범위:
  - `.env`(gitignore 대상)의 `DATABASE_URL_SYNC`는 수정하지 않았다. CLAUDE.md가 에이전트의 `.env`
    접근을 금지하며, 사용자가 직접 `postgresql+psycopg2://`로 바꿔야 한다
  - 통합 테스트 미실행 (로컬 DB 기동 필요). CI에서 처음으로 실행될 것이다
  - Docker 빌드 미검증
  - passlib 탈출(Q-005), SQLAlchemy 2.1 마이그레이션(Q-006), 전수 고정(Q-007)은 이연
- 다음 작업: PR #1 CI 재실행 확인 → 병합 → 루틴 첫 실행
- 대체: 없음

### [L-0004] 일일 연구·개발 사이클 클라우드 루틴 설정
- 날짜: 2026-09-27
- 담당: main
- 상태: 구현됨
- 대상: claude.ai 예약 루틴 `trig_01WXgK8LSrLNGWyfZkSZVkxw` (저장소 파일 아님)
- 한 일:
  - 매일 06:00 KST (cron `0 21 * * *` UTC) 실행. 모델 `claude-opus-5`
  - 저장소: `https://github.com/cho-y-j/able` (클라우드가 새로 클론)
  - 사이클: 선행조건 확인 → 기준선 측정 → QUEUE에서 **1건만** 선택 →
    `quant-builder` 위임 → **신규 컨텍스트** `quant-reviewer` 검수 → LEDGER 기록 → 가지 + PR
  - `반증됨` 판정 시 통과 금지. 2회 반증이면 되돌리고 기록. PR 제목에 `[반증됨]` 표기 강제
  - ADR-0004 보호: `risk/limits.py`·`circuit_breaker.py`·`human_approval.py` 수정 금지 (제안만)
  - `main` 직접 수정 금지, `.env` 접근 금지
- 증거:
  - `RemoteTrigger create` → `HTTP 200`, `outcome: CREATE_TRIGGER_OUTCOME_CREATED`
  - `id: trig_01WXgK8LSrLNGWyfZkSZVkxw`, `enabled: true`
  - `next_run_at: 2026-09-26T21:08:27Z` (= 2026-09-27 06:08 KST)
  - 관리: https://claude.ai/code/routines/trig_01WXgK8LSrLNGWyfZkSZVkxw
- **클라우드 환경 제약 (실측)**:
  - PostgreSQL·Redis·KIS 자격증명 없음 → `tests/integration` 실행 불가, KIS 호출 작업 착수 불가
  - 단, `tests/unit` 은 인프라 없이 전량 통과함을 로컬에서 확인:
    `cd backend && .venv/bin/python -m pytest tests/unit -q` → `978 passed in 14.13s`
    (DB·Redis 미기동 상태에서 측정) → 루틴이 전체 유닛 스위트를 검증에 쓸 수 있다
  - 이 제약을 루틴 프롬프트에 명시해, 인프라가 필요한 항목은 건너뛰고 보고하게 함
- 검수: 미검수 — 첫 실행(2026-09-27 06:08 KST) 결과로 실효성이 검증된다
- 남은 범위:
  - **PR #1 미병합 상태에서는 루틴이 아무 작업도 하지 않고 중단한다** (의도된 설계).
    `CLAUDE.md`·`docs/research/*` 가 `main`에 있어야 동작한다
  - 프론트엔드 빌드(`npm run build`)를 클라우드에서 실행 가능한지 미검증
  - MCP 커넥터 2개(`Claude_Docs`, `Claude_Code_Remote`)가 서버에서 자동 부착됨 — 요청하지 않았으며 용도 미확인
- 다음 작업: PR #1 병합 → 루틴 첫 실행이 Q-002 또는 Q-001 착수
- 대체: 없음

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
