
# mypkg/pipeline/layout_analyzer_pipeline.py
# Sanitized JSON을 받아 레이아웃 분석(섹션, 블록, 메타데이터)을 수행하고 DocJSON을 생성하는 파이프라인.
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import json

from mypkg.core.docjson_types import ContentBlock, Section, DocumentDocJSON
from mypkg.core.io import (
    component_paths_from_sanitized, meta_path_from_sanitized, load_json, save_json,
    load_available_components_from_sanitized, resolve_sanitized_path, save_blocks_components_from_sanitized,
    docjson_output_path_from_sanitized, base_dir_from_sanitized
)
from mypkg.components.analyzer.section_analyzer import build_sections, iter_sections
from mypkg.components.analyzer.list_table_analyzer import (
    emit_list_table_components_from_sanitized, analyze_lists, analyze_tables
)
from mypkg.components.analyzer.diagram_analyzer import emit_diagram_components_from_sanitized
from mypkg.components.analyzer.layout_assembler import (
    assign_blocks_to_sections, build_paragraph_blocks, build_diagram_blocks
)
from mypkg.components.analyzer.document_metadata_analyzer import DocumentMetadataAnalyzer

def _drop_drawings(ir: Dict[str, Any]) -> Dict[str, Any]:
    ir2 = dict(ir); ir2.pop("drawings", None); return ir2

def _blocks_from_dicts(arr: List[Dict[str, Any]]) -> List[ContentBlock]:
    return [ContentBlock.from_dict(d) for d in arr or []]

def run_pipeline(sanitized_path: str | Path, out_docjson_path: str | Path,
                 emit_components: bool = True, use_components: bool = True,
                 doc_version: str | None = None) -> DocumentDocJSON:
    """레이아웃 파이프라인 실행.

    1. Sanitized JSON을 읽고 섹션/컴포넌트/블록을 구축한다.
    2. 컴포넌트 파일 저장, 메타데이터 추출을 수행한다.
    3. 최종 DocJSON을 직렬화하여 지정된 경로에 저장한다.
    """

    sanitized_path = resolve_sanitized_path(sanitized_path)  # 절대 경로
    basename = base_dir_from_sanitized(sanitized_path).name  # {version}/{basename}/_sanitized → basename
    
    # 출력 경로가 디렉터리이거나 비어있으면 규칙에 따라 자동으로 파일 경로를 계산한다.
    odp = Path(out_docjson_path) if out_docjson_path else None
    if odp is None or (not odp.suffix):
        out_docjson_path = docjson_output_path_from_sanitized(sanitized_path, basename)
    else:
        out_docjson_path = odp.resolve()
    out_docjson_path.parent.mkdir(parents=True, exist_ok=True)

    ir = json.loads(sanitized_path.read_text(encoding="utf-8"))
    paragraphs = ir.get("paragraphs", [])
    tables_ir = ir.get("tables", [])

    # 1) 섹션 트리를 먼저 구성한다. 헤딩이 있는 단락은 나중에 문단 블록 생성 시 제외하기 위해 인덱스를 기록한다.
    sections: List[Section] = build_sections(paragraphs)
    heading_idx = {s.doc_index for s in iter_sections(sections)}

    # 2) 리스트/테이블/다이어그램 컴포넌트를 파일로 저장한다.
    #    emit_components가 False라면 여기서 생성을 건너뛰고 기존 파일만 사용한다.
    if emit_components:
        emit_list_table_components_from_sanitized(paragraphs, tables_ir, sanitized_path, basename)
        emit_diagram_components_from_sanitized(ir, sanitized_path, basename)
        
    # 다이어그램 원본(drawings)은 별도 컴포넌트 파일로 분리했으므로 이후 단계에서는 제거한다.
    ir = _drop_drawings(ir)

    # 3) 컴포넌트 파일을 읽거나, 파일이 없다면 즉석 분석을 수행한다.
    comps: Dict[str, Any] = load_available_components_from_sanitized(sanitized_path, basename) if use_components else {}

    # 3-1) Lists
    list_blocks: List[ContentBlock]
    consumed = set()
    if "lists" in comps:
        list_blocks = _blocks_from_dicts(comps["lists"])
        consumed = set(comps.get("consumed", []))
    else:
        list_blocks, consumed = analyze_lists(paragraphs)
    # 3-2) Tables
    if "tables" in comps:
        table_blocks = _blocks_from_dicts(comps["tables"])
    else:
        table_blocks = analyze_tables(tables_ir)
    # 3-3) Diagrams
    diagrams = comps.get("diagrams", [])
    diagram_blocks = build_diagram_blocks(diagrams)

    # 4) 문단 블록을 생성한다. 이미 리스트로 소비된 단락(consumed)과 헤딩은 제외한다.
    para_blocks = build_paragraph_blocks(paragraphs, skip_docidx=consumed, heading_idx=heading_idx)

    # 5) 모든 블록을 합쳐 문서 순서(doc_index, id)대로 정렬하고 각 섹션에 배치한다.
    all_blocks: List[ContentBlock] = para_blocks + list_blocks + table_blocks + diagram_blocks
    all_blocks.sort(key=lambda b: (b.doc_index, b.id))
    assign_blocks_to_sections(sections, all_blocks)

    # 6) 전체 블록을 컴포넌트 형태로도 저장해둔다. 재실행 시 재사용할 수 있다.
    blocks_payload = {"blocks": [b.to_dict() for b in all_blocks]}
    save_blocks_components_from_sanitized(blocks_payload, sanitized_path, basename)

    # 7) 문서 메타데이터를 추출하여 `_meta`에 저장한다.
    metadata = DocumentMetadataAnalyzer(json.loads(sanitized_path.read_text(encoding="utf-8"))).analyze()
    metadata_dict = metadata.to_dict()
    # 별도 메타 파일로도 저장
    save_json(metadata_dict, meta_path_from_sanitized(sanitized_path, basename))

    # 8) 최종 DocJSON을 구성한다.
    #    assign_blocks_to_sections 호출로 섹션에 블록이 이미 채워져 있고, flat blocks도 함께 보관한다.
    docjson = DocumentDocJSON(
        version=(doc_version or "0.1.0"),
        metadata=metadata,
        blocks=all_blocks,
        sections=sections,
    )

    save_json(docjson.to_dict(), out_docjson_path)
    return docjson
