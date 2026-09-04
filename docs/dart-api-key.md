# OpenDART API 인증키 발급과 설정

확인일: 2026-09-04

## 발급 방법

1. OpenDART의 [인증키 신청 페이지](https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do)를 연다.
2. 오픈API 이용약관과 개인정보 수집·이용에 동의한다.
3. 개발 및 개인 프로젝트라면 `사용자 구분`에서 **개인**을 선택한다.
4. 이메일 중복 확인 후 이메일과 비밀번호를 입력한다.
5. API 사용환경은 `웹`을 선택한다.
6. API 사용용도에는 다음과 같이 작성할 수 있다.

   > 취업 준비자를 위한 기업 공시 리서치 웹 서비스 개발 및 개인 학습. 기업 검색, 정기보고서 조회, 재무정보 분석에 사용.

7. 아직 배포 주소가 없다면 확인 URL은 선택 항목이므로 비워두거나, 본인이 관리하는 프로젝트 주소가 있을 때만 입력한다.
8. `등록`을 누른다. 개인회원은 공식 안내상 계정 신청 완료 후 즉시 발급되며, 결과는 이메일로 발송된다.
9. 이후 [OpenDART 로그인](https://opendart.fss.or.kr/uat/uia/actionLogin.do) 후 `인증키 신청/관리 → 인증키 관리`에서도 확인한다.

기업용은 회사정보, 요청 IP와 사업자 증빙이 추가로 필요하며 담당자 승인에 1~2영업일이 걸린다. 기업용의 한도 관련 혜택이 당장 필요하지 않은 로컬 MVP에는 개인용을 권장한다.

## 로컬 설정

키를 소스코드, 프런트 JavaScript, README 또는 Git 커밋에 넣지 않는다. 현재 프로젝트는 루트의 `.env`를 자동으로 읽고 해당 파일을 Git에서 제외한다.

```dotenv
DART_API_KEY=발급받은_40자리_인증키
```

또는 현재 PowerShell 세션에만 환경변수를 설정할 수 있다. 프로세스 환경변수가 `.env`보다 우선한다.

```powershell
$env:DART_API_KEY='발급받은 40자리 인증키'
python backend/scripts/dart_smoke.py
```

현재 PowerShell 창을 닫으면 이 값은 사라진다. 설정 여부는 실제 키를 출력하지 않고 다음으로 확인한다.

```powershell
python -c "import os; print(bool(os.getenv('DART_API_KEY')))"
```

서버 실행:

```powershell
uvicorn app.main:app --app-dir backend --reload
```

`GET http://localhost:8000/api/health`의 `dart_api_key_configured`가 `true`인지 확인한다.

## 유출 시

키를 채팅이나 이슈에 붙이지 않는다. 유출이 의심되면 OpenDART 인증키 관리에서 재발급/폐기하고 배포 환경의 키를 교체한다. 애플리케이션 로그에는 `crtfc_key`가 포함된 요청 URL을 남기지 않는다.
