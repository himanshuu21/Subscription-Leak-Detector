from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import auth
from app.config import settings
from app.db.models import Base, User
from app.db.session import get_db
from app.main import app


class FakeGoogleClient:
    async def authorize_redirect(self, request, redirect_uri):
        assert redirect_uri.endswith("/api/auth/google/callback")
        return RedirectResponse("https://accounts.google.test/authorize", status_code=302)

    async def authorize_access_token(self, request):
        return {
            "userinfo": {
                "sub": "google-user-123",
                "email": "oauth@example.com",
                "email_verified": True,
                "name": "OAuth User",
            }
        }


def test_google_oauth_creates_cookie_session(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_db():
        with testing_session() as db:
            yield db

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(auth.oauth, "create_client", lambda name: FakeGoogleClient())
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            page = client.get("/")
            assert page.status_code == 200
            assert page.text.count('id="root"') == 1
            config = client.get("/api/config")
            assert config.json()["google_oauth_enabled"] is True

            start = client.get("/api/auth/google/login", follow_redirects=False)
            assert start.status_code == 302
            assert start.headers["location"] == "https://accounts.google.test/authorize"

            callback = client.get("/api/auth/google/callback", follow_redirects=False)
            assert callback.status_code == 303
            assert callback.headers["location"] == "/upload-page"
            assert callback.cookies.get("sld_session")
            assert client.get("/api/uploads").status_code == 200

        with testing_session() as db:
            user = db.query(User).filter(User.email == "oauth@example.com").one()
            assert user.google_sub == "google-user-123"
            assert user.auth_provider == "google"
            assert user.hashed_password is None
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_google_route_is_unavailable_without_configuration(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")
    with TestClient(app) as client:
        response = client.get("/api/auth/google/login")
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]
