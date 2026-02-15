# ABLE - AI-Based Leveraged Exchange

> AI 기반 자동매매 트레이딩 플랫폼 (한국투자증권 KIS API 연동)

## 프로젝트 현황 (2026-02-15)

- **백엔드**: Python 146개 모듈 / FastAPI + SQLAlchemy + Celery
- **프론트엔드**: TypeScript 41개 모듈 / Next.js 16.1.6 + Tailwind
- **테스트**: 백엔드 664개 + 프론트엔드 180개 = **844개 테스트 통과**
- **빌드**: 18개 라우트 정상

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (Next.js :3000)                               │
│  18 routes / WebSocket 실시간 시세 / i18n (한/영)       │
└────────────────────┬────────────────────────────────────┘
                     │ REST API + WebSocket
┌────────────────────▼────────────────────────────────────┐
│  Backend (FastAPI :8000)                                │
│  11 API 모듈 / JWT 인증 / AES-256 자격증명 암호화      │
├─────────────────────────────────────────────────────────┤
│  Celery Worker (agents, periodic 큐)                    │
│  7 태스크 / LangGraph 에이전트 오케스트레이션           │
├─────────────────────────────────────────────────────────┤
│  Celery Beat (스케줄러)                                 │
│  아침 브리핑 / NXT 에이전트 / 가격 업데이트 / 점심 점검│
└────────┬──────────────┬─────────────────────────────────┘
         │              │
┌────────▼──────┐ ┌─────▼──────┐
│ PostgreSQL    │ │ Redis      │
│ (TimescaleDB) │ │ (Celery    │
│ :15432        │ │  Broker)   │
└───────────────┘ │ :16379     │
                  └────────────┘
         │
┌────────▼──────────────────┐
│  외부 API                 │
│  - 한국투자증권 KIS API   │
│  - OpenAI GPT-4o          │
│  - DeepSeek AI            │
│  - yfinance (시장 데이터) │
│  - 한국 뉴스 RSS          │
└───────────────────────────┘
```

---

## API 엔드포인트 (11개 모듈)

| 모듈 | Prefix | 주요 기능 |
|------|--------|-----------|
| auth | `/auth` | 회원가입, 로그인, JWT 토큰 갱신 |
| api_keys | `/keys` | KIS/LLM API 자격증명 관리 (AES-256 암호화) |
| strategies | `/strategies` | 전략 CRUD, 자동매매 활성화/비활성화 |
| backtests | `/backtests` | 백테스트 실행, 결과 조회 |
| trading | `/trading` | 주문 실행 (TWAP/VWAP/직접) |
| agents | `/agents` | AI 에이전트 세션 관리 |
| market_data | `/market` | 시세, OHLCV, 데일리 리포트, 장마감 리포트 |
| websocket | `/ws` | 실시간 시세 (1초), 트레이딩, 에이전트 알림 |
| paper | `/paper` | 모의투자 (페이퍼 트레이딩) |
| notifications | `/notifications` | 알림 관리 (이메일/웹) |
| analysis | `/analysis` | 3-Layer AI 분석 (DeepSeek + GPT-4o) |

---

## 프론트엔드 라우트 (18개)

| 라우트 | 페이지 |
|--------|--------|
| `/` | 랜딩 페이지 |
| `/login`, `/register` | 인증 |
| `/dashboard` | 대시보드 홈 |
| `/dashboard/market` | 마켓 인텔리전스 (4탭: 브리핑/장마감/보관함/검색) |
| `/dashboard/strategies` | 전략 목록 (종목별 그룹, AI 탐색) |
| `/dashboard/strategies/[id]` | 전략 상세 (6탭: 성과/에쿼티/거래/검증/파라미터/AI) |
| `/dashboard/strategies/compare` | 전략 비교 |
| `/dashboard/backtests` | 백테스트 목록 |
| `/dashboard/backtests/[id]` | 백테스트 상세 |
| `/dashboard/trading` | 실시간 트레이딩 |
| `/dashboard/paper` | 모의투자 |
| `/dashboard/portfolio` | 포트폴리오 |
| `/dashboard/risk` | 리스크 대시보드 |
| `/dashboard/agents` | AI 에이전트 세션 |
| `/dashboard/notifications` | 알림 |
| `/dashboard/settings` | 설정 (API 키, 알림, 언어) |

---

## 핵심 기능

### 1. 데일리 마켓 인텔리전스
- **아침 브리핑** (06:30 KST): 미장 분석 → 테마 감지 → 한국 관심종목 추출 → GPT-4o AI 브리핑
- **장마감 리포트** (16:00 KST, 코스피 거래일만): 한국 시장 정리 + AI 분석
- **리포트 보관함**: 게시판 형식으로 과거 리포트 열람 (날짜/유형/헤드라인/심리)
- **뉴스 통합**: yfinance 미국 뉴스 + 한국 RSS (매일경제, 한경, 연합뉴스)

### 2. AI 전략 탐색 & 최적화
- **24개 매매 전략**: 추세추종(9) + 모멘텀(6) + 변동성(4) + 복합(5)
- **최적화 방법**: Grid Search / Genetic / Bayesian
- **3중 검증**: Walk-Forward Analysis + Monte Carlo + Out-of-Sample
- **등급 시스템**: A+ ~ D (종합점수 기반)
- **중복 방지**: user_id + strategy_type + stock_code unique constraint + upsert

### 3. 자동매매 시스템
```
버튼 클릭 → is_auto_trading=True
    ↓
Celery Beat (08:00 NXT 프리마켓 / 12:30 점심)
    ↓
scheduled_agent_run → 활성 전략 유저 찾기
    ↓
LangGraph 트레이딩 그래프 (시장분석 → 시그널 → 리스크 → 주문)
    ↓
ExecutionEngine (SmartOrderRouter → TWAP/VWAP/직접)
    ↓
KIS API → 한국투자증권 실주문
```

### 4. 3-Layer AI 분석
- **Layer 1**: DeepSeek 기술적 분석 (차트 패턴, 지지/저항)
- **Layer 2**: GPT-4o 뉴스 감성 분석 (실시간 뉴스 크롤링)
- **Layer 3**: 종합 판단 (매수/매도/관망 + 확신도)

### 5. 주문 실행 엔진
- **SmartOrderRouter**: 주문 크기/유동성에 따라 자동 전략 선택
- **TWAP**: 시간 균등 분할 주문
- **VWAP**: 거래량 가중 분할 주문
- **슬리피지 추적**: 예상가 vs 체결가 비교

---

## Celery 스케줄 (모두 .env로 조정 가능)

| 시간 (KST) | 태스크 | .env 변수 |
|-------------|--------|-----------|
| 06:30 (평일) | 아침 마켓 브리핑 | `SCHEDULE_BRIEFING_HOUR/MINUTE` |
| 08:00 (평일) | NXT 프리마켓 에이전트 | `SCHEDULE_AGENT_OPEN_HOUR/MINUTE` |
| 매 1분 (08-16시) | 포지션 가격 업데이트 | `SCHEDULE_PRICE_INTERVAL_MINUTES` |
| 12:30 (평일) | 점심 포트폴리오 점검 | `SCHEDULE_AGENT_MIDDAY_HOUR/MINUTE` |

---

## 기술 스택

| 계층 | 기술 |
|------|------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS, lightweight-charts |
| Backend | FastAPI, SQLAlchemy 2.0 (async), Pydantic v2 |
| AI/ML | LangGraph, OpenAI GPT-4o, DeepSeek, pandas, numpy |
| Database | PostgreSQL 16 (TimescaleDB), Alembic migrations |
| Queue | Celery 5, Redis 7 |
| 증권 API | 한국투자증권 KIS REST + WebSocket |
| 인증 | JWT (access + refresh), AES-256 자격증명 암호화 |
| 테스트 | pytest (664), Jest + React Testing Library (180) |

---

## 실행 방법

```bash
# 인프라 (Docker)
docker compose up -d  # PostgreSQL + Redis

# 백엔드
cd backend
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 프론트엔드
cd frontend
npm run dev  # :3000

# Celery (자동매매 + 스케줄)
cd backend
celery -A app.tasks.celery_app worker -Q agents,periodic -l info \
  --include=app.tasks.periodic_tasks,app.tasks.agent_tasks,app.tasks.optimization_tasks
celery -A app.tasks.celery_app beat -l info

# 테스트
cd backend && python -m pytest tests/ -x -q     # 664 tests
cd frontend && npx jest                           # 180 tests
cd frontend && npx next build                     # 18 routes
```

---

## 최근 커밋 이력

| 커밋 | 내용 |
|------|------|
| `5d119f2` | 트레이딩 스케줄 설정화 + NXT 프리마켓 08:00 대응 |
| `280d101` | 전략 중복 버그 수정 (unique constraint + upsert) |
| `272bbeb` | 리포트 보관함 탭 (게시판 형식 아카이브) |
| `a607181` | GPT-4o 브리핑, 뉴스 통합, 장마감 리포트, 전략 설명 |
| `c49555b` | 데일리 마켓 인텔리전스 시스템 |
| `ead1d31` | AI 분석 결과 DB 저장 + 이력 |
| `26921b9` | 전략 페이지 프로 UI 리디자인 + 종목 필터링 |
| `aae0846` | 3-Layer 하이브리드 AI 분석 (DeepSeek + GPT-4o) |
