import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings  # noqa: E402
from app.dart import DartClient  # noqa: E402


TARGET_NAMES = ("삼성전자", "SK하이닉스", "현대자동차", "NAVER", "카카오")


def normalize_company_name(name: str) -> str:
    return name.replace("주식회사", "").replace("(주)", "").replace(" ", "").casefold()


def main() -> int:
    settings = Settings.from_env()
    with DartClient(
        settings.dart_api_key,
        base_url=settings.dart_base_url,
        timeout=30.0,
    ) as client:
        companies = client.get_corporations()
        listed_companies = [company for company in companies if company.stock_code]
        by_name = {normalize_company_name(company.corp_name): company for company in listed_companies}

        report_results: list[dict[str, object]] = []
        for target_name in TARGET_NAMES:
            company = by_name.get(normalize_company_name(target_name))
            if company is None:
                report_results.append({"target": target_name, "error": "company_not_found"})
                continue
            disclosures = client.get_disclosures(company.corp_code, page_size=20)
            periodic = next(
                (item for item in disclosures if any(word in item.report_name for word in ("사업보고서", "반기보고서", "분기보고서"))),
                None,
            )
            if periodic is None:
                report_results.append({"target": target_name, "corp_code": company.corp_code, "error": "report_not_found"})
                continue
            archive = client.inspect_document(periodic.receipt_number)
            report_results.append({
                "target": target_name,
                "matched_name": company.corp_name,
                "corp_code": company.corp_code,
                "stock_code": company.stock_code,
                "report_name": periodic.report_name,
                "receipt_number": periodic.receipt_number,
                "xml_file_count": archive.xml_file_count,
                "files": [
                    {
                        "name": file.name,
                        "size": file.size,
                        "root_tag": file.root_tag,
                        "encoding": file.encoding,
                        "title_samples": list(file.title_samples),
                    }
                    for file in archive.files
                ],
            })

    result = {
        "corporation_count": len(companies),
        "listed_corporation_count": len(listed_companies),
        "reports": report_results,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all("error" not in report for report in report_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
