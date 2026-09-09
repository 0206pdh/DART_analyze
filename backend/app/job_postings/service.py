from __future__ import annotations

import ipaddress
import socket
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zipfile import BadZipFile, ZipFile

import httpx
from lxml import html
from pypdf import PdfReader


MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_TEXT_CHARS = 20_000
MAX_REDIRECTS = 3
SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm", ".pdf", ".docx"}


class JobPostingImportError(ValueError):
    pass


def import_from_url(url: str) -> tuple[str | None, str]:
    parsed = _validate_public_url(url)
    current_url = parsed.geturl()
    headers = {"User-Agent": "DART-Career/0.1 (+job-posting-import)"}
    with httpx.Client(timeout=10.0, follow_redirects=False, headers=headers) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _validate_public_url(current_url)
            response = client.get(current_url)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise JobPostingImportError("채용공고 페이지가 잘못된 리디렉션을 반환했습니다.")
                current_url = urljoin(current_url, location)
                continue
            if response.status_code >= 400:
                raise JobPostingImportError(f"채용공고 페이지를 불러오지 못했습니다. ({response.status_code})")
            if len(response.content) > MAX_IMPORT_BYTES:
                raise JobPostingImportError("페이지 크기가 너무 큽니다. 채용공고 본문만 붙여 넣어 주세요.")
            content_type = response.headers.get("content-type", "").lower()
            if content_type and not any(kind in content_type for kind in ("text/html", "text/plain", "application/xhtml")):
                raise JobPostingImportError("HTML 또는 텍스트 형식의 채용공고 URL만 지원합니다.")
            title, text = extract_text(response.content, ".html")
            return current_url, _limit_text(text, title)
    raise JobPostingImportError("리디렉션이 너무 많습니다.")


def extract_text(content: bytes, extension: str, content_type: str | None = None) -> tuple[str | None, str]:
    if len(content) > MAX_IMPORT_BYTES:
        raise JobPostingImportError("파일 크기가 2MB를 초과합니다.")
    suffix = Path(extension).suffix.lower() or extension.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise JobPostingImportError("지원 형식은 TXT, Markdown, HTML, PDF, DOCX입니다.")
    try:
        if suffix in {".txt", ".md", ".markdown"}:
            return None, content.decode("utf-8-sig", errors="replace")
        if suffix in {".html", ".htm"}:
            return _extract_html(content)
        if suffix == ".pdf":
            reader = PdfReader(BytesIO(content))
            return None, "\n".join(page.extract_text() or "" for page in reader.pages)
        if suffix == ".docx":
            return _extract_docx(content)
    except (BadZipFile, OSError, ValueError) as error:
        raise JobPostingImportError("파일 내용을 읽지 못했습니다.") from error
    raise JobPostingImportError("파일 내용을 읽지 못했습니다.")


def _extract_html(content: bytes) -> tuple[str | None, str]:
    document = html.fromstring(content)
    for node in document.xpath("//script|//style|//noscript|//svg"):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)
    title = " ".join(document.xpath("//title/text()")) or None
    return title, document.text_content()


def _extract_docx(content: bytes) -> tuple[str | None, str]:
    from xml.etree import ElementTree

    with ZipFile(BytesIO(content)) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    paragraphs = []
    for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        text = "".join(node.text or "" for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
        if text.strip():
            paragraphs.append(text)
    return None, "\n".join(paragraphs)


def _limit_text(text: str, title: str | None = None) -> str:
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if len(normalized) < 20:
        raise JobPostingImportError("채용공고 본문을 충분히 찾지 못했습니다. 본문을 직접 붙여 넣어 주세요.")
    return normalized[:MAX_TEXT_CHARS]


def _validate_public_url(value: str):
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise JobPostingImportError("http 또는 https 형식의 URL을 입력해 주세요.")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise JobPostingImportError("URL의 호스트를 확인하지 못했습니다.") from error
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise JobPostingImportError("내부 네트워크 주소는 불러올 수 없습니다.")
    return parsed
