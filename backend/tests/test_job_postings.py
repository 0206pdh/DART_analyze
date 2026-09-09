from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.job_postings.service import extract_text
from app.main import app


def test_extracts_html_without_scripts() -> None:
    content = "<html><title>Job posting</title><script>bad()</script><main>Backend developer job posting with API operations experience.</main></html>".encode()
    title, text = extract_text(content, ".html")

    assert title == "Job posting"
    assert "Backend developer" in text
    assert "bad" not in text


def test_extracts_docx_text() -> None:
    document_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Data analysis job posting.</w:t></w:r></w:p></w:body></w:document>'''.encode()
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    _, text = extract_text(buffer.getvalue(), "posting.docx")

    assert text == "Data analysis job posting."


def test_file_import_endpoint_returns_editable_text(monkeypatch) -> None:
    monkeypatch.setenv("APP_SESSION_SECRET", "test-session-secret")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_session():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)
        assert client.get("/api/auth/session").status_code == 200
        response = client.post(
            "/api/job-postings/from-file",
            files={"file": ("posting.txt", "Backend developer job posting with API operations experience.", "text/plain")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Backend developer" in response.json()["text"]
