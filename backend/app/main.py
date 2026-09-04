from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.companies.router import router as companies_router
from app.analysis.router import router as analysis_router
from app.config import Settings


app = FastAPI(title="DART Career API", version="0.1.0")
app.include_router(companies_router)
app.include_router(analysis_router)


@app.get("/api/health")
def health() -> dict[str, str | bool]:
    settings = Settings.from_env()
    return {
        "status": "ok",
        "phase": "2",
        "dart_api_key_configured": settings.dart_api_key is not None,
        "openai_api_key_configured": settings.openai_api_key is not None,
    }


WEB_ROOT = Path(__file__).resolve().parents[2] / "web"
if WEB_ROOT.exists():
    app.mount("/", StaticFiles(directory=WEB_ROOT, html=True), name="web")
