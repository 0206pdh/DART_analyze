from collections.abc import Generator
from pathlib import Path
import sqlite3

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings


class Base(DeclarativeBase):
    pass


def create_database_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite:///"):
        database_path = database_url.removeprefix("sqlite:///")
        if database_path and database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, pool_pre_ping=True)
    if database_url.startswith("sqlite"):
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

