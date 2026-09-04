from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.companies.repository import CompanyRepository  # noqa: E402
from app.config import Settings  # noqa: E402
from app.dart import DartClient  # noqa: E402
from app.database import SessionFactory  # noqa: E402


def main() -> int:
    settings = Settings.from_env()
    with SessionFactory() as session:
        repository = CompanyRepository(session)
        sync_record = repository.start_sync()
        try:
            with DartClient(settings.dart_api_key, timeout=30.0) as client:
                companies = client.get_corporations()
            count = repository.sync(companies)
            repository.finish_sync(sync_record, company_count=count)
        except Exception as exc:
            repository.fail_sync(sync_record, exc)
            raise
    print(f"회사 원장 동기화 완료: {count:,}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

