from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.companies.models import ApiUsageBucketRecord
from app.database import Base
from app.security import SessionIdentity, UsageLimiter


def test_usage_limiter_enforces_window_limit() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    identity = SessionIdentity("session-1", "ip-hash", 9999999999)

    with Session(engine) as session:
        limiter = UsageLimiter(session)
        assert limiter.consume(identity, "analysis", 60, 2)[0] is True
        assert limiter.consume(identity, "analysis", 60, 2)[0] is True
        assert limiter.consume(identity, "analysis", 60, 2)[0] is False
        assert session.query(ApiUsageBucketRecord).count() == 1
