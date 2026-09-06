from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

import httpx

from app.dart.errors import DartApiError, DartConfigurationError, DartResponseError
from app.dart.models import Company, CompanySummary, Disclosure, DocumentArchive, FinancialAccount
from app.dart.parsers import inspect_document_archive, parse_company_archive


class DartClient:
    def __init__(
        self,
        api_key: str | None,
        *,
        base_url: str = "https://opendart.fss.or.kr",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise DartConfigurationError("DART_API_KEY가 설정되지 않았습니다.")
        self._api_key = api_key
        self._client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
            transport=transport,
            headers={"User-Agent": "dart-career/0.1"},
        )

    def __enter__(self) -> "DartClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get_corporations(self) -> list[CompanySummary]:
        response = self._get("/api/corpCode.xml")
        return parse_company_archive(response.content)

    def get_company(self, corp_code: str) -> Company:
        self._validate_corp_code(corp_code)
        data = self._get_json("/api/company.json", {"corp_code": corp_code})
        return Company(
            corp_code=str(data["corp_code"]),
            corp_name=str(data["corp_name"]),
            corp_name_eng=_optional_string(data.get("corp_name_eng")),
            stock_name=_optional_string(data.get("stock_name")),
            stock_code=_optional_string(data.get("stock_code")),
            ceo_name=_optional_string(data.get("ceo_nm")),
            corporation_type=_optional_string(data.get("corp_cls")),
            business_number=_optional_string(data.get("bizr_no")),
            industry_code=_optional_string(data.get("induty_code")),
            established_date=_optional_string(data.get("est_dt")),
            accounting_month=_optional_string(data.get("acc_mt")),
        )

    def get_disclosures(
        self,
        corp_code: str,
        *,
        begin_date: str | None = None,
        end_date: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[Disclosure]:
        self._validate_corp_code(corp_code)
        if not 1 <= page_size <= 100:
            raise ValueError("page_size는 1에서 100 사이여야 합니다.")
        if end_date is None:
            end_date = date.today().strftime("%Y%m%d")
        if begin_date is None:
            begin_date = (date.today() - timedelta(days=366)).strftime("%Y%m%d")
        params: dict[str, str | int] = {
            "corp_code": corp_code,
            "pblntf_ty": "A",
            "last_reprt_at": "Y",
            "sort": "date",
            "sort_mth": "desc",
            "page_no": page,
            "page_count": page_size,
        }
        params["bgn_de"] = begin_date
        params["end_de"] = end_date
        try:
            data = self._get_json("/api/list.json", params)
        except DartApiError as exc:
            if exc.status == "013":
                return []
            raise
        return [
            Disclosure(
                receipt_number=str(item["rcept_no"]),
                corporation_class=str(item["corp_cls"]),
                corporation_name=str(item["corp_name"]),
                corporation_code=str(item["corp_code"]),
                stock_code=_optional_string(item.get("stock_code")),
                report_name=str(item["report_nm"]),
                filer_name=str(item["flr_nm"]),
                receipt_date=str(item["rcept_dt"]),
                remarks=_optional_string(item.get("rm")),
            )
            for item in data.get("list", [])
        ]

    def download_document(self, receipt_number: str) -> bytes:
        if not receipt_number.isdigit() or len(receipt_number) != 14:
            raise ValueError("receipt_number는 14자리 숫자여야 합니다.")
        return self._get("/api/document.xml", {"rcept_no": receipt_number}).content

    def inspect_document(self, receipt_number: str) -> DocumentArchive:
        return inspect_document_archive(self.download_document(receipt_number))

    def get_financial_statements(
        self,
        corp_code: str,
        business_year: str,
        report_code: str,
        *,
        financial_statement_division: str = "CFS",
    ) -> list[FinancialAccount]:
        self._validate_corp_code(corp_code)
        if not business_year.isdigit() or len(business_year) != 4:
            raise ValueError("business_year는 4자리 숫자여야 합니다.")
        if report_code not in {"11011", "11012", "11013", "11014"}:
            raise ValueError("지원하지 않는 report_code입니다.")
        if financial_statement_division not in {"CFS", "OFS"}:
            raise ValueError("financial_statement_division은 CFS 또는 OFS여야 합니다.")
        try:
            data = self._get_json("/api/fnlttSinglAcntAll.json", {
                "corp_code": corp_code,
                "bsns_year": business_year,
                "reprt_code": report_code,
                "fs_div": financial_statement_division,
            })
        except DartApiError as exc:
            if exc.status == "013":
                return []
            raise
        return [FinancialAccount(
            receipt_number=str(item.get("rcept_no", "")),
            business_year=str(item.get("bsns_year", business_year)),
            report_code=str(item.get("reprt_code", report_code)),
            statement_division=str(item.get("sj_div", "")),
            account_id=str(item.get("account_id", "")),
            account_name=str(item.get("account_nm", "")),
            current_amount=_optional_string(item.get("thstrm_amount")),
            current_cumulative_amount=_optional_string(item.get("thstrm_add_amount")),
            previous_amount=_optional_string(item.get("frmtrm_amount")),
            previous_quarter_amount=_optional_string(item.get("frmtrm_q_amount")),
            previous_cumulative_amount=_optional_string(item.get("frmtrm_add_amount")),
            currency=_optional_string(item.get("currency")),
            order=int(item.get("ord") or 0),
        ) for item in data.get("list", [])]

    def _get_json(self, path: str, params: Mapping[str, str | int] | None = None) -> dict[str, Any]:
        response = self._get(path, params)
        try:
            data = response.json()
        except ValueError as exc:
            raise DartResponseError("OpenDART가 유효한 JSON을 반환하지 않았습니다.") from exc
        if not isinstance(data, dict):
            raise DartResponseError("OpenDART JSON 응답의 최상위 값이 객체가 아닙니다.")
        self._raise_for_api_status(data)
        return data

    def _get(self, path: str, params: Mapping[str, str | int] | None = None) -> httpx.Response:
        query = {"crtfc_key": self._api_key, **(dict(params) if params else {})}
        try:
            response = self._client.get(path, params=query)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise DartResponseError("OpenDART 요청 시간이 초과되었습니다.") from exc
        except httpx.HTTPStatusError as exc:
            raise DartResponseError(f"OpenDART HTTP 오류: {exc.response.status_code}") from exc
        except httpx.TransportError as exc:
            raise DartResponseError(f"OpenDART 연결 오류: {type(exc).__name__}") from exc
        return response

    @staticmethod
    def _raise_for_api_status(data: Mapping[str, Any]) -> None:
        status = str(data.get("status", ""))
        if status != "000":
            raise DartApiError(status or "unknown", str(data.get("message", "알 수 없는 오류")))

    @staticmethod
    def _validate_corp_code(corp_code: str) -> None:
        if not corp_code.isdigit() or len(corp_code) != 8:
            raise ValueError("corp_code는 8자리 숫자여야 합니다.")


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
