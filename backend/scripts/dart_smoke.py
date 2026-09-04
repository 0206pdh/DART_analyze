import argparse
import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings  # noqa: E402
from app.dart import DartClient, DartConfigurationError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenDART Phase 0 smoke test")
    parser.add_argument("--corp-code", default="00126380", help="8자리 DART 고유번호")
    args = parser.parse_args()
    settings = Settings.from_env()

    try:
        with DartClient(
            settings.dart_api_key,
            base_url=settings.dart_base_url,
            timeout=settings.dart_timeout_seconds,
        ) as client:
            company = client.get_company(args.corp_code)
            disclosures = client.get_disclosures(args.corp_code, page_size=5)
    except DartConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        print("PowerShell 예: $env:DART_API_KEY='발급받은 키'", file=sys.stderr)
        return 2

    print(json.dumps({
        "company": company.corp_name,
        "corp_code": company.corp_code,
        "recent_disclosures": [
            {
                "report_name": item.report_name,
                "receipt_date": item.receipt_date,
                "viewer_url": item.viewer_url,
            }
            for item in disclosures
        ],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

