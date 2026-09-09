from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

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


def test_file_import_endpoint_returns_editable_text() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/job-postings/from-file",
        files={"file": ("posting.txt", "Backend developer job posting with API operations experience.", "text/plain")},
    )

    assert response.status_code == 200
    assert "Backend developer" in response.json()["text"]
