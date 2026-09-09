from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import hmac
import secrets
import time

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.companies.models import ApiUsageBucketRecord
from app.config import Settings
from app.database import get_session


SESSION_COOKIE = "dart_career_session"
SESSION_TTL_SECONDS = 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class SessionIdentity:
    session_id: str
    ip_hash: str
    expires_at: int


def create_session(request: Request, response: Response) -> dict[str, int | bool]:
    settings = Settings.from_env()
    _require_secret(settings)
    token, identity = _new_session(settings.session_secret or "", request)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https",
        samesite="lax",
        path="/",
    )
    return {"authenticated": True, "expires_at": identity.expires_at}


def require_api_session(request: Request) -> SessionIdentity:
    settings = Settings.from_env()
    _require_secret(settings)
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="API 세션이 없습니다. 페이지를 새로고침해 주세요.")
    identity = _verify_session(token, settings.session_secret or "", request)
    if identity is None:
        raise HTTPException(status_code=401, detail="API 세션이 만료되었습니다. 페이지를 새로고침해 주세요.")
    return identity


def enforce_api_protection(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> SessionIdentity:
    identity = require_api_session(request)
    scope, minute_limit, daily_limit = _limits_for_path(request.url.path)
    limiter = UsageLimiter(session)
    for window_seconds, limit in ((60, minute_limit), (86_400, daily_limit)):
        allowed, retry_after = limiter.consume(identity, scope, window_seconds, limit)
        if not allowed:
            response.headers["Retry-After"] = str(retry_after)
            response.headers["X-RateLimit-Limit"] = str(limit)
            raise HTTPException(status_code=429, detail=f"요청 한도를 초과했습니다. {retry_after}초 후 다시 시도해 주세요.")
    response.headers["X-RateLimit-Limit"] = str(minute_limit)
    return identity


class UsageLimiter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def consume(self, identity: SessionIdentity, scope: str, window_seconds: int, limit: int) -> tuple[bool, int]:
        now = datetime.now(UTC)
        epoch = int(now.timestamp())
        window_epoch = epoch - (epoch % window_seconds)
        window_start = datetime.fromtimestamp(window_epoch, UTC)
        expires_at = window_start + timedelta(seconds=window_seconds)
        identity_hash = sha256(f"{identity.session_id}:{identity.ip_hash}".encode()).hexdigest()
        bucket_key = sha256(f"{identity_hash}:{scope}:{window_epoch}".encode()).hexdigest()
        dialect = self._session.bind.dialect.name if self._session.bind else ""
        insert_builder = {"sqlite": sqlite_insert, "postgresql": pg_insert}.get(dialect)
        if insert_builder is None:
            raise RuntimeError("지원하지 않는 데이터베이스입니다.")
        statement = insert_builder(ApiUsageBucketRecord).values(
            bucket_key=bucket_key,
            identity_hash=identity_hash,
            scope=scope,
            window_start=window_start,
            expires_at=expires_at,
            request_count=1,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[ApiUsageBucketRecord.bucket_key],
            set_={"request_count": ApiUsageBucketRecord.request_count + 1},
            where=ApiUsageBucketRecord.request_count < limit,
        )
        result = self._session.execute(statement)
        self._session.commit()
        if result.rowcount == 0:
            return False, max(1, int((expires_at - now).total_seconds()))
        return True, max(1, int((expires_at - now).total_seconds()))


def _limits_for_path(path: str) -> tuple[str, int, int]:
    if path == "/api/analyses/draft":
        return "draft", 3, 10
    if path == "/api/analyses":
        return "analysis", 2, 5
    if path in {"/api/job-postings/from-url", "/api/job-postings/from-file"}:
        return "import", 6, 30
    if path == "/api/companies/search":
        return "search", 30, 300
    return "read", 60, 600


def _new_session(secret: str, request: Request) -> tuple[str, SessionIdentity]:
    session_id = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    payload = f"{session_id}.{expires_at}"
    signature = hmac.new(secret.encode(), payload.encode(), sha256).hexdigest()
    token = f"{payload}.{signature}"
    return token, SessionIdentity(session_id, _ip_hash(request, secret), expires_at)


def _verify_session(token: str, secret: str, request: Request) -> SessionIdentity | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    session_id, expires_text, signature = parts
    payload = f"{session_id}.{expires_text}"
    expected = hmac.new(secret.encode(), payload.encode(), sha256).hexdigest()
    try:
        expires_at = int(expires_text)
    except ValueError:
        return None
    if not hmac.compare_digest(signature, expected) or expires_at <= int(time.time()):
        return None
    return SessionIdentity(session_id, _ip_hash(request, secret), expires_at)


def _ip_hash(request: Request, secret: str) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",", 1)[0].strip() or (request.client.host if request.client else "unknown")
    return sha256(f"{secret}:{ip}".encode()).hexdigest()


def _require_secret(settings: Settings) -> None:
    if not settings.session_secret:
        raise HTTPException(status_code=503, detail="APP_SESSION_SECRET가 설정되지 않았습니다.")
