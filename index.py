"""Vercel Python 진입점.

Vercel은 루트의 `index.py` 에서 top-level `app` 을 찾아 서버리스 함수로 실행하고
모든 요청을 이 앱으로 보낸다. FastAPI 가 `/api/*` 와 정적 `web/` 를 함께 서빙한다.
백엔드 코드는 `backend/` 아래에 있으므로 import 경로에 추가한다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.main import app  # noqa: E402

__all__ = ["app"]
