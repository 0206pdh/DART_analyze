# DART 기반 자기소개서 리서치 도우미

지원 기업을 검색하고, OpenDART 공시와 사용자가 제공한 채용공고·직무 정보를 함께 분석해 자기소개서의 방향과 근거를 제안하는 웹 서비스입니다.

현재 저장소는 구현 전 기획 단계입니다. 과도한 선행 설계보다 가장 위험한 가정부터 검증하는 문서를 담고 있습니다.

## 문서

- [제품 범위](docs/product-scope.md)
- [OpenDART API 조사](docs/opendart-api.md)
- [단계별 개발 계획](docs/phases.md)
- [Phase 0 검증 결과](docs/phase-0-findings.md)
- [ADR-0001: 모듈형 모놀리스](docs/adr/0001-modular-monolith.md)
- [ADR-0002: 채용공고 입력 방식](docs/adr/0002-job-posting-input.md)
- [ADR-0003: 근거 기반 생성](docs/adr/0003-evidence-grounded-generation.md)
- [OpenDART 인증키 발급](docs/dart-api-key.md)
- [ADR 전체 목록](docs/adr/README.md)

## 현재 결론

1. MVP는 모듈형 모놀리스로 시작합니다.
2. DART는 채용공고·직무 API가 아니므로, MVP의 채용공고는 사용자가 본문과 직무를 입력합니다.
3. 회사 검색은 `corpCode.xml`을 주기적으로 동기화한 로컬 인덱스로 처리합니다.
4. 최신 정기공시 검색과 구조화 재무 데이터부터 사용하고, 보고서 원문 파싱은 별도 기술 검증 후 편입합니다.
5. 생성 결과에는 접수번호, 보고서명, 접수일 등 출처를 붙이고 사실과 제안을 분리합니다.

## 프런트 프로토타입 실행

의존성 없는 정적 프로토타입이 `web/`에 있습니다. `web/index.html`을 직접 열거나 로컬 서버로 실행할 수 있습니다.

```powershell
python -m http.server 8080 --directory web
```

브라우저에서 <http://localhost:8080>을 엽니다. 현재 기업 검색과 분석은 UI 흐름을 확인하기 위한 예시이며 DART 백엔드는 아직 연결되지 않았습니다.

## Phase 0 백엔드

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python backend/scripts/sync_companies.py
uvicorn app.main:app --app-dir backend --reload
```

웹과 API는 <http://localhost:8000>에서 함께 제공됩니다. 헬스 체크는 <http://localhost:8000/api/health>, 회사 검색은 `/api/companies/search?q=삼성전자`에서 확인합니다. DART 실호출은 인증키 설정 후 실행합니다.

```powershell
$env:DART_API_KEY='발급받은 40자리 키'
python backend/scripts/dart_smoke.py
```

테스트:

```powershell
pytest
```

## Supabase(무료) + 읽기 전용 배포 준비

배포 런타임은 DART를 호출하지 않는다. 6개월 주기로 로컬/CI에서 시가총액 상위 상장사만
미리 수집해 Postgres에 넣고, 서버는 그 데이터만 읽는다.

### 1. 데이터 적재 (로컬 또는 CI, 6개월 주기)

```powershell
python -m pip install -e ".[dev,preload]"

# .env 의 DATABASE_URL 을 Supabase Session pooler(5432)로 설정.
#   postgresql+psycopg://postgres.<ref>:<PW>@aws-N-<region>.pooler.supabase.com:5432/postgres
#   (비밀번호에 @ 등 기호가 있으면 %40 처럼 URL 인코딩. Direct 연결 db.<ref>... 는
#    IPv6 전용이라 부하 시 끊기므로 pooler 를 쓴다.)

python -m alembic upgrade head
python backend/scripts/sync_companies.py            # 회사 원장 12만 건(검색용)
python backend/scripts/preload_listed.py --top 1000 # 시총 상위 1000개 공시·재무
```

프리로드는 중단해도 안전하며 재실행 시 이미 채운 기업은 건너뛴다. 연결이 끊기면 기업별로
3회 재시도한다. OpenDART 일일 한도(020) 초과 시 종료 코드 2로 멈추므로 24시간 뒤 다시 실행한다.
종목 목록은 기본적으로 FinanceDataReader로 받고, `--marketcap-csv` / `--codes-file` 로 대체 가능.
저장 섹션은 `회사의 개요`·`사업의 내용`·`경영진단`만 섹션당 5만 자로 잘라 보관한다.

### 2. Vercel 배포 (최초 1회 연결 후 git push 시 자동)

Vercel Python 런타임이 루트 `index.py` 의 `app` 을 자동 감지해 서버리스 함수로 실행하고
모든 요청을 FastAPI 로 보낸다(FastAPI 가 `/api/*` 와 정적 `web/` 를 함께 서빙). 별도
`vercel.json` 은 없다. `.python-version`(3.12), `.vercelignore`, `pyproject.toml` 로 구성.

Vercel 대시보드에서 GitHub 레포를 Import 하고 환경변수를 설정한다.

| 변수 | 값 |
|---|---|
| `DATABASE_URL` | Supabase **Transaction pooler(6543)** 문자열 (`...pooler.supabase.com:6543/postgres`, 스킴 `postgresql+psycopg://`) |
| `OPENAI_API_KEY` | 분석 생성용 |
| `READ_ONLY` | `true` |

`DART_API_KEY` 는 배포 서버에 넣지 않는다. 코드가 `:6543` 을 감지하면 커넥션 풀을 끄고
prepared statement 를 비활성화한다(`app/database.py`).

## 구현 시작 전 필요한 것

- OpenDART 인증키 (`DART_API_KEY`로 서버 환경변수에만 보관)
- 생성형 AI 공급자와 모델 결정
- MVP에서 지원할 채용공고 입력 예시 3~5개
