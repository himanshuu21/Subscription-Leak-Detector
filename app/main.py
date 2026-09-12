from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.transactions import router as transactions_router
from app.api.subscriptions import router as subscriptions_router
from app.db.session import engine
from app.db.models import Base
from app.config import settings

app = FastAPI(title='Subscription Leak Detector', version='1.0.0')
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=600,
    same_site="lax",
    https_only=settings.ENVIRONMENT.lower() == "production",
)

app.include_router(auth_router)
app.include_router(transactions_router)
app.include_router(subscriptions_router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"

if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/config", include_in_schema=False)
def frontend_config():
    return {
        "currency": settings.CURRENCY_SYMBOL,
        "google_oauth_enabled": settings.google_oauth_enabled,
    }


@app.get("/{frontend_path:path}", include_in_schema=False)
def serve_react_app(frontend_path: str):
    """Serve the React SPA and let the browser handle client-side routes."""
    if FRONTEND_INDEX.is_file():
        return FileResponse(FRONTEND_INDEX)

    # Keeps API/test startup useful before the first npm build and explains the
    # missing build instead of failing during module import.
    development_index = FRONTEND_DIR / "index.html"
    if development_index.is_file():
        return FileResponse(development_index)
    return {"detail": "Frontend is not built. Run `npm install && npm run build` in frontend/."}
