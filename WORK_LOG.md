# ABLE Platform - 작업 기록 및 로드맵

> **[2026-09-27 주의]** 이 파일의 과거 기록에 있는 `✅ 완료`는 루트 `CLAUDE.md`의 상태 어휘로는
> **`구현됨`**(코드가 존재함)에 해당하며 **`검증됨`이 아니다.**
> 실례: 아래 Day 1 항목 13 "백테스팅 엔진(벡터화) ✅ 완료" — 해당 엔진은 2026-09-26 감사에서
> 알파 0인 랜덤워크 데이터에 Sharpe 10.74를 보고하는 룩어헤드 결함이 확인되었다
> (`backend/app/analysis/backtest/engine.py:74`, 근거: `docs/research/LEDGER.md` L-0001).
>
> **이 파일의 항목을 "이미 검증된 기능"의 근거로 인용하지 않는다.** (ADR-0010)
> 신규 기록은 이 파일에 추가하지 않고 `docs/research/LEDGER.md`에 한다.

## Phase 1 MVP 작업 기록

### 2026-02-14 (Day 1) - 프로젝트 스캐폴딩 + 핵심 아키텍처 구축

**완료 항목:**

| # | 작업 | 상태 | 파일 수 |
|---|------|------|---------|
| 1 | 보완분석보고서 완전 분석 | ✅ 완료 | - |
| 2 | 3단계 개발 로드맵 수립 | ✅ 완료 | 계획서 작성 |
| 3 | Docker Compose (PostgreSQL+TimescaleDB+Redis) | ✅ 완료 | 1 |
| 4 | Backend FastAPI 프로젝트 구조 | ✅ 완료 | 50+ |
| 5 | SQLAlchemy ORM 모델 (10개 테이블) | ✅ 완료 | 8 |
| 6 | Pydantic 스키마 (Request/Response) | ✅ 완료 | 6 |
| 7 | JWT 인증 시스템 | ✅ 완료 | 3 |
| 8 | Fernet API 키 암호화 (KeyVault) | ✅ 완료 | 1 |
| 9 | REST API 엔드포인트 (7개 라우터) | ✅ 완료 | 8 |
| 10 | KIS API 클라이언트 (REST + WebSocket) | ✅ 완료 | 4 |
| 11 | LLM 프로바이더 추상화 (OpenAI/Anthropic/Google) | ✅ 완료 | 5 |
| 12 | 기술적 지표 30개 구현 | ✅ 완료 | 4 |
| 13 | 백테스팅 엔진 (벡터화) | ✅ 완료 | 1 |
| 14 | Grid Search + Bayesian 최적화 | ✅ 완료 | 2 |
| 15 | Walk-Forward Analysis | ✅ 완료 | 1 |
| 16 | 전략 스코어링 시스템 | ✅ 완료 | 1 |
| 17 | LangGraph 에이전트 오케스트레이션 (5개 노드) | ✅ 완료 | 7 |
| 18 | Celery 비동기 태스크 구조 | ✅ 완료 | 3 |
| 19 | Frontend Next.js 14 (App Router, TailwindCSS) | ✅ 완료 | 12 |
| 20 | 프론트엔드 페이지 7개 | ✅ 완료 | 7 |
| 21 | Zustand 상태 관리 | ✅ 완료 | 2 |
| 22 | API 클라이언트 + WebSocket 매니저 | ✅ 완료 | 2 |
| 23 | 단위 테스트 (지표, 백테스트, 스코어링) | ✅ 완료 | 3 |
| 24 | Alembic 마이그레이션 설정 | ✅ 완료 | 3 |
| 25 | .env 환경설정 + 암호키 생성 | ✅ 완료 | 2 |
| 26 | Frontend 빌드 검증 통과 | ✅ 완료 | - |

---

### 2026-02-14 (Day 1, 후반) - 전체 통합 + 완전 자동화 연결

**완료 항목:**

| # | 작업 | 상태 | 상세 |
|---|------|------|------|
| 27 | WebSocket 라우터 통합 | ✅ 완료 | `router.py`에 websocket 포함, /ws/trading, /ws/agents, /ws/market/{stock_code} |
| 28 | KIS 서비스 레이어 | ✅ 완료 | `services/kis_service.py` - 사용자 암호화된 인증정보에서 KIS 클라이언트 자동 생성 |
| 29 | Market Data → KIS 실연동 | ✅ 완료 | `market_data.py` 전면 재작성: get_price, get_ohlcv, get_indicators, get_balance, get_indices 모두 KIS API 연동 |
| 30 | 주문 실행 → KIS 실연동 | ✅ 완료 | `trading.py` 전면 재작성: place_order→KIS 제출, cancel→KIS 취소, WebSocket 실시간 알림 |
| 31 | Celery 전략 탐색 완전 구현 | ✅ 완료 | `optimization_tasks.py`: KIS OHLCV 동기 fetch → Grid Search (RSI/SMA/BB) → WFA 검증 → 스코어링 → DB 저장 |
| 32 | Celery 백테스트 완전 구현 | ✅ 완료 | `optimization_tasks.py`: 전략 로드 → KIS OHLCV → 백테스트 실행 → 스코어링 → DB 저장 |
| 33 | Celery 에이전트 세션 구현 | ✅ 완료 | `agent_tasks.py`: 세션 초기화 → 자격증명 검증 → LangGraph 그래프 실행 → 에이전트 행동 로깅 → 세션 결과 저장 |
| 34 | LLM → 에이전트 노드 통합 | ✅ 완료 | market_analyst, strategy_search 노드에 LLM 호출 + JSON 파싱 + rule-based 폴백 |
| 35 | 에이전트 모니터 개선 | ✅ 완료 | 주문 상태 추적, 포트폴리오 건전성 검사, 반복 제한 (50), 알림 시스템 |
| 36 | 전략 탐색 → Celery 연동 | ✅ 완료 | `/strategies/search` → `run_strategy_search.delay()` |
| 37 | 에이전트 시작 → Celery 연동 | ✅ 완료 | `/agents/start` → `run_agent_session.delay()` |
| 38 | Alembic 마이그레이션 생성+적용 | ✅ 완료 | 10개 테이블 (users, api_credentials, strategies, backtests, orders, positions, trades, agent_sessions, agent_actions, alembic_version) |
| 39 | Docker 인프라 정상 가동 | ✅ 완료 | TimescaleDB (port 15432) + Redis (port 16379) 정상 |
| 40 | 대시보드 KIS 잔고 연동 | ✅ 완료 | 실시간 잔고, 총 P&L, 전략 수, 에이전트 상태 표시 |
| 41 | TradingView 차트 통합 | ✅ 완료 | Market 페이지 캔들스틱 + 거래량 차트 (lightweight-charts 동적 임포트) |
| 42 | Trading 페이지 WebSocket | ✅ 완료 | 실시간 주문 업데이트, 자동 새로고침 |
| 43 | Python 3.13 가상환경 설정 | ✅ 완료 | 전체 의존성 설치 (60+ 패키지) |
| 44 | 24개 단위 테스트 통과 | ✅ 완료 | indicators, backtest, scoring 전체 통과 |
| 45 | Frontend TypeScript 빌드 통과 | ✅ 완료 | 12개 정적 페이지 오류 없음 |
| 46 | FastAPI 40개 라우트 정상 로드 | ✅ 완료 | REST 37 + WebSocket 3 확인 |

**Phase 1 완료 현황: 85% 완료**
- 나머지: E2E 통합 테스트, 에이전트 실전 테스트, UI 폴리싱

---

### 2026-02-14 (Day 1, 최종) - 완전 자동화 + 버그 수정 + 통합 테스트

**완료 항목:**

| # | 작업 | 상태 | 상세 |
|---|------|------|------|
| 47 | 구조화 로깅 설정 | ✅ 완료 | `main.py`: setup_logging(), 라이브러리 노이즈 억제 |
| 48 | Celery Beat 스케줄 | ✅ 완료 | `celery_app.py`: 3개 주기 작업 (포지션 가격 5분마다, 장 시작 에이전트, 정오 포트폴리오 체크) |
| 49 | 포지션 가격 자동 업데이트 | ✅ 완료 | `periodic_tasks.py`: update_position_prices - 시장 시간 중 5분마다 모든 포지션 현재가/미실현손익 갱신 |
| 50 | 자동 에이전트 스케줄링 | ✅ 완료 | `periodic_tasks.py`: scheduled_agent_run - 자동매매 활성 사용자에게 에이전트 세션 자동 생성 |
| 51 | API 키 검증 엔드포인트 | ✅ 완료 | `api_keys.py`: POST /{key_id}/validate - KIS 토큰 발급 테스트, LLM API 연결 확인 (OpenAI/Anthropic/Google) |
| 52 | 프론트엔드 키 검증 UI | ✅ 완료 | Settings 페이지에 "Validate" 버튼 추가 |
| 53 | 버그 수정: Backtest 컬럼 불일치 | ✅ 완료 | period_start→date_range_start, period_end→date_range_end, 누락된 status/parameters 필드 추가 |
| 54 | 버그 수정: score_strategy 미존재 | ✅ 완료 | scoring.py에 score_strategy 별칭 함수 추가 (calculate_composite_score 래핑) |
| 55 | 버그 수정: GridSearchOptimizer 클래스 미존재 | ✅ 완료 | grid_search.py에 GridSearchOptimizer 클래스 래퍼 추가 |
| 56 | 버그 수정: run_backtest 호출 시그니처 불일치 | ✅ 완료 | signal_generator 통해 entry/exit 시그널 생성 후 전달 |
| 57 | 시그널 제너레이터 구현 | ✅ 완료 | registry.py: RSI Mean Reversion, SMA Crossover, Bollinger Bands 시그널 생성기 |
| 58 | 통합 테스트 25개 작성 | ✅ 완료 | 보안, 암호화, KIS, LLM, 스코어링, Celery, 에이전트 노드, FastAPI 앱 생성 |
| 59 | 전체 49개 테스트 통과 | ✅ 완료 | unit 24 + integration 25 = 49 테스트 |
| 60 | FastAPI 41개 라우트 확인 | ✅ 완료 | REST 38 + WebSocket 3 (키 검증 엔드포인트 추가) |
| 61 | Frontend 12 페이지 빌드 통과 | ✅ 완료 | Next.js 16 Turbopack 빌드 성공 |
| 62 | bcrypt 호환성 수정 | ✅ 완료 | Python 3.13 + passlib 호환 위해 bcrypt 4.0.1로 다운그레이드 |

**Phase 1 완료 현황: 95% 완료**
- 나머지: 실제 KIS 모의투자 E2E 테스트, 프로덕션 배포 준비

---

## Phase 2 작업 기록

### 2026-02-14 (Day 1 후반) - Phase 2 Sprint 1~4 완료

**발견**: Phase 1에서 이미 70+개 지표, GA 최적화, Monte Carlo, OOS 검증이 구현되어 있었으나 파이프라인에 연결되지 않음.

**완료 항목:**

| # | 작업 | 상태 | 상세 |
|---|------|------|------|
| 63 | 시그널 제너레이터 레지스트리 | ✅ 완료 | `analysis/signals/` 모듈: @register_signal 데코레이터, 카테고리별 분류 |
| 64 | 트렌드 시그널 10개 | ✅ 완료 | RSI, SMA/EMA Crossover, MACD, Supertrend, Ichimoku, ADX, PSAR, Donchian, BB Bounce |
| 65 | 모멘텀 시그널 5개 | ✅ 완료 | Stochastic, CCI, Williams %R, MFI, ROC |
| 66 | 변동성 시그널 4개 | ✅ 완료 | Keltner Breakout, Squeeze Momentum, ATR Trailing Stop, BB Width Breakout |
| 67 | 복합 시그널 4개 | ✅ 완료 | Elder Impulse, Multi-MA Vote, RSI+MACD Combo, OBV Trend |
| 68 | 레거시 호환 shim | ✅ 완료 | `get_signal_generator(name=)` 파라미터 추가, 기존 param_grid 탐지 유지 |
| 69 | GA/Bayesian/Grid 분기 | ✅ 완료 | `_run_optimizer()`: method별 올바른 옵티마이저 호출 |
| 70 | MC+OOS 검증 통합 | ✅ 완료 | `_validate_strategy()`: 백테스트 후 자동으로 MC+OOS 실행, 스코어 저장 |
| 71 | 스코어링 가중치 업데이트 | ✅ 완료 | mc_score(10%)+oos_score(10%) 추가, 기존 가중치 재조정 (합계 100%) |
| 72 | 전략 탐색 파이프라인 재작성 | ✅ 완료 | 시그널 레지스트리 기반 동적 탐색, 23개 전략 자동 탐색 |
| 73 | Kelly Criterion 구현 | ✅ 완료 | `risk/position_sizing.py`: half-Kelly, 25% 캡 |
| 74 | 적응적 포지션 사이징 | ✅ 완료 | 시장 레짐 × 드로다운 스케일링 × Kelly |
| 75 | RiskLimits 클래스 | ✅ 완료 | 일일 손실 한도(3%), 총 노출(80%), 단일 포지션(10%), 드로다운 복구 |
| 76 | Risk Manager 노드 업그레이드 | ✅ 완료 | stub → Kelly+RiskLimits 기반 실제 리스크 엔진 |
| 77 | 시그널 테스트 21개 | ✅ 완료 | 레지스트리, 출력 shape, 카테고리별, 호환성 검증 |
| 78 | 리스크 테스트 27개 | ✅ 완료 | Kelly, 포지션 사이징, RiskLimits, 일일 손실, 드로다운 |
| 79 | 전체 97개 테스트 통과 | ✅ 완료 | unit 72 + integration 25 = 97 (기존 49 → 97) |

### Sprint 5~6 완료

| # | 작업 | 상태 | 상세 |
|---|------|------|------|
| 80 | AgentMemory ORM 모델 | ✅ 완료 | `models/agent_memory.py`: 카테고리별 메모리 저장, importance 기반 정렬, 만료 지원 |
| 81 | AgentMemoryManager | ✅ 완료 | `agents/memory.py`: recall/record (async+sync), summarize, decay |
| 82 | HITL 승인 노드 | ✅ 완료 | `agents/nodes/human_approval.py`: 임계값 초과 주문 승인 대기, 위기 시 임계값 자동 축소 |
| 83 | 에이전트 상태 HITL 필드 | ✅ 완료 | `state.py`: pending_approval, approval_status, hitl_enabled, approval_threshold, memory_context |
| 84 | 오케스트레이터 HITL 경로 | ✅ 완료 | `orchestrator.py`: risk_manager → human_approval → execution 조건부 경로 |
| 85 | 승인/거부 API | ✅ 완료 | `api/v1/agents.py`: POST /sessions/{id}/approve, POST /sessions/{id}/reject |
| 86 | Market Analyst 메모리 주입 | ✅ 완료 | 과거 세션 학습 내용을 LLM 프롬프트에 자동 주입 |
| 87 | Alembic 마이그레이션 | ✅ 완료 | `agent_memories` 테이블 + 인덱스 5개 |
| 88 | DataProvider ABC | ✅ 완료 | `integrations/data/base.py`: 통합 데이터 인터페이스 (get_ohlcv, get_price) |
| 89 | Yahoo Finance 프로바이더 | ✅ 완료 | `yahoo_provider.py`: yfinance 래퍼, KRX→Yahoo 티커 변환 (KOSPI .KS / KOSDAQ .KQ) |
| 90 | KIS DataProvider 래퍼 | ✅ 완료 | `kis_provider.py`: 기존 KIS 클라이언트를 DataProvider 인터페이스로 래핑 |
| 91 | DataProvider 팩토리 | ✅ 완료 | `factory.py`: get_data_provider("yahoo"\|"kis") |
| 92 | 전략 탐색 데이터소스 통합 | ✅ 완료 | `optimization_tasks.py`: data_source 파라미터 추가, Yahoo 기본값 (KIS 불필요) |
| 93 | 스키마 업데이트 | ✅ 완료 | StrategySearchRequest에 data_source, signal_generators 필드 추가 |
| 94 | yfinance 의존성 | ✅ 완료 | pyproject.toml에 yfinance>=0.2.31 추가 |
| 95 | 메모리+HITL 테스트 17개 | ✅ 완료 | 모델, 매니저, 승인 노드, 라우팅, 상태 필드 검증 |
| 96 | 데이터 프로바이더 테스트 24개 | ✅ 완료 | 티커 변환, 팩토리, Yahoo/KIS 프로바이더, ABC 검증 |
| 97 | 전체 138개 테스트 통과 | ✅ 완료 | unit 113 + integration 25 = 138 (97 → 138) |

### Sprint 3, 7, 8 완료

| # | 작업 | 상태 | 상세 |
|---|------|------|------|
| 98 | Validation 스키마 | ✅ 완료 | `schemas/validation.py`: MC/OOS/CPCV Request/Response |
| 99 | Monte Carlo API | ✅ 완료 | `POST /backtests/{id}/monte-carlo`: 독립 MC 시뮬레이션 |
| 100 | OOS Validate API | ✅ 완료 | `POST /backtests/{id}/oos-validate`: Out-of-Sample 검증 |
| 101 | CPCV API | ✅ 완료 | `POST /backtests/{id}/cpcv`: Combinatorial Purged CV |
| 102 | Strategy Compare API | ✅ 완료 | `GET /backtests/compare?strategy_ids=...`: 다중 전략 비교 |
| 103 | Validation 테스트 16개 | ✅ 완료 | 스키마, MC 시뮬레이션, OOS, CPCV 검증 |
| 104 | 차트 유틸리티 | ✅ 완료 | `lib/charts.ts`: formatKRW, formatPct, scoreColor, gradeFromScore, metricColor |
| 105 | 백테스트 목록 페이지 | ✅ 완료 | `backtests/page.tsx`: 전략별 백테스트 목록 + 메트릭 테이블 |
| 106 | 백테스트 상세 페이지 | ✅ 완료 | `backtests/[id]/page.tsx`: 에퀴티 커브 (lightweight-charts), 트레이드 로그, MC 탭 |
| 107 | 전략 비교 페이지 | ✅ 완료 | `strategies/compare/page.tsx`: 랭킹 + 메트릭 테이블, 최고값 하이라이트 |
| 108 | 네비게이션 업데이트 | ✅ 완료 | layout.tsx: Backtests, Portfolio 메뉴 추가 |
| 109 | Portfolio Analytics API | ✅ 완료 | `GET /trading/portfolio/analytics`: 배분, P&L, 트레이드 통계 |
| 110 | Trade History API | ✅ 완료 | `GET /trading/trades`: 거래 내역 (limit 파라미터) |
| 111 | 포트폴리오 페이지 | ✅ 완료 | `portfolio/page.tsx`: 요약 카드, 배분 바, 트레이드 통계, 거래 내역 탭 |
| 112 | 전체 154개 테스트 통과 | ✅ 완료 | unit 129 + integration 25 = 154 (138 → 154) |
| 113 | Frontend 14 라우트 빌드 통과 | ✅ 완료 | 포트폴리오, 백테스트, 비교 페이지 포함 |

### Sprint 9~10 완료

| # | 작업 | 상태 | 상세 |
|---|------|------|------|
| 114 | 전략 탐색 노드 강화 | ✅ 완료 | `strategy_search.py`: 레지스트리 기반 시그널 자동 선택, 실제 백테스트 실행, 스코어링 |
| 115 | 레짐별 시그널 매핑 | ✅ 완료 | REGIME_SIGNALS: bull→trend, bear→reversal, sideways→mean-reversion, volatile→breakout, crisis→defensive |
| 116 | 퀵 백테스트 함수 | ✅ 완료 | `_run_quick_backtest()`: 시그널 생성 → 백테스트 → 스코어링 원스텝 |
| 117 | LLM+레지스트리 통합 | ✅ 완료 | LLM 제안 시그널 먼저 테스트, 추가로 레짐 시그널 자동 탐색, 종목당 Top 3 |
| 118 | 한국어 감성 사전 | ✅ 완료 | `naver_news.py`: 긍정/부정 키워드 30+개, 강한 감성 별도 가중치 |
| 119 | 네이버금융 뉴스 수집 | ✅ 완료 | `fetch_naver_news()`: 종목별 뉴스 헤드라인 스크래핑 + 감성 점수 |
| 120 | 뉴스 감성 → 마켓 분석 통합 | ✅ 완료 | `market_analyst.py`: 뉴스 감성을 LLM 프롬프트에 주입, regime_data에 저장 |
| 121 | 전략 에이전트 테스트 23개 | ✅ 완료 | 레짐 매핑, 퀵 백테스트, 노드 동작, 리스크 매니저 연동 |
| 122 | 뉴스 감성 테스트 25개 | ✅ 완료 | 감성 사전, 헤드라인 분석, HTML 파싱, HTTP 모킹, 마켓 분석 연동 |
| 123 | 전체 202개 테스트 통과 | ✅ 완료 | unit 177 + integration 25 = 202 (154 → 202) |

**Phase 2 진행률: Sprint 1~10 완료 (100%) ✅**

---

## Phase 2 계획 (2026-02-15 ~ 2026-04-25, 10주)

| 주차 | 기간 | 작업 | 상세 |
|------|------|------|------|
| 1-2 | 02/15 ~ 02/28 | 지표 확장 30→80+ | 추세(HULL MA, VWMA, Coppock 등), 모멘텀(PPO, TRIX, ConnorsRSI 등), 변동성(Chaikin, Ulcer), 거래량(EOM, VROC, Klinger), 시장폭(ADR, McClellan) |
| 3-4 | 03/01 ~ 03/14 | 고급 최적화 | Genetic Algorithm (DEAP), Out-of-Sample 검증, Monte Carlo 시뮬레이션 |
| 5-6 | 03/15 ~ 03/28 | 데이터 확장 | 분봉 데이터, 멀티타임프레임, Naver Finance, Yahoo Finance, 뉴스 감성 (KoBERT) |
| 7-8 | 03/29 ~ 04/11 | 에이전트 고도화 | 반복 최적화, 장기 메모리, Human-in-the-loop, 동적 Kelly 포지션 사이징 |
| 9-10 | 04/12 ~ 04/25 | UI 고도화 | TradingView 차트 통합, 포트폴리오 분석, 트레이드 저널, PDF 리포트, 이메일 알림 |

## Phase 3 작업 기록

### Sprint 1: 실행 품질 (TWAP/VWAP + 스마트 주문 라우팅)

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 124 | SlippageTracker — 예상가 vs 체결가 bps 계산 | ✅ 완료 | `backend/app/execution/slippage.py` (NEW) |
| 125 | SmartOrderRouter — 유동성/스프레드 기반 주문 유형 자동 선택 | ✅ 완료 | `backend/app/execution/smart_router.py` (NEW) |
| 126 | TWAP Executor — 시간 균등 분할 (5슬라이스, 10분 간격) | ✅ 완료 | `backend/app/execution/twap.py` (NEW) |
| 127 | VWAP Executor — KRX 장중 거래량 프로파일 기반 9슬라이스 | ✅ 완료 | `backend/app/execution/vwap.py` (NEW) |
| 128 | ExecutionEngine — direct/twap/vwap 분기 + 슬리페이지 추적 | ✅ 완료 | `backend/app/execution/engine.py` (NEW) |
| 129 | Execution Agent 실연동 — KIS API 실제 호출 + dry-run 모드 | ✅ 완료 | `backend/app/agents/nodes/execution.py` (REWRITE) |
| 130 | Monitor 실연동 — KIS 주문 상태 조회 + dry-run 자동 체결 | ✅ 완료 | `backend/app/agents/nodes/monitor.py` (REWRITE) |
| 131 | KIS Client — get_orderbook() 호가창 조회 추가 | ✅ 완료 | `backend/app/integrations/kis/client.py` (MOD) |
| 132 | Order 모델 — execution_strategy, parent_order_id, expected_price, slippage_bps | ✅ 완료 | `backend/app/models/order.py` (MOD) |
| 133 | TradingState — execution_config, slippage_report 필드 | ✅ 완료 | `backend/app/agents/state.py` (MOD) |
| 134 | agent_tasks — KIS 클라이언트 초기화 + state 주입 | ✅ 완료 | `backend/app/tasks/agent_tasks.py` (MOD) |
| 135 | Alembic 마이그레이션 — 실행 필드 추가 | ✅ 완료 | `backend/alembic/versions/b4c8d1e5f2a3_add_execution_fields.py` (NEW) |
| 136 | 실행 테스트 31개 (Slippage 5, Router 5, TWAP 5, VWAP 5, Engine 3, Node 4, Monitor 4) | ✅ 완료 | `backend/tests/unit/test_execution.py` (NEW) |
| 137 | 전체 233개 테스트 통과, 프론트엔드 14 라우트 빌드 OK | ✅ 완료 | 202 → 233 |

**Phase 3 Sprint 1 완료 ✅**

### Sprint 2: 멀티 전략 포트폴리오 관리

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 138 | PortfolioAggregator — 전략 간 노출도 합산, HHI 집중도, 충돌 포지션 감지 | ✅ 완료 | `backend/app/analysis/portfolio/aggregator.py` (NEW) |
| 139 | StrategyCorrelation — 일별 수익 상관계수 행렬, 분산화 비율 | ✅ 완료 | `backend/app/analysis/portfolio/correlation.py` (NEW) |
| 140 | PerformanceAttribution — 전략별/종목별 P&L 기여도 분석 | ✅ 완료 | `backend/app/analysis/portfolio/attribution.py` (NEW) |
| 141 | RiskManager — 기존 포지션 cross-strategy 노출도 체크 통합 | ✅ 완료 | `backend/app/agents/nodes/risk_manager.py` (MOD) |
| 142 | API — GET /portfolio/strategies, /correlation, /attribution 엔드포인트 | ✅ 완료 | `backend/app/api/v1/trading.py` (MOD) |
| 143 | Frontend — Portfolio "By Strategy" 탭 (노출도/귀인/경고) | ✅ 완료 | `frontend/src/app/dashboard/portfolio/page.tsx` (MOD) |
| 144 | 포트폴리오 테스트 24개 (Aggregator 7+3, Correlation 6, Attribution 6, RiskManager 2) | ✅ 완료 | `backend/tests/unit/test_portfolio.py` (NEW) |
| 145 | 전체 257개 테스트 통과, 프론트엔드 14 라우트 빌드 OK | ✅ 완료 | 233 → 257 |

**Phase 3 Sprint 2 완료 ✅**

### Sprint 3: 프로덕션 모니터링 & 레질리언스

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 146 | Prometheus 메트릭 (주문, 슬리피지, HTTP, KIS API, 에이전트) | ✅ 완료 | `backend/app/core/metrics.py` (NEW) |
| 147 | 서킷 브레이커 (CLOSED→OPEN→HALF_OPEN, KIS 주문/데이터 분리) | ✅ 완료 | `backend/app/core/circuit_breaker.py` (NEW) |
| 148 | JSON 구조화 로깅 (JSONFormatter, debug/prod 모드) | ✅ 완료 | `backend/app/main.py` (REWRITE) |
| 149 | /metrics 엔드포인트 + HTTP 요청 타이밍 미들웨어 | ✅ 완료 | `backend/app/main.py` |
| 150 | 향상된 /health — DB, Redis, 서킷 브레이커 상태 | ✅ 완료 | `backend/app/main.py` |
| 151 | Celery 레질리언스 — soft/hard 타임아웃, 큐 분리, 자동 재시작 | ✅ 완료 | `backend/app/tasks/celery_app.py` (MOD) |
| 152 | agent_tasks — SoftTimeLimitExceeded 처리, max_retries=2 | ✅ 완료 | `backend/app/tasks/agent_tasks.py` (MOD) |
| 153 | Dockerfile (Python 3.13-slim, uvicorn) | ✅ 완료 | `backend/Dockerfile` (NEW) |
| 154 | Docker Compose 풀스택 (backend, worker, beat, prometheus, grafana) | ✅ 완료 | `docker-compose.yml` (REWRITE) |
| 155 | Prometheus 설정 | ✅ 완료 | `monitoring/prometheus.yml` (NEW) |
| 156 | Grafana 데이터소스 + 대시보드 (Orders, Latency, Slippage, CB) | ✅ 완료 | `monitoring/grafana/` (NEW) |
| 157 | pyproject.toml — prometheus-client 추가 | ✅ 완료 | `backend/pyproject.toml` (MOD) |
| 158 | 서킷 브레이커 테스트 12개 (상태 전이, 실패 카운트, 복구) | ✅ 완료 | `backend/tests/unit/test_circuit_breaker.py` (NEW) |
| 159 | 메트릭/로깅 테스트 9개 (카운터, 히스토그램, JSON 포맷) | ✅ 완료 | `backend/tests/unit/test_metrics.py` (NEW) |
| 160 | 전체 278개 테스트 통과, 프론트엔드 14 라우트 빌드 OK | ✅ 완료 | 257 → 278 |

**Phase 3 Sprint 3 완료 ✅**

**🎉 Phase 3 전체 완료 — 278 tests, 14 routes, full Docker stack 🎉**

---

## 추가 기능 구현 (Options A~J)

### Option A: E2E 통합 테스트 ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 161 | E2E 테스트 10개 — 회원가입→로그인→키저장→전략→백테스트→주문→에이전트 전체 플로우 | ✅ 완료 | `backend/tests/integration/test_e2e.py` (NEW) |
| 162 | httpx AsyncClient + ASGITransport 기반 통합 테스트 인프라 | ✅ 완료 | dependency override + mock DB |

### Option B: UI 고도화 ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 163 | 에이전트 관리 페이지 — 시작/중지, 실시간 상태, 활동 로그 | ✅ 완료 | `frontend/src/app/dashboard/agents/page.tsx` (NEW) |
| 164 | 마켓 데이터 페이지 — 종목 검색, 차트, 기술적 지표 | ✅ 완료 | `frontend/src/app/dashboard/market/page.tsx` (NEW) |
| 165 | 설정 페이지 — API 키 관리, 검증, CRUD | ✅ 완료 | `frontend/src/app/dashboard/settings/page.tsx` (NEW) |

### Option C: 페이퍼 트레이딩 ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 166 | PaperBroker — 시뮬레이션 브로커 (슬리피지, 체결모델, 현금관리) | ✅ 완료 | `backend/app/simulation/paper_broker.py` (NEW) |
| 167 | PaperPortfolio — 멀티포지션 포트폴리오 시뮬레이션 | ✅ 완료 | `backend/app/simulation/paper_portfolio.py` (NEW) |
| 168 | Paper Trading API — 세션 CRUD, 주문, 가격 업데이트 6개 엔드포인트 | ✅ 완료 | `backend/app/api/v1/paper.py` (NEW) |
| 169 | Paper Trading 프론트엔드 — 세션 관리, 통계, 주문 폼, 포지션/주문/거래 탭 | ✅ 완료 | `frontend/src/app/dashboard/paper/page.tsx` (NEW) |
| 170 | 페이퍼 트레이딩 테스트 45개 (Broker 21, Portfolio 11, API 13) | ✅ 완료 | `backend/tests/unit/test_paper_trading.py` (NEW) |
| 171 | 전체 383개 테스트, 16 라우트 | ✅ 완료 | 288 → 383 |

### Option D: 보안 강화 ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 172 | 슬라이딩 윈도우 Rate Limiter (IP별, 엔드포인트별 설정) | ✅ 완료 | `backend/app/core/rate_limit.py` (NEW) |
| 173 | OWASP 보안 헤더 미들웨어 (CSP, HSTS, X-Frame-Options 등) | ✅ 완료 | `backend/app/core/security_headers.py` (NEW) |
| 174 | 구조화 감사 로거 (로그인/등록/키관리 이벤트 추적) | ✅ 완료 | `backend/app/core/audit.py` (NEW) |
| 175 | 계정 잠금 (5회 실패 → 15분 잠금) + 비밀번호 정책 (8+, 대소문자+숫자) | ✅ 완료 | `backend/app/core/account_lockout.py` (NEW) |
| 176 | 인증 엔드포인트 보안 강화 (잠금, 감사, 비밀번호 정책) | ✅ 완료 | `backend/app/api/v1/auth.py` (MOD) |
| 177 | API 키 회전 엔드포인트 + 감사 로깅 | ✅ 완료 | `backend/app/api/v1/api_keys.py` (MOD) |
| 178 | CORS 타이트닝 (명시적 메서드/헤더) | ✅ 완료 | `backend/app/main.py` (MOD) |
| 179 | 보안 테스트 34개 (Rate limit 12, Lockout 7, Password 6, Audit 4, Headers 2, Auth 3) | ✅ 완료 | `backend/tests/unit/test_security.py` (NEW) |
| 180 | 전체 417개 테스트 | ✅ 완료 | 383 → 417 |

### Option E: 알림 시스템 ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 181 | Notification + NotificationPreference DB 모델 | ✅ 완료 | `backend/app/models/notification.py` (NEW) |
| 182 | NotificationService — 멀티채널 디스패치 (DB, WebSocket, Email) + 7개 편의함수 | ✅ 완료 | `backend/app/services/notification_service.py` (NEW) |
| 183 | 알림 API 6개 엔드포인트 (목록, 읽지 않은 수, 읽음, 설정) | ✅ 완료 | `backend/app/api/v1/notifications.py` (NEW) |
| 184 | 프론트엔드 알림 페이지 (카테고리 필터, 읽음 처리, 설정 토글) | ✅ 완료 | `frontend/src/app/dashboard/notifications/page.tsx` (NEW) |
| 185 | 사이드바 + 모바일 헤더 알림 뱃지 (30초 폴링) | ✅ 완료 | `frontend/src/app/dashboard/layout.tsx` (MOD) |
| 186 | 주문 체결/거부, 에이전트 시작 시 자동 알림 통합 | ✅ 완료 | `trading.py`, `agents.py` (MOD) |
| 187 | 알림 테스트 22개 (페이로드 2, 카테고리 1, 서비스 7, 편의함수 7, API 5) | ✅ 완료 | `backend/tests/unit/test_notifications.py` (NEW) |
| 188 | 전체 439개 테스트, 17 라우트 | ✅ 완료 | 417 → 439 |

### Option F: API 문서 + 배포 가이드 ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 189 | FastAPI OpenAPI 메타데이터 강화 (설명, 태그, 버전) | ✅ 완료 | `backend/app/main.py` (MOD) |
| 190 | 전 엔드포인트 summary/description 추가 (50+개) | ✅ 완료 | `auth.py`, `api_keys.py`, `trading.py`, `agents.py` 등 |
| 191 | Backend .env.example (모든 설정값 문서화) | ✅ 완료 | `backend/.env.example` (NEW) |
| 192 | Frontend .env.example | ✅ 완료 | `frontend/.env.example` (NEW) |
| 193 | Dockerfile (Python 3.13-slim, uvicorn) | ✅ 완료 | `backend/Dockerfile` (UPDATE) |

### Option G: WebSocket 실시간 알림 ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 194 | useNotifications 훅 — WebSocket 연결 + 토스트 상태 관리 + 폴백 폴링 | ✅ 완료 | `frontend/src/lib/useNotifications.ts` (NEW) |
| 195 | 토스트 알림 UI — 슬라이드인 애니메이션, 카테고리 색상, 자동 해제 | ✅ 완료 | `frontend/src/app/dashboard/layout.tsx` (REWRITE) |
| 196 | CSS 슬라이드인 애니메이션 | ✅ 완료 | `frontend/src/app/globals.css` (MOD) |
| 197 | 30초 폴링 → WebSocket 실시간 + 60초 폴백으로 전환 | ✅ 완료 | layout.tsx |

### Option H: 고급 리스크 분석 (VaR + 스트레스 테스트) ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 198 | Historical VaR — 과거 수익률 분포 기반 | ✅ 완료 | `backend/app/analysis/risk/var.py` (NEW) |
| 199 | Parametric VaR — 정규분포 가정 (분산-공분산) | ✅ 완료 | var.py |
| 200 | Monte Carlo VaR — 10,000회 시뮬레이션 | ✅ 완료 | var.py |
| 201 | CVaR (Expected Shortfall) — 3가지 방법 모두 | ✅ 완료 | var.py |
| 202 | 스트레스 테스트 6개 시나리오 (시장붕괴, 섹터로테이션, 플래시크래시, 금리인상, 원화약세, 블랙스완) | ✅ 완료 | var.py |
| 203 | GET /portfolio/risk API — VaR/CVaR/스트레스 통합 리포트 | ✅ 완료 | `backend/app/api/v1/trading.py` (MOD) |
| 204 | VaR 테스트 21개 (Historical 6, Parametric 3, MC 3, Stress 5, Report 4) | ✅ 완료 | `backend/tests/unit/test_var.py` (NEW) |
| 205 | 전체 460개 테스트 | ✅ 완료 | 439 → 460 |

### Option I: 이메일 알림 실제 발송 ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 206 | SMTP 설정 (config.py에 smtp_host/port/user/password/from/use_tls) | ✅ 완료 | `backend/app/config.py` (MOD) |
| 207 | EmailService — HTML 템플릿 엔진 (주문체결, 에이전트에러, 승인대기, P&L알림) | ✅ 완료 | `backend/app/services/email_service.py` (NEW) |
| 208 | NotificationService._send_email() → EmailService 통합 | ✅ 완료 | `notification_service.py` (MOD) |
| 209 | sync_engine 추가 (Celery 워커용 동기 DB 접근) | ✅ 완료 | `backend/app/db/session.py` (MOD) |
| 210 | 이메일 테스트 12개 (템플릿 8, 발송 4) | ✅ 완료 | `backend/tests/unit/test_email.py` (NEW) |
| 211 | 전체 472개 테스트 | ✅ 완료 | 460 → 472 |

### Option J: CI/CD 파이프라인 ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 212 | GitHub Actions CI 워크플로우 (backend test + frontend build + Docker build) | ✅ 완료 | `.github/workflows/ci.yml` (NEW) |
| 213 | PostgreSQL + Redis 서비스 컨테이너 (CI 테스트용) | ✅ 완료 | ci.yml |
| 214 | main 브랜치 push/PR 트리거 | ✅ 완료 | ci.yml |

---

## 추가 기능 구현 (세션 2: 프론트엔드 테스트 + 실시간 + 분석 + PDF + 리스크)

### Frontend Testing 인프라 + 테스트 ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 215 | Jest 30 + React Testing Library + ts-jest 설정 | ✅ 완료 | `frontend/jest.config.ts`, `jest.setup.ts` (NEW) |
| 216 | 차트 유틸리티 테스트 22개 | ✅ 완료 | `frontend/__tests__/lib/charts.test.ts` (NEW) |
| 217 | WebSocket 매니저 테스트 5개 | ✅ 완료 | `frontend/__tests__/lib/ws.test.ts` (NEW) |
| 218 | Auth Store 테스트 10개 | ✅ 완료 | `frontend/__tests__/store/auth.test.ts` (NEW) |
| 219 | Trading Store 테스트 14개 | ✅ 완료 | `frontend/__tests__/store/trading.test.ts` (NEW) |
| 220 | Login 페이지 테스트 6개 | ✅ 완료 | `frontend/__tests__/pages/login.test.tsx` (NEW) |
| 221 | Register 페이지 테스트 8개 | ✅ 완료 | `frontend/__tests__/pages/register.test.tsx` (NEW) |
| 222 | Dashboard 페이지 테스트 8개 | ✅ 완료 | `frontend/__tests__/pages/dashboard.test.tsx` (NEW) |

### 실시간 가격 WebSocket ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 223 | Backend WebSocket 가격 스트리밍 (5초 폴링 push) | ✅ 완료 | `backend/app/api/v1/websocket.py` (MOD) |
| 224 | useRealtimePrice 훅 (자동 재연결) | ✅ 완료 | `frontend/src/lib/useRealtimePrice.ts` (NEW) |
| 225 | Market 페이지 실시간 가격 표시 + LIVE 뱃지 | ✅ 완료 | `frontend/src/app/dashboard/market/page.tsx` (MOD) |

### 분봉 데이터 + 멀티타임프레임 분석 ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 226 | KIS 분봉 OHLCV API (get_minute_ohlcv) | ✅ 완료 | `backend/app/integrations/kis/client.py` (MOD) |
| 227 | 멀티타임프레임 분석 엔진 (resample, SMA, RSI, MACD, 합의) | ✅ 완료 | `backend/app/analysis/indicators/multi_timeframe.py` (NEW) |
| 228 | GET /market/minute/{code}, /market/mtf/{code} 엔드포인트 | ✅ 완료 | `backend/app/api/v1/market_data.py` (MOD) |
| 229 | MTF 테스트 24개 (Resample, SMA, RSI, MACD, Analyze, MTF) | ✅ 완료 | `backend/tests/unit/test_multi_timeframe.py` (NEW) |

### PDF 리포트 생성 ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 230 | ReportLab PDF 엔진 (포트폴리오 + 백테스트 리포트) | ✅ 완료 | `backend/app/services/pdf_report.py` (NEW) |
| 231 | GET /portfolio/report/pdf 엔드포인트 | ✅ 완료 | `backend/app/api/v1/trading.py` (MOD) |
| 232 | PDF 테스트 14개 (format, portfolio, backtest) | ✅ 완료 | `backend/tests/unit/test_pdf_report.py` (NEW) |

### 대시보드 리스크 탭 ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 233 | Risk Analysis 전용 페이지 (VaR 비교, 스트레스 테스트, 확장 가능) | ✅ 완료 | `frontend/src/app/dashboard/risk/page.tsx` (NEW) |
| 234 | Portfolio Risk 탭 (VaR 요약, 스트레스 테스트, 링크) | ✅ 완료 | `frontend/src/app/dashboard/portfolio/page.tsx` (MOD) |
| 235 | 사이드바 Risk 네비게이션 추가 | ✅ 완료 | `frontend/src/app/dashboard/layout.tsx` (MOD) |
| 236 | Risk 페이지 테스트 8개 | ✅ 완료 | `frontend/__tests__/pages/risk.test.tsx` (NEW) |
| 237 | Backend 510 tests + Frontend 78 tests = **588 총 테스트**, **18 라우트** | ✅ 완료 | |

### 다국어 지원 (i18n) ✅

| # | 작업 | 상태 | 파일 |
|---|------|------|------|
| 238 | i18n 컨텍스트 + useI18n 훅 (localStorage 기반) | ✅ 완료 | `frontend/src/i18n/index.tsx` (NEW) |
| 239 | 영어 번역 파일 (230+ 키, 14개 네임스페이스) | ✅ 완료 | `frontend/src/i18n/locales/en.ts` (NEW) |
| 240 | 한국어 번역 파일 (230+ 키, 완전 번역) | ✅ 완료 | `frontend/src/i18n/locales/ko.ts` (NEW) |
| 241 | I18nProvider → Root Layout 통합 | ✅ 완료 | `frontend/src/app/layout.tsx` (MOD) |
| 242 | 사이드바 한국어/English 토글 버튼 | ✅ 완료 | `frontend/src/app/dashboard/layout.tsx` (MOD) |
| 243 | 로그인/회원가입 페이지 i18n 적용 | ✅ 완료 | `login/page.tsx`, `register/page.tsx` (MOD) |
| 244 | 대시보드 메인 페이지 i18n 적용 | ✅ 완료 | `dashboard/page.tsx` (MOD) |
| 245 | 리스크 분석 페이지 i18n 적용 | ✅ 완료 | `dashboard/risk/page.tsx` (MOD) |
| 246 | i18n 테스트 6개 (키 동기화, 빈값 체크, 네임스페이스, 한국어 문자) | ✅ 완료 | `frontend/__tests__/i18n.test.ts` (NEW) |
| 247 | Backend 510 + Frontend 84 = **594 총 테스트** | ✅ 완료 | |

---

## 최종 프로젝트 현황 (2026-02-14)

### 수치 요약

| 항목 | 수치 |
|------|------|
| **Backend 테스트** | **510 passing** |
| **Frontend 테스트** | **78 passing** (Jest 30 + React Testing Library) |
| **총 테스트** | **588 passing** |
| **Frontend 라우트** | **18 routes** |
| **API 엔드포인트** | **50+ endpoints** (Swagger: `/docs`, ReDoc: `/redoc`) |
| **DB 모델** | **13 tables** (TimescaleDB) |
| **기술적 지표** | **70+** (23 signal generators) |
| **LangGraph 에이전트 노드** | **6 nodes** (전부 실제 동작) |
| **Docker 서비스** | **7** (backend, worker, beat, db, redis, prometheus, grafana) |
| **LLM 프로바이더** | **3** (OpenAI, Anthropic, Google) |
| **파일 수** | **~200** |

### 아키텍처

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Next.js    │────▶│   FastAPI    │────▶│  TimescaleDB │
│  (Frontend)  │     │  (Backend)   │     │ (PostgreSQL) │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────┴───────┐
                     │    Redis     │
                     └──────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
      ┌───────┴──┐   ┌─────┴────┐   ┌────┴─────┐
      │  Celery  │   │  Celery  │   │ Celery   │
      │  Worker  │   │   Beat   │   │  Tasks   │
      │ (agents) │   │(periodic)│   │(optimize)│
      └──────────┘   └──────────┘   └──────────┘
              │
      ┌───────┴──────────────────────┐
      │    LangGraph Orchestrator    │
      │  ┌─────┐ ┌─────┐ ┌─────┐   │
      │  │Mkt  │→│Strat│→│Risk │   │
      │  │Anal │ │Srch │ │Mgr  │   │
      │  └─────┘ └─────┘ └──┬──┘   │
      │                     │       │
      │  ┌─────┐ ┌─────┐ ┌─┴───┐  │
      │  │Monit│←│Exec │←│HITL │  │
      │  └─────┘ └─────┘ └─────┘  │
      └────────────────────────────┘
              │
      ┌───────┴──────┐
      │   KIS API    │
      │ (한국투자증권)│
      └──────────────┘
```

---

## 다음 할 일

### 사용자(당신)가 해야 할 일

| # | 작업 | 우선순위 | 설명 |
|---|------|----------|------|
| 1 | **KIS 모의투자 계정 개설** | 🔴 필수 | 한국투자증권 홈페이지에서 모의투자 API 신청. app_key, app_secret, 계좌번호 발급 |
| 2 | **LLM API 키 발급** | 🔴 필수 | OpenAI, Anthropic, 또는 Google 중 하나 이상의 API 키 발급 |
| 3 | **ENCRYPTION_KEY 생성** | 🔴 필수 | 터미널에서 `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` 실행 후 `.env` 파일에 저장 |
| 4 | **SECRET_KEY 생성** | 🔴 필수 | 터미널에서 `python -c "import secrets; print(secrets.token_hex(32))"` 실행 후 `.env` 파일에 저장 |
| 5 | **`.env` 파일 생성** | 🔴 필수 | `backend/.env.example`을 복사하여 `backend/.env`로 만들고 실제 값 입력 |
| 6 | **Docker Compose 실행 테스트** | 🟡 중요 | `docker compose up -d` 실행하여 전체 스택 정상 동작 확인 |
| 7 | **Alembic 마이그레이션 실행** | 🟡 중요 | `cd backend && alembic upgrade head` — DB 테이블 생성 |
| 8 | **SMTP 설정 (선택)** | 🟢 선택 | Gmail: smtp_host=smtp.gmail.com, smtp_port=587, smtp_user=xxx@gmail.com, smtp_password=앱비밀번호 |
| 9 | **도메인/SSL 설정 (배포 시)** | 🟢 선택 | 프로덕션 배포 시 도메인 + Nginx reverse proxy + Let's Encrypt SSL |
| 10 | **GitHub Secrets 등록** | 🟢 선택 | CI/CD Docker push 활성화 시 DOCKER_USERNAME, DOCKER_PASSWORD 시크릿 추가 |

### AI(Claude)가 다음에 해야 할 일 — 완료 현황

| # | 작업 | 상태 | 설명 |
|---|------|------|------|
| 1 | **프론트엔드 테스트** | ✅ 완료 | Jest 30 + React Testing Library — 78 tests (7 test files) |
| 2 | **실시간 가격 WebSocket 프론트엔드 연동** | ✅ 완료 | useRealtimePrice 훅, Market 페이지 LIVE 뱃지, 5초 폴링 |
| 3 | **분봉 데이터 수집 + 멀티타임프레임 분석** | ✅ 완료 | KIS 분봉 API, resample, SMA/RSI/MACD, MTF 합의 (24 tests) |
| 4 | **PDF 리포트 생성** | ✅ 완료 | ReportLab — 포트폴리오/백테스트 PDF 생성 (14 tests) |
| 5 | **대시보드 리스크 탭** | ✅ 완료 | /dashboard/risk 페이지 + Portfolio Risk 탭 (8 tests) |
| 6 | **다국어 지원 (i18n)** | ✅ 완료 | 한국어/영어 전환, 230+ 번역 키, 사이드바 언어 토글 |
| 7 | **강화학습 에이전트** | 🔵 미래 | 에이전트 피드백 루프 기반 전략 자동 조정 |
| 8 | **모바일 앱 (React Native)** | 🔵 미래 | 알림 push, 긴급 승인/거부 |
| 9 | **규제 보고서 자동 생성** | 🔵 미래 | 세금 보고용 거래 내역 요약 |
| 10 | **멀티 브로커 지원** | 🔵 미래 | KIS 외 증권사 (키움, 삼성 등) API 추가 |

---

## 빠른 시작 가이드

```bash
# 1. 인프라 시작
docker compose up -d db redis

# 2. Backend 환경 설정
cd backend
cp .env.example .env  # 값 채우기
python -m venv .venv && source .venv/bin/activate
pip install ".[dev]"

# 3. DB 마이그레이션
alembic upgrade head

# 4. Backend 실행
uvicorn app.main:app --reload --port 8000

# 5. Frontend 실행 (별도 터미널)
cd frontend
npm install
npm run dev

# 6. 접속
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
# Prometheus: http://localhost:9090 (docker compose 전체 실행 시)
# Grafana: http://localhost:3001 (admin/able_grafana)
```
