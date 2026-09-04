# Architecture Decision Records

ADR은 중요한 선택과 당시의 근거를 보존한다. 구현과 결정이 달라지면 기존 기록을 지우지 않고 새로운 ADR로 대체한다.

## 결정 목록

| 번호 | 결정 | 상태 |
|---|---|---|
| [0001](0001-modular-monolith.md) | 모듈형 모놀리스로 시작 | 채택 |
| [0002](0002-job-posting-input.md) | MVP 채용공고는 사용자 입력 | 채택 |
| [0003](0003-evidence-grounded-generation.md) | 생성 결과를 공시 근거에 연결 | 채택 |
| [0004](0004-python-fastapi-backend.md) | Python 3.13과 FastAPI 백엔드 | 채택 |
| [0005](0005-httpx-dart-client.md) | HTTPX 기반 DART 어댑터 | 채택 |
| [0006](0006-server-side-secrets.md) | 인증키는 서버 환경변수에서 관리 | 채택 |
| [0007](0007-recovering-dart-document-parser.md) | DART 원문은 복구 모드 XML 파서로 처리 | 채택 |
| [0008](0008-sqlite-initial-database.md) | 초기 운영 DB는 SQLite | 채택 |
| [0009](0009-sqlalchemy-alembic-data-layer.md) | SQLAlchemy 2.x와 Alembic | 채택 |
| [0010](0010-single-server-deployment.md) | 단일 소형 서버 배포 | 채택 |
| [0011](0011-dart-cache-strategy.md) | DART 데이터 온디맨드 캐시 | 채택 |
| [0012](0012-company-search-sql.md) | 회사 검색은 관계형 DB 문자열 검색 | 채택 |
| [0013](0013-raw-document-file-storage.md) | 원문 ZIP은 파일시스템 저장 | 채택 |
| [0014](0014-structured-financial-data.md) | 재무 수치는 구조화 재무 API 우선 | 채택 |
| [0015](0015-openai-model-and-responses-api.md) | GPT-5.4 mini와 Responses API 구조화 출력 | 채택 |
| [0016](0016-analysis-privacy-and-cost-boundaries.md) | 모델 전송량과 저장 범위 최소화 | 채택 |
| [0017](0017-synchronous-analysis-execution.md) | Phase 2 분석 동기 처리 | 채택 |

## 아직 결정하지 않은 항목

| 항목 | 결정 시점 | 비교할 후보 |
|---|---|---|
| 보고서 검색 | 원문 파싱 평가 후 | 섹션/키워드 검색, PostgreSQL FTS, 임베딩 검색 |
| 인증 | 사용자 문서 저장 직전 | 익명 로컬, 이메일 링크, OAuth |
| 배포 플랫폼 | 첫 공개 배포 직전 | 운영비, 서울 리전, 비밀관리, DB 지원 기준 비교 |

미결정 항목은 구현 직전에 ADR을 추가한다. 후보를 평가하지 않고 라이브러리부터 설치하지 않는다.

## ADR 작성 기준

모든 신규 ADR에는 다음을 포함한다.

1. 상태와 날짜
2. 문제와 제약
3. 판단 기준
4. 실질적인 비교 후보와 비교표
5. 선택 및 선택 이유
6. 감수하는 단점
7. 재검토 조건
