from io import BytesIO
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from lxml import etree

from app.dart.errors import DartApiError, DartResponseError
import re

from app.dart.models import CompanySummary, DocumentArchive, DocumentFile, ExtractedSection


def parse_company_archive(content: bytes) -> list[CompanySummary]:
    try:
        with ZipFile(BytesIO(content)) as archive:
            xml_names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
            if not xml_names:
                raise DartResponseError("회사 고유번호 ZIP에 XML 파일이 없습니다.")
            xml_content = archive.read(xml_names[0])
    except BadZipFile as exc:
        _raise_api_error_if_xml(content)
        raise DartResponseError("회사 고유번호 응답이 유효한 ZIP 파일이 아닙니다.") from exc

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        raise DartResponseError("회사 고유번호 XML을 파싱할 수 없습니다.") from exc

    companies: list[CompanySummary] = []
    for item in root.findall(".//list"):
        corp_code = _text(item, "corp_code")
        corp_name = _text(item, "corp_name")
        modify_date = _text(item, "modify_date")
        if not corp_code or not corp_name or not modify_date:
            continue
        companies.append(
            CompanySummary(
                corp_code=corp_code,
                corp_name=corp_name,
                corp_eng_name=_optional_text(item, "corp_eng_name"),
                stock_code=_optional_text(item, "stock_code"),
                modify_date=modify_date,
            )
        )
    return companies


def inspect_document_archive(content: bytes, *, sample_limit: int = 12) -> DocumentArchive:
    try:
        with ZipFile(BytesIO(content)) as archive:
            xml_infos = [info for info in archive.infolist() if info.filename.lower().endswith(".xml")]
            if not xml_infos:
                raise DartResponseError("공시 원문 ZIP에 XML 파일이 없습니다.")
            files = tuple(
                _inspect_document_file(info.filename, info.file_size, archive.read(info), sample_limit)
                for info in xml_infos
            )
    except BadZipFile as exc:
        _raise_api_error_if_xml(content)
        raise DartResponseError("공시 원문 응답이 유효한 ZIP 파일이 아닙니다.") from exc
    return DocumentArchive(files=files)


def extract_document_sections(content: bytes) -> list[ExtractedSection]:
    xml_content = _first_xml_from_archive(content, "공시 원문")
    parser = etree.XMLParser(recover=True, no_network=True, resolve_entities=False, huge_tree=True)
    try:
        root = etree.fromstring(xml_content, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise DartResponseError("공시 원문 XML을 복구 파싱할 수 없습니다.") from exc

    sections: list[ExtractedSection] = []
    for element in root.iter():
        if not isinstance(element.tag, str) or element.tag.rsplit("}", 1)[-1].upper() != "SECTION-1":
            continue
        title_element = next((child for child in element if isinstance(child.tag, str) and child.tag.rsplit("}", 1)[-1].upper() == "TITLE"), None)
        if title_element is None:
            continue
        title = _normalize_text("".join(title_element.itertext()))
        text = _normalize_text("".join(element.itertext()))
        if not title or len(text) < 20:
            continue
        sections.append(ExtractedSection(
            order=len(sections),
            title=title[:500],
            text=text,
            source_element_id=element.get("ATOCID"),
        ))
    return sections


def _first_xml_from_archive(content: bytes, label: str) -> bytes:
    try:
        with ZipFile(BytesIO(content)) as archive:
            xml_names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
            if not xml_names:
                raise DartResponseError(f"{label} ZIP에 XML 파일이 없습니다.")
            return archive.read(xml_names[0])
    except BadZipFile as exc:
        _raise_api_error_if_xml(content)
        raise DartResponseError(f"{label} 응답이 유효한 ZIP 파일이 아닙니다.") from exc


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _inspect_document_file(name: str, size: int, content: bytes, sample_limit: int) -> DocumentFile:
    encoding = _detect_xml_encoding(content)
    try:
        parser = etree.XMLParser(
            recover=True,
            no_network=True,
            resolve_entities=False,
            huge_tree=True,
        )
        root = etree.fromstring(content, parser=parser)
    except etree.XMLSyntaxError:
        return DocumentFile(name=name, size=size, root_tag=None, encoding=encoding, title_samples=())

    titles: list[str] = []
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        tag = element.tag.rsplit("}", 1)[-1].upper()
        if tag not in {"TITLE", "SECTION-1", "SECTION-2", "SECTION-3", "COVER-TITLE", "LIBRARY"}:
            continue
        text = " ".join("".join(element.itertext()).split())
        if text and text not in titles:
            titles.append(text[:160])
        if len(titles) >= sample_limit:
            break
    return DocumentFile(
        name=name,
        size=size,
        root_tag=root.tag.rsplit("}", 1)[-1] if isinstance(root.tag, str) else None,
        encoding=encoding,
        title_samples=tuple(titles),
    )


def _detect_xml_encoding(content: bytes) -> str | None:
    declaration = content[:200].decode("ascii", errors="ignore")
    match = re.search(r"encoding=[\"']([^\"']+)", declaration, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _raise_api_error_if_xml(content: bytes) -> None:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return
    status = root.findtext("status")
    message = root.findtext("message")
    if status and status != "000":
        raise DartApiError(status.strip(), (message or "알 수 없는 오류").strip())


def _text(element: ET.Element, key: str) -> str:
    return (element.findtext(key) or "").strip()


def _optional_text(element: ET.Element, key: str) -> str | None:
    return _text(element, key) or None
