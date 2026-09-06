"""시가총액 상위 상장사만 DART에서 미리 수집해 Postgres(Supabase)에 적재한다.

배포 런타임(Vercel, READ_ONLY)에서는 DART를 호출하지 않으므로, 이 스크립트를
로컬 또는 CI에서 주기적으로(예: 6개월) 실행해 데이터를 채워 둔다.

선행 조건: `python backend/scripts/sync_companies.py`로 회사 원장이 채워져 있어야 한다
(종목코드 → corp_code 매칭에 사용).

종목 목록 소스(우선순위):
  1. --codes-file  : 6자리 종목코드 목록(줄바꿈 구분)
  2. --marketcap-csv : 종목코드 + 시가총액 컬럼이 있는 CSV(시총 내림차순 상위 N)
  3. 미지정 시 FinanceDataReader 로 KRX 전종목을 받아 시총 상위 N
     (pip install -e ".[preload]")

사용 예:
  python backend/scripts/preload_listed.py --top 1000
  python backend/scripts/preload_listed.py --marketcap-csv krx.csv --top 500
  python backend/scripts/preload_listed.py --codes-file codes.txt --force
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
import sys
import time

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import InterfaceError, OperationalError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.companies.financials import FinancialService  # noqa: E402
from app.companies.models import CompanyRecord, FilingRecord, FilingSectionRecord, FinancialMetricRecord  # noqa: E402
from app.companies.service import CompanyResearchService  # noqa: E402
from app.config import Settings  # noqa: E402
from app.dart import DartClient  # noqa: E402
from app.dart.errors import DartApiError, DartError  # noqa: E402
from app.database import SessionFactory  # noqa: E402

ANNUAL_REPORT_CODE = "11011"
PERIODIC_KEYWORDS = ("사업보고서", "반기보고서", "분기보고서")
CODE_HEADER_CANDIDATES = ("code", "종목코드", "단축코드", "isu_srt_cd", "srtncd", "ticker")
MARCAP_HEADER_CANDIDATES = ("marcap", "시가총액", "marketcap", "market_cap", "mktcap")


class DailyQuotaExceeded(RuntimeError):
    pass


def _retry(fn, *, attempts: int = 4, base_delay: float = 3.0):
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except DartApiError as error:
            if error.status == "020":
                raise DailyQuotaExceeded("OpenDART 일일 요청 한도(020)를 초과했습니다. 24시간 후 재실행하세요.") from error
            if not error.retryable or attempt == attempts:
                raise
        except DartError:
            if attempt == attempts:
                raise
        time.sleep(base_delay * attempt)
    raise RuntimeError("unreachable")


def _normalize_code(value: str) -> str | None:
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits.zfill(6) if digits else None


def _codes_from_file(path: Path) -> list[str]:
    codes: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        code = _normalize_code(line.strip())
        if code:
            codes.append(code)
    return codes


def _codes_from_marketcap_csv(path: Path, top: int) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit(f"CSV 헤더를 읽을 수 없습니다: {path}")
        lower = {name.lower().strip(): name for name in reader.fieldnames}
        code_col = next((lower[c] for c in CODE_HEADER_CANDIDATES if c in lower), None)
        marcap_col = next((lower[c] for c in MARCAP_HEADER_CANDIDATES if c in lower), None)
        if code_col is None or marcap_col is None:
            raise SystemExit(f"CSV에서 종목코드/시가총액 컬럼을 찾지 못했습니다: {reader.fieldnames}")
        rows: list[tuple[int, str]] = []
        for row in reader:
            code = _normalize_code((row.get(code_col) or "").strip())
            raw = (row.get(marcap_col) or "").replace(",", "").strip()
            if not code or not raw:
                continue
            try:
                rows.append((int(float(raw)), code))
            except ValueError:
                continue
    rows.sort(reverse=True)
    return [code for _, code in rows[:top]]


def _codes_from_fdr(top: int) -> list[str]:
    try:
        import FinanceDataReader as fdr
    except ImportError as error:
        raise SystemExit(
            "FinanceDataReader가 필요합니다. `pip install -e \".[preload]\"` 하거나 "
            "--marketcap-csv / --codes-file 를 사용하세요."
        ) from error
    listing = fdr.StockListing("KRX")
    columns = {c.lower(): c for c in listing.columns}
    code_col = next((columns[c] for c in CODE_HEADER_CANDIDATES if c in columns), None)
    marcap_col = next((columns[c] for c in MARCAP_HEADER_CANDIDATES if c in columns), None)
    if code_col is None or marcap_col is None:
        raise SystemExit(f"FDR 응답에서 컬럼을 찾지 못했습니다: {list(listing.columns)}")
    ranked = listing.dropna(subset=[marcap_col]).sort_values(marcap_col, ascending=False)
    out: list[str] = []
    for raw in ranked[code_col].astype(str).tolist():
        code = _normalize_code(raw)
        if code and code not in out:
            out.append(code)
        if len(out) >= top:
            break
    return out


def _resolve_targets(session: Session, codes: list[str]) -> tuple[list[CompanyRecord], list[str]]:
    wanted = list(dict.fromkeys(codes))
    found = {
        record.stock_code: record
        for record in session.scalars(
            select(CompanyRecord).where(CompanyRecord.stock_code.in_(wanted))
        )
    }
    ordered = [found[code] for code in wanted if code in found]
    missing = [code for code in wanted if code not in found]
    return ordered, missing


def _already_loaded(session: Session, corp_code: str, years: list[str]) -> bool:
    has_sections = session.scalar(
        select(FilingSectionRecord.id)
        .join(FilingRecord, FilingRecord.receipt_number == FilingSectionRecord.receipt_number)
        .where(FilingRecord.corp_code == corp_code)
        .limit(1)
    )
    if has_sections is None:
        return False
    loaded_years = set(session.scalars(
        select(FinancialMetricRecord.business_year)
        .where(FinancialMetricRecord.corp_code == corp_code)
        .distinct()
    ))
    # 오래된 연도는 신규 상장사 등에서 비어 있을 수 있으므로 최소 1개 연도만 확인한다.
    return any(year in loaded_years for year in years)


def _latest_periodic_receipt(filings: list[FilingRecord]) -> str | None:
    ordered = sorted(filings, key=lambda f: f.receipt_date, reverse=True)
    for filing in ordered:
        if any(keyword in filing.report_name for keyword in PERIODIC_KEYWORDS):
            return filing.receipt_number
    return None


def _load_company(
    session: Session,
    dart: DartClient,
    company: CompanyRecord,
    years: list[str],
    *,
    store_archive: bool,
) -> str:
    research = CompanyResearchService(session, dart, Settings.from_env().document_cache_dir)
    _retry(lambda: research.refresh_company(company.corp_code))
    receipt = _latest_periodic_receipt(research.get_filings(company.corp_code))
    if receipt is None:
        return "no-periodic-report"
    _, sections = _retry(lambda: research.cache_and_extract(receipt, store_archive=store_archive))

    financials = FinancialService(session, dart)
    filled_years = 0
    for year in years:
        records = _retry(lambda y=year: financials.refresh(company.corp_code, y, ANNUAL_REPORT_CODE))
        filled_years += 1 if records else 0
    return f"ok (sections={len(sections)}, fin_years={filled_years}/{len(years)})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--top", type=int, default=1000, help="시가총액 상위 N개 (기본 1000)")
    parser.add_argument("--codes-file", type=Path, help="6자리 종목코드 목록 파일")
    parser.add_argument("--marketcap-csv", type=Path, help="종목코드+시가총액 CSV")
    parser.add_argument("--years", type=int, default=2, help="적재할 연간 재무 개수 (기본 2)")
    parser.add_argument("--sleep", type=float, default=0.5, help="기업 간 대기(초)")
    parser.add_argument("--force", action="store_true", help="이미 적재된 기업도 다시 수집")
    parser.add_argument("--store-archive", action="store_true", help="원문 ZIP을 로컬 data/documents 에도 저장")
    parser.add_argument("--limit", type=int, help="이번 실행에서 처리할 최대 기업 수")
    args = parser.parse_args()

    settings = Settings.from_env()
    if not settings.dart_api_key:
        raise SystemExit("DART_API_KEY가 필요합니다.")
    if settings.read_only:
        raise SystemExit("READ_ONLY 환경에서는 프리로드를 실행하지 않습니다. .env에서 READ_ONLY를 해제하세요.")

    if args.codes_file:
        codes = _codes_from_file(args.codes_file)[: args.top]
    elif args.marketcap_csv:
        codes = _codes_from_marketcap_csv(args.marketcap_csv, args.top)
    else:
        codes = _codes_from_fdr(args.top)
    if not codes:
        raise SystemExit("대상 종목코드를 확보하지 못했습니다.")

    current_year = date.today().year
    years = [str(current_year - offset) for offset in range(1, args.years + 1)]

    with SessionFactory() as session:
        targets, missing = _resolve_targets(session, codes)
    print(f"대상 종목 {len(codes)}개 중 원장 매칭 {len(targets)}개 · 미매칭 {len(missing)}개")
    if missing:
        print(f"  미매칭 코드 예: {', '.join(missing[:15])}{' ...' if len(missing) > 15 else ''}")
    if args.limit:
        targets = targets[: args.limit]

    processed = skipped = failed = 0
    with DartClient(settings.dart_api_key, base_url=settings.dart_base_url, timeout=60.0) as dart:
        for index, company in enumerate(targets, start=1):
            label = f"[{index}/{len(targets)}] {company.corp_name} ({company.stock_code})"
            for attempt in range(1, 4):
                try:
                    with SessionFactory() as session:
                        if not args.force and _already_loaded(session, company.corp_code, years):
                            skipped += 1
                            break
                        status = _load_company(
                            session, dart, company, years, store_archive=args.store_archive
                        )
                    processed += 1
                    print(f"{label}: {status}")
                    break
                except DailyQuotaExceeded as error:
                    print(f"\n중단: {error}")
                    print(f"진행 상황 - 완료 {processed} · 건너뜀 {skipped} · 실패 {failed}")
                    return 2
                except (OperationalError, InterfaceError) as error:
                    if attempt < 3:
                        print(f"{label}: DB 연결 오류, {attempt}회 재시도")
                        time.sleep(5 * attempt)
                        continue
                    failed += 1
                    print(f"{label}: 실패 - DB 연결 ({type(error).__name__})")
                except Exception as error:  # noqa: BLE001 - 개별 기업 실패는 건너뛰고 계속
                    failed += 1
                    print(f"{label}: 실패 - {type(error).__name__}: {error}")
                    break
            time.sleep(args.sleep)

    print(f"\n완료 - 신규/갱신 {processed} · 건너뜀 {skipped} · 실패 {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
