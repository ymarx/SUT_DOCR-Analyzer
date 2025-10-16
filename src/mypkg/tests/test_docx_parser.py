import os
from pathlib import Path
import pytest
import json
from dataclasses import asdict
from mypkg.components.parser.docx_parser import DocxContentParser

def _get_fixture_path(filename: str) -> Path:
    return Path(f"src/mypkg/tests/fixtures/{filename}").resolve()

def _get_output_dir() -> Path:
    out = Path("src/mypkg/tests/output/parser").resolve()
    out.mkdir(parents=True, exist_ok=True)
    return out

@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_filename", [
    "sample2_section.docx",
])
async def test_docx_parse_success(fixture_filename):
    sample = _get_fixture_path(fixture_filename)
    if not sample.exists():
        pytest.skip(f"Sample DOCX not found: {sample}")

    parser = DocxContentParser()
    assert ".docx" in parser.supported_formats

    res = await parser.parse(sample)
    assert res.success, f"docx parse failed: {res.error}"

    # 반환 payload 기본 키 검사
    assert isinstance(res.content, dict), "payload must be a dict"
    assert "docx_content" in res.content, "payload must contain 'docx_content'"

    content = res.content["docx_content"]
    assert isinstance(content, dict)
    # 변경된 키 확인
    for key in ("paragraphs_docx", "inline_images"):
        assert key in content, f"missing key in docx_content: {key}"

    # 타입 체크
    assert isinstance(content["paragraphs_docx"], list)
    assert isinstance(content["inline_images"], list)

@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_filename", [
    "sample2_section.docx",
])
async def test_docx_runs_and_styles_shape(fixture_filename):
    sample = _get_fixture_path(fixture_filename)
    if not sample.exists():
        pytest.skip(f"Sample DOCX not found: {sample}")

    parser = DocxContentParser()
    res = await parser.parse(sample)
    assert res.success

    paras = res.content["docx_content"]["paragraphs_docx"]
    # 문단이 하나라도 있으면 run 필드 구조가 맞는지 확인
    if paras:
        p0 = paras[0]
        assert hasattr(p0, "runs")
        assert isinstance(p0.runs, list)
        if p0.runs:
            r0 = p0.runs[0]
            # RunRecord 속성 확인
            assert hasattr(r0, "text")
            assert hasattr(r0, "b")
            assert hasattr(r0, "i")
            assert hasattr(r0, "u")
            assert hasattr(r0, "rStyle")
            assert hasattr(r0, "sz")
            assert hasattr(r0, "color")


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_filename", [
    "sample2_section.docx",
])
async def test_extract_docx_content_to_json(fixture_filename):
    sample = _get_fixture_path(fixture_filename)
    if not sample.exists():
        pytest.skip(f"Sample DOCX not found: {sample}")

    outdir = _get_output_dir()
    filename_stem = sample.stem

    parser = DocxContentParser()
    res = await parser.parse(sample)
    assert res.success

    # dataclass를 dict로 변환하여 JSON 저장
    content_dict = asdict(res)

    out_path = outdir / f"{filename_stem}_output_docx.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(content_dict, f, ensure_ascii=False, indent=2)

    print(f"\n[INFO] 결과 저장됨: {out_path}")