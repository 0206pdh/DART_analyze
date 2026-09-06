from collections.abc import Generator
from pathlib import Path
import sqlite3

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import Settings


class Base(DeclarativeBase):
    pass


def create_database_engine(database_url: str) -> Engine:
    is_sqlite = database_url.startswith("sqlite")
    if database_url.startswith("sqlite:///"):
        database_path = database_url.removeprefix("sqlite:///")
        if database_path and database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict = {"pool_pre_ping": True}
    if not is_sqlite:
        connect_args = {"connect_timeout": 15}
        if ":6543" in database_url:
            # Supabase 트랜잭션 풀러(서버리스): 커넥션 풀링은 풀러에 맡기고
            # prepared statement 를 끈다.
            kwargs["poolclass"] = NullPool
            connect_args["prepare_threshold"] = None
        else:
            kwargs["pool_recycle"] = 1800
        kwargs["connect_args"] = connect_args
    engine = create_engine(database_url, **kwargs)
    if is_sqlite:
        event.listen(engine, "connect", _configure_sqlite)
    return engine


def _configure_sqlite(connection: sqlite3.Connection, _: object) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


settings = Settings.from_env()
engine = create_database_engine(settings.database_url)
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    with SessionFactory() as session:
        yield session

