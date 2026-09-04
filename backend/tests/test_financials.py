from sqlalchemy.orm import Session

from app.companies.financials import FinancialService, _parse_amount
from app.companies.models import CompanyRecord
from app.dart.models import FinancialAccount
from app.database import Base, create_database_engine


class FakeDartClient:
    def get_financial_statements(self, *args: object, **kwargs: object) -> list[FinancialAccount]:
        return [
            FinancialAccount("20260101000001", "2026", "11012", "BS", "ifrs-full_Assets", "자산총계", "120", None, "100", None, None, "KRW", 1),
            FinancialAccount("20260101000001", "2026", "11012", "IS", "ifrs-full_Revenue", "매출액", "70", "120", None, "60", "100", "KRW", 2),
            FinancialAccount("20260101000001", "2026", "11012", "IS", "dart_OperatingIncomeLoss", "영업이익", "10", "18", None, "8", "15", "KRW", 3),
        ]


def test_refreshes_normalized_financial_metrics() -> None:
    engine = create_database_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(CompanyRecord(corp_code="00126380", corp_name="삼성전자", normalized_name="삼성전자", corp_eng_name=None, normalized_eng_name=None, stock_code="005930", modify_date="20260101"))
        session.commit()
        records = FinancialService(session, FakeDartClient()).refresh("00126380", "2026", "11012")  # type: ignore[arg-type]
        by_code = {record.metric_code: record for record in records}
        assert by_code["assets"].current_amount == 120
        assert by_code["assets"].previous_amount == 100
        assert by_code["revenue"].current_amount == 120
        assert by_code["revenue"].previous_amount == 100


def test_parses_accounting_amounts() -> None:
    assert _parse_amount("1,234") == 1234
    assert _parse_amount("(500)") == -500
    assert _parse_amount("-") is None
