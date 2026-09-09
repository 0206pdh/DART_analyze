from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Settings:
    dart_api_key: str | None
    openai_api_key: str | None
    openai_model: str
    openai_max_output_tokens: int
    openai_timeout_seconds: float
    analysis_max_source_chars: int
    database_url: str
    document_cache_dir: Path
    session_secret: str | None = None
    read_only: bool = False
    dart_base_url: str = "https://opendart.fss.or.kr"
    dart_timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        key = os.getenv("DART_API_KEY", "").strip()
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        default_db = (PROJECT_ROOT / "data" / "dart-career.db").as_posix()
        database_url = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{default_db}"
        cache_dir = Path(os.getenv("DOCUMENT_CACHE_DIR", "").strip() or PROJECT_ROOT / "data" / "documents")
        return cls(
            dart_api_key=key or None,
            openai_api_key=openai_key or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini").strip() or "gpt-5.4-mini",
            openai_max_output_tokens=int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "3000")),
            openai_timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "35")),
            analysis_max_source_chars=int(os.getenv("ANALYSIS_MAX_SOURCE_CHARS", "40000")),
            database_url=database_url,
            document_cache_dir=cache_dir,
            session_secret=os.getenv("APP_SESSION_SECRET", "").strip() or None,
            read_only=os.getenv("READ_ONLY", "").strip().lower() in {"1", "true", "yes", "on"},
        )
