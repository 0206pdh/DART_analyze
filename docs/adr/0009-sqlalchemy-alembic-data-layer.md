# ADR-0009: SQLAlchemy 2.x와 Alembic을 사용한다

- 상태: 채택
- 날짜: 2026-09-04

## 맥락

SQLite로 시작하지만 PostgreSQL 전환 가능성을 유지해야 한다. 회사, 공시, 분석, 문서 모델에는 관계와 트랜잭션이 필요하며 배포 환경에서 스키마 변경 이력을 재현해야 한다.

## 판단 기준

- SQLite와 PostgreSQL 지원
- 명시적인 트랜잭션과 쿼리 제어
- 타입 힌트 및 FastAPI와의 결합도
- 마이그레이션 성숙도
- 라이브러리 종속성과 학습 비용

## 비교

| 후보 | 장점 | 단점 | 평가 |
|---|---|---|---|
| SQLAlchemy 2.x + Alembic | 성숙한 ORM/Core, 두 DB 공식 dialect, 마이그레이션 표준 조합 | 설정과 개념이 비교적 많음 | 채택 |
| SQLModel + Alembic | Pydantic과 ORM 모델 결합, 코드량 감소 | API 스키마와 영속 모델 결합, 복잡한 매핑에서 제약 | 보류 |
| Django ORM | 마이그레이션과 관리도구 통합 | FastAPI와 이중 프레임워크, 현재 범위에 과함 | 제외 |
| 직접 SQL + 자체 migration | 완전한 제어, 의존성 감소 | DB 전환과 스키마 이력 관리 비용 증가 | 제외 |
| Peewee | 가볍고 배우기 쉬움 | 대규모 생태계와 고급 매핑에서 SQLAlchemy보다 약함 | 보류 |

## 결정

SQLAlchemy 2.x의 typed declarative 모델과 명시적 `Session`을 사용한다. Alembic revision을 배포 전에 실행하며 애플리케이션 시작 시 자동으로 테이블을 생성하지 않는다. API Pydantic 스키마와 DB 모델은 분리한다.

## 감수하는 단점

- 작은 모델에도 repository/session 코드가 필요하다.
- Alembic 자동생성 결과는 반드시 검토해야 한다.
- SQLite와 PostgreSQL의 동작 차이를 통합 테스트해야 한다.

## 재검토 조건

SQLAlchemy가 측정 가능한 성능 병목이 되면 해당 쿼리만 Core 또는 직접 SQL로 내린다. ORM 전체 교체는 하지 않는다.

