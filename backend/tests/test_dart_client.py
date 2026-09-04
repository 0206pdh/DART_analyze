from io import BytesIO
import json
from zipfile import ZipFile

import httpx
import pytest

from app.dart.client import DartClient
from app.dart.errors import DartApiError, DartConfigurationError


def _json_response(request: httpx.Request, payload: dict[str, object]) -> httpx.Response:
    return httpx.Response(200, json=payload, request=request)


def _company_zip() -> bytes:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <result><list><corp_code>00126380</corp_code><corp_name>Samsung Electronics</corp_name>
    <corp_eng_name>Samsung Electronics Co., Ltd.</corp_eng_name><stock_code>005930</stock_code>
    <modify_date>20250101</modify_date></list></result>"""
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("CORPCODE.xml", xml)
    return output.getvalue()


def test_requires_api_key() -> None:
    with pytest.raises(DartConfigurationError):
        DartClient(None)


def test_parses_company_archive() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["crtfc_key"] == "test-key"
        return httpx.Response(200, content=_company_zip(), request=request)

    with DartClient("test-key", transport=httpx.MockTransport(handler)) as client:
        companies = client.get_corporations()

    assert len(companies) == 1
    assert companies[0].corp_code == "00126380"
    assert companies[0].stock_code == "005930"


def test_maps_api_error_and_retryability() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(request, {"status": "020", "message": "요청 제한 초과"})

    with DartClient("test-key", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DartApiError) as caught:
            client.get_company("00126380")

    assert caught.value.status == "020"
    assert caught.value.retryable is True


def test_gets_latest_periodic_disclosures() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        assert params["corp_code"] == "00126380"
        assert params["pblntf_ty"] == "A"
        assert params["last_reprt_at"] == "Y"
        assert len(params["bgn_de"]) == 8
        assert len(params["end_de"]) == 8
        return _json_response(request, {
            "status": "000",
            "message": "정상",
            "list": [{
                "rcept_no": "20250814001234",
                "corp_cls": "Y",
                "corp_name": "삼성전자",
                "corp_code": "00126380",
                "stock_code": "005930",
                "report_nm": "반기보고서 (2025.06)",
                "flr_nm": "삼성전자",
                "rcept_dt": "20250814",
                "rm": "",
            }],
        })

    with DartClient("test-key", transport=httpx.MockTransport(handler)) as client:
        disclosures = client.get_disclosures("00126380")

    assert disclosures[0].report_name.startswith("반기보고서")
    assert disclosures[0].viewer_url.endswith("20250814001234")


def test_maps_no_disclosures_to_empty_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(request, {"status": "013", "message": "조회된 데이타가 없습니다."})

    with DartClient("test-key", transport=httpx.MockTransport(handler)) as client:
        assert client.get_disclosures("00126380") == []


def test_rejects_invalid_corp_code() -> None:
    with DartClient("test-key", transport=httpx.MockTransport(lambda request: None)) as client:
        with pytest.raises(ValueError, match="8자리"):
            client.get_company("5930")
