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

## 구현 시작 전 필요한 것

- OpenDART 인증키 (`DART_API_KEY`로 서버 환경변수에만 보관)
- 생성형 AI 공급자와 모델 결정
- MVP에서 지원할 채용공고 입력 예시 3~5개
