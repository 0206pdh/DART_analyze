# OpenDART API 조사

조사일: 2026-09-04  
공식 개발가이드: <https://opendart.fss.or.kr/guide/main.do>

## 결론

OpenDART만으로 기업 검색, 공시 검색, 보고서 원문 다운로드, 재무제표 조회는 가능하다. 채용공고나 직무 정보는 제공하지 않으므로 별도 입력 또는 합법적인 외부 연동이 필요하다.

OpenDART 인증키는 40자리이며 모든 호출에 `crtfc_key`로 전달한다. 키가 브라우저에 노출되지 않도록 모든 DART 호출은 서버에서 수행한다.

## MVP에 필요한 API

| 목적 | 엔드포인트 | 주요 입력 | 응답/사용법 |
|---|---|---|---|
| 회사명 검색용 원장 | `GET /api/corpCode.xml` | `crtfc_key` | ZIP 바이너리 안의 XML. `corp_code`, `corp_name`, `corp_eng_name`, `stock_code`, `modify_date`를 로컬 DB에 동기화 |
| 기업 상세 | `GET /api/company.json` | `crtfc_key`, `corp_code` | 대표자, 주소, 업종코드, 결산월 등 기업개황 |
| 공시 검색 | `GET /api/list.json` | 키, `corp_code`; 날짜·공시유형·페이지 옵션 | 정기공시는 `pblntf_ty=A`, 최종본 위주 화면은 `last_reprt_at=Y`; 최대 페이지 크기 100 |
| 공시 원문 | `GET /api/document.xml` | 키, `rcept_no` | ZIP 바이너리. 내부 XML을 정제해 보고서 본문 섹션 추출 |
| 전체 재무제표 | `GET /api/fnlttSinglAcntAll.json` | 키, 회사, 사업연도, 보고서코드, 개별/연결 구분 | 모든 계정. 원문보다 안정적인 수치 분석에 우선 사용 |
| 주요 재무지표 | `GET /api/fnlttSinglIndx.json` | 키, 회사, 사업연도, 보고서코드, 지표분류 | 성장성·수익성 등 요약 지표 후보 |

기본 URL은 `https://opendart.fss.or.kr`이다.

## 보고서 코드

| 코드 | 보고서 |
|---|---|
| `11011` | 사업보고서 |
| `11012` | 반기보고서 |
| `11013` | 1분기보고서 |
| `11014` | 3분기보고서 |

공시 목록에서는 보고서명만 문자열로 거르기보다 `pblntf_ty=A`로 조회한 뒤 정기보고서 종류와 정정·철회 여부를 서버에서 정규화한다. 재무 API에는 위 보고서 코드를 사용한다.

## 권장 데이터 흐름

1. 배치 작업이 `corpCode.xml`을 내려받아 회사 인덱스를 upsert한다.
2. 사용자 검색은 DART를 매번 부르지 않고 로컬 인덱스를 조회한다.
3. 회사 선택 후 `company.json`과 `list.json`을 캐시를 거쳐 호출한다.
4. 가장 최근 유효 정기보고서의 `rcept_no`를 고른다.
5. 구조화 재무 API로 수치 신호를 만들고, 원문 파서가 검증된 뒤 사업 내용·리스크·연구개발 등의 텍스트 섹션을 보강한다.
6. 분석 시 사용한 데이터와 출처 메타데이터를 스냅샷으로 저장한다.

## 오류와 운영 고려사항

- 정상 코드는 `000`이다. HTTP 200이어도 응답의 `status`를 확인해야 한다.
- `013`은 조회 결과 없음이며 빈 상태로 다룬다.
- `020`은 요청 제한 초과다. 공식 가이드는 일반적으로 20,000건 이상 요청 시 발생할 수 있다고 설명하지만 계정별 제한이 다를 수 있으므로 하드코딩하지 않는다.
- `010`, `011`, `012`, `901`은 키/계정 설정 문제로 운영 경고가 필요하다.
- `800`은 점검, `900`은 미정의 오류다. 짧은 재시도 후 사용자에게 기준시각과 실패 상태를 알린다.
- ZIP 응답은 Content-Type만 신뢰하지 말고 ZIP 시그니처와 오류 XML을 구분한다.
- `corp_code`는 종목코드와 다른 DART 8자리 식별자다. 문자열로 보관해 앞자리 0을 보존한다.
- 원문에는 표와 정정 문서가 포함된다. 정정 전/후 보고서를 섞지 않고 사용한 접수번호를 보존한다.

## API 검증 체크리스트

실제 인증키를 준비한 뒤 Phase 0에서 다음을 자동화한다.

- [ ] `corpCode.xml` 다운로드, ZIP 해제, XML 파싱
- [ ] 삼성전자(`corp_code=00126380`) 기업개황 조회
- [ ] 최근 정기공시 조회와 페이지네이션
- [ ] 사업·반기·분기보고서 접수번호 식별
- [ ] 원문 ZIP에서 XML 파일 목록과 인코딩 확인
- [ ] 연결/개별 재무제표 응답 차이 확인
- [ ] 잘못된 키, 결과 없음, 제한 초과 응답 매핑
- [ ] 원문 링크 `https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}` 확인

인증키가 없는 현재 단계에서는 공식 명세까지만 확인했으며 실호출 성공을 검증한 것으로 간주하지 않는다.

## 공식 문서

- 공시정보 API 목록: <https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS001>
- 공시검색: <https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001>
- 기업개황: <https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019002>
- 공시서류 원본: <https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003>
- 고유번호: <https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018>
- 정기보고서 재무정보: <https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS003>

