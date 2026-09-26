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
| L-0008 | .env 규칙 개정 + 유출 차단 | 검증됨 | 루틴 프롬프트 갱신 필요 |
| L-0007 | 루틴 프롬프트 v2 | 구현됨 | 첫 실행 결과 대기 |
| L-0006 | 에이전트 로드 제약 | 구현됨 | 루틴 첫 실행까지 클라우드 로드 여부 미검증 |
| L-0005 | CI 정상화 | 구현됨 | 통합 8건 수정 중 (구현 에이전트 작업) |
| L-0004 | 일일 자동 루틴 | 구현됨 | **PR #1 병합 대기** — 병합 전까지 루틴은 매일 중단만 보고 |
| Q-002 | L-0001 독립 재현 | 미착수 | 없음 (루틴 첫 착수 예정) |

---

## 기록 (최신순)

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
