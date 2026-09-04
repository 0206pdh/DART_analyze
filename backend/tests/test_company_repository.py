from sqlalchemy.orm import Session

from app.companies.repository import CompanyRepository
from app.dart.models import CompanySummary
from app.database import Base, create_database_engine


def test_sync_and_search_companies() -> None:
    engine = create_database_engine("sqlite://")
    Base.metadata.create_all(engine)
    companies = [
        CompanySummary("00126380", "삼성전자(주)", "Samsung Electronics", "005930", "20260901"),
        CompanySummary("00164779", "SK하이닉스", "SK hynix", "000660", "20260901"),
        CompanySummary("00139834", "LG씨엔에스", "LG CNS Co., Ltd.", "064400", "20260901"),
    ]
    with Session(engine) as session:
        repository = CompanyRepository(session)
        assert repository.sync(companies) == 3
        assert repository.search("삼성")[0][0].corp_code == "00126380"
        assert repository.search("005930")[0][0].corp_name == "삼성전자(주)"
        assert repository.search("lg cns")[0][0].corp_code == "00139834"
        assert repository.search("LG씨앤에스")[0][0].corp_code == "00139834"


def test_sync_updates_existing_company() -> None:
    engine = create_database_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repository = CompanyRepository(session)
        repository.sync([CompanySummary("00126380", "삼성전자", None, "005930", "20250101")])
        repository.sync([CompanySummary("00126380", "삼성전자(주)", None, "005930", "20260901")])
        assert repository.get("00126380").modify_date == "20260901"
        assert repository.search("삼성전자")[0][0].corp_name == "삼성전자(주)"


def test_search_returns_total_and_pages() -> None:
    engine = create_database_engine("sqlite://")
    Base.metadata.create_all(engine)
    companies = [
        CompanySummary(f"{index:08d}", f"LG테스트{index}", f"LG Test {index}", f"{index:06d}", "20260901")
        for index in range(5)
    ]
    with Session(engine) as session:
        repository = CompanyRepository(session)
        repository.sync(companies)
        first, total = repository.search("LG", limit=2)
        second, second_total = repository.search("LG", limit=2, offset=2)
        assert total == second_total == 5
        assert len(first) == len(second) == 2
        assert {item.corp_code for item in first}.isdisjoint(item.corp_code for item in second)


def test_search_excludes_unlisted_companies() -> None:
    engine = create_database_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repository = CompanyRepository(session)
        repository.sync([
            CompanySummary("00000001", "테스트상장", None, "123456", "20260901"),
            CompanySummary("00000002", "테스트비상장", None, None, "20260901"),
        ])
        rows, total = repository.search("테스트")
        assert total == 1
        assert rows[0].corp_name == "테스트상장"
