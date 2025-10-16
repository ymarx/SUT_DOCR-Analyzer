import os
from pathlib import Path
import pytest
import json
import zipfile
from dataclasses import asdict
from mypkg.components.parser.xml_parser import DocxXmlParser
from mypkg.core.base_parser import TableRecord, TableCellRecord, ParagraphRecord

def _get_fixture_path(filename: str) -> Path:
    return Path(f"src/mypkg/tests/fixtures/{filename}").resolve()

def _get_output_dir() -> Path:
    out = Path("src/mypkg/tests/output/parser").resolve()
    out.mkdir(parents=True, exist_ok=True)
    return out

def _safe_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

def _dump_all_inner_xml(docx_path: Path, outdir: Path, filename_stem: str) -> int:
    """
    DOCX(zip) 내부의 모든 *.xml 파일을 {outdir}/{filename_stem}_xml/ 하위폴더 구조 그대로 저장.
    반환: 저장한 파일 개수
    """
    count = 0
    xml_outdir = outdir / f"{filename_stem}_xml"
    with zipfile.ZipFile(docx_path, "r") as zf:
        for name in zf.namelist():
            if name.lower().endswith(".xml"):
                data = zf.read(name)
                out_path = xml_outdir / name
                _safe_write(out_path, data)
                count += 1
    return count, xml_outdir

@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_filename", [
    "sample2_section.docx",
])
async def test_xml_parse_success_and_keys(fixture_filename):
    sample = _get_fixture_path(fixture_filename)
    if not sample.exists():
        pytest.skip(f"Sample DOCX not found: {sample}")

    parser = DocxXmlParser()
    assert ".docx" in parser.supported_formats

    res = await parser.parse(sample)
    assert res.success, f"xml parse failed: {res.error}"

    assert isinstance(res.content, dict)
    assert "docx_xml" in res.content, "payload must contain 'docx_xml'"

    x = res.content["docx_xml"]
    # 변경된 키 구조 확인
    for key in ("tables", "headers", "footers", "relationships", "drawings_raw", "paragraphs_xml"):
        assert key in x, f"missing key in docx_xml: {key}"

    assert isinstance(x["tables"], list)
    assert isinstance(x["headers"], list)
    assert isinstance(x["footers"], list)
    assert isinstance(x["relationships"], dict)
    assert "map" in x["relationships"]
    assert isinstance(x["drawings_raw"], list)
    assert isinstance(x["paragraphs_xml"], list)

    # 데이터클래스 객체인지 확인
    if x["paragraphs_xml"]:
        assert isinstance(x["paragraphs_xml"][0], ParagraphRecord)

@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_filename", [
    "sample2_section.docx"
])
async def test_extract_inner_xml_and_optional_parse_json(fixture_filename):
    sample = _get_fixture_path(fixture_filename)
    if not sample.exists():
        pytest.skip(f"Sample DOCX not found: {sample}")

    outdir = _get_output_dir()
    filename_stem = sample.stem

    # 1) 원본 XML 전부 추출
    n, xml_outdir = _dump_all_inner_xml(sample, outdir, filename_stem)
    assert n > 0, "No XML files found in docx zip"
    print(f"\n[INFO] Extracted {n} XML files under: {xml_outdir}")

    parser = DocxXmlParser()
    res = await parser.parse(sample)
    assert res.success, f"xml parse failed: {res.error}"

    # dataclass를 dict로 변환
    content_for_save = asdict(res)
    
    out_path_xml = outdir / f"{filename_stem}_output_xml.json"
    out_path_xml.write_text(json.dumps(content_for_save, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] XmlParser JSON saved to: {out_path_xml}")

@pytest.mark.asyncio
async def test_xml_parser_content_details(fixture_filename="sample2_section.docx"):
    """
    Parses a docx and checks for specific content details.
    This test assumes 'sample2_section.docx' contains certain elements.
    """
    sample = _get_fixture_path(fixture_filename)
    if not sample.exists():
        pytest.skip(f"Sample DOCX not found: {sample}")

    parser = DocxXmlParser()
    res = await parser.parse(sample)
    assert res.success, f"Parse failed: {res.error}"

    data = res.content["docx_xml"]

    # 1. Test for paragraphs
    assert len(data["paragraphs_xml"]) > 10, "Expected a significant number of paragraphs"
    # Check a specific paragraph for numbering, assuming it's a list item
    numbered_items = [p for p in data["paragraphs_xml"] if p.numId is not None and p.ilvl is not None]
    assert len(numbered_items) > 0, "Expected to find at least one numbered list item"
    first_numbered = numbered_items[0]
    assert first_numbered.list_type == 'number' or first_numbered.list_type == 'bullet'
    assert first_numbered.text.strip() != ""

    # 2. Test for tables
    assert len(data["tables"]) > 0, "Expected to find at least one table"
    table = data["tables"][0]
    assert isinstance(table, TableRecord)
    assert len(table.rows) > 0, "Table should have rows"
    first_row_cells = table.rows[0]
    assert len(first_row_cells) > 0, "Table row should have cells"
    first_cell = first_row_cells[0]
    assert isinstance(first_cell, TableCellRecord)

    # 3. Test for drawings
    assert len(data["drawings_raw"]) > 0, "Expected to find at least one drawing"
    drawing = data["drawings_raw"][0]
    assert "did" in drawing
    assert drawing["did"].startswith("d")
    assert "kind" in drawing # kind can be None, but key should exist
    assert "context" in drawing
    assert "p_idx" in drawing["context"]

    # 4. Test for relationships
    assert "map" in data["relationships"]
    rels_map = data["relationships"]["map"]
    assert len(rels_map) > 0, "Expected some relationships"