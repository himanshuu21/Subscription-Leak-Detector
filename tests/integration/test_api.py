from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.session import get_db
from app.main import app


def test_cookie_auth_and_import_diagnostics():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            signup = client.post(
                "/api/auth/signup",
                json={"email": "api@example.com", "password": "LongEnough!12"},
            )
            assert signup.status_code == 200
            assert signup.cookies.get("sld_session")

            csv_body = (
                "Date,Description,Debit,Credit\n"
                "2026-01-01,Netflix,199.00,\n"
                "2026-02-01,Netflix,199.00,\n"
                "2026-02-02,Refund,,199.00\n"
                "not-a-date,Broken,100.00,\n"
            )
            upload = client.post(
                "/api/upload",
                files={"file": ("transactions.csv", csv_body, "text/csv")},
            )
            assert upload.status_code == 200, upload.text
            body = upload.json()
            assert body["total_rows"] == 4
            assert body["imported_rows"] == 2
            assert body["credit_row_count"] == 1
            assert body["invalid_row_count"] == 1
            assert '"row": 5' in body["invalid_row_errors"]

            dashboard = client.get("/dashboard")
            assert dashboard.status_code == 200
            assert 'id="root"' in dashboard.text
            assert dashboard.headers["content-type"].startswith("text/html")

            logout = client.post("/api/auth/logout")
            assert logout.status_code == 204
            assert client.get("/api/uploads").status_code == 401
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
