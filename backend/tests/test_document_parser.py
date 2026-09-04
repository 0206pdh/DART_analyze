from io import BytesIO
from zipfile import ZipFile

import pytest

from app.dart.errors import DartApiError
from app.dart.parsers import extract_document_sections, inspect_document_archive


def _archive(content: bytes) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("report.xml", content)
    return output.getvalue()


def test_inspects_document_xml() -> None:
    content = b'''<?xml version="1.0" encoding="UTF-8"?>
    <DOCUMENT><SECTION-1><TITLE>Business Overview</TITLE></SECTION-1></DOCUMENT>'''
    result = inspect_document_archive(_archive(content))

    assert result.xml_file_count == 1
    assert result.files[0].root_tag == "DOCUMENT"
    assert result.files[0].encoding == "UTF-8"
    assert "Business Overview" in result.files[0].title_samples


def test_maps_document_error_xml() -> None:
    error = b"<?xml version='1.0'?><result><status>014</status><message>file missing</message></result>"
    with pytest.raises(DartApiError) as caught:
        inspect_document_archive(error)
    assert caught.value.status == "014"


def test_extracts_top_level_sections() -> None:
    content = b'''<?xml version="1.0" encoding="UTF-8"?>
    <DOCUMENT><BODY><SECTION-1 ATOCID="42"><TITLE>Business</TITLE>
    <P>Business direction and material information.</P></SECTION-1></BODY></DOCUMENT>'''
    sections = extract_document_sections(_archive(content))
    assert sections[0].title == "Business"
    assert sections[0].source_element_id == "42"
