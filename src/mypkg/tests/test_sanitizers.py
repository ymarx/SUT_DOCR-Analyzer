import pytest
import json
from pathlib import Path
from dataclasses import asdict

from mypkg.components.parser.docx_parser import DocxContentParser
from mypkg.components.parser.xml_parser import DocxXmlParser
from mypkg.components.sanitizer.paragraph_sanitizer import _merge_paragraphs, _clean_runs
from mypkg.components.sanitizer.table_sanitizer import TableSanitizer
from mypkg.components.sanitizer.diagram_sanitizer import DiagramSanitizer
from mypkg.core.base_parser import ParagraphRecord, RunRecord, TableRecord, TableCellRecord, DrawingRecord

def _get_fixture_path(filename: str) -> Path:
    return Path(f"src/mypkg/tests/fixtures/{filename}").resolve()

def test_paragraph_sanitizer_logic():
    """ParagraphSanitizer의 병합 및 정제 로직을 테스트합니다."""
    # 입력 데이터 준비
    p_docx1 = ParagraphRecord(text="1. 서론", doc_index=0, style="h1", runs=[
        RunRecord(text="1.", b=True, i=False, u=False), 
        RunRecord(text=" 서론", b=True, i=False, u=False)
    ])
    p_docx2 = ParagraphRecord(text="본문입니다.", doc_index=1, style="Normal", runs=[
        RunRecord(text="본문입니다.", b=False, i=False, u=False)
    ])
    paragraphs_docx = [p_docx1, p_docx2]

    p_xml1 = ParagraphRecord(text="1. 서론", doc_index=0, numId="1", ilvl="0", numFmt="decimal", list_type="number")
    p_xml2 = ParagraphRecord(text="본문입니다.", doc_index=1, numId=None, ilvl=None)
    paragraphs_xml = [p_xml1, p_xml2]

    # Sanitize
    merged = _merge_paragraphs(paragraphs_docx, paragraphs_xml)
    result = _clean_runs(merged)

    # 결과 검증
    assert len(result) == 2
    res_p1 = result[0]
    assert res_p1.text == "1. 서론"
    assert len(res_p1.runs) == 1
    assert res_p1.numId == "1"
    res_p2 = result[1]
    assert res_p2.text == "본문입니다."
    assert res_p2.numId is None

def test_table_sanitizer_flatten():
    """TableSanitizer가 테이블 데이터를 올바르게 평탄화하는지 테스트합니다."""
    ts = TableSanitizer()
    tables = [TableRecord(
        tid="t0",
        rows=[
            [TableCellRecord(text="헤더A", gridSpan=2, vMerge=None),
             TableCellRecord(text="B", gridSpan=1, vMerge=None)],
            [TableCellRecord(text="", gridSpan=2, vMerge="continue"),
             TableCellRecord(text="C", gridSpan=1, vMerge=None)],
        ]
    )]
    out = ts.apply(tables, [])
    assert out[0]["data"][0] == ["헤더A", "헤더A", "B"]

def test_diagram_sanitizer_apply():
    """DiagramSanitizer가 raw 데이터를 새로운 DrawingRecord로 올바르게 변환하는지 테스트합니다."""
    sanitizer = DiagramSanitizer()
    
    # 실제와 유사한 XML 스니펫을 포함하는 테스트 데이터
    drawings_raw = [
        {
            "did": "d0",
            "kind": "shape",
            "shape": {"preset": "rect"},
            "texts_raw": [{"text": "  테스트  텍스트 "}],
            "xml_snippet": '''<w:drawing xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" 
                                       xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">
                    <wp:anchor distT="0" distB="0" distL="114300" distR="114300" simplePos="0" relativeHeight="251658240" 
                               behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">
                        <wp:extent cx="150000" cy="100000"/>
                    </wp:anchor>
                </w:drawing>''',
            "context": {"doc_index": 5, "tbl_idx": None}
        }
    ]

    result = sanitizer.apply(drawings_raw, [])

    assert len(result) == 1
    d0 = result[0]
    assert isinstance(d0, DrawingRecord)
    assert d0.did == "d0"
    assert d0.kind == "shape"
    assert d0.preset == "rect"
    assert d0.anchor_type == "anchor"
    assert d0.extent["w"] == 150000
    assert d0.extent["h"] == 100000
    assert d0.text["norm"] == "테스트 텍스트"
    assert d0.context["doc_index"] == 5 # doc_index 확인

@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_filename", [
    "sample2_section.docx",
])
async def test_full_pipeline_and_save_sanitized_output(fixture_filename):
    """전체 파이프라인(파서 -> sanitizer)을 실행하고 최종 결과를 저장합니다."""
    sample = _get_fixture_path(fixture_filename)
    if not sample.exists():
        pytest.skip(f"Sample DOCX not found: {sample}")

    # 1. 파싱
    docx_parser = DocxContentParser()
    xml_parser = DocxXmlParser()
    res_docx = await docx_parser.parse(sample)
    res_xml = await xml_parser.parse(sample)
    assert res_docx.success and res_xml.success

    docx_content = res_docx.content["docx_content"]
    xml_content = res_xml.content["docx_xml"]

    # 2. 정제
    # ParagraphSanitizer는 클래스 인스턴스화 없이 모듈 함수를 직접 호출
    sanitized_paragraphs = _merge_paragraphs(docx_content["paragraphs_docx"], xml_content["paragraphs_xml"])
    sanitized_paragraphs = _clean_runs(sanitized_paragraphs)

    diag_sanitizer = DiagramSanitizer()
    sanitized_drawings = diag_sanitizer.apply(xml_content["drawings_raw"], sanitized_paragraphs)
    table_sanitizer = TableSanitizer()
    sanitized_tables = table_sanitizer.apply(xml_content["tables"], sanitized_paragraphs)

    # 3. 최종 결과 취합
    final_result = {
        "paragraphs": [asdict(p) for p in sanitized_paragraphs],
        "drawings": [asdict(d) for d in sanitized_drawings],
        "tables": sanitized_tables,
        "headers": [asdict(h) for h in xml_content["headers"]],
        "footers": [asdict(f) for f in xml_content["footers"]],
        "relationships": {"map": {k: asdict(v) for k, v in xml_content["relationships"]["map"].items()}},
        "inline_images": [asdict(i) for i in docx_content["inline_images"]],
    }

    # 4. JSON 저장
    outdir = Path("src/mypkg/tests/output/sanitizer").resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / f"{sample.stem}_output_sanitized.json"

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    
    print(f"\n[INFO] Sanitized 결과 저장됨: {out_path}")
