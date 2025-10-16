"""
레이아웃 어셈블러: 블록을 섹션 구조에 배치

개요
- 문단/리스트/테이블/다이어그램 블록을 하나의 시퀀스로 모아 정렬한 뒤,
  섹션(span 범위)에 따라 각 섹션에 귀속시킵니다.

핵심 구성요소
- assign_blocks_to_sections: 재귀적으로 섹션 트리를 순회하며 블록을 span 규칙에 맞춰 배치
- build_paragraph_blocks: 제목/리스트로 소비된 문단을 제외한 순수 문단 블록 생성
- build_diagram_blocks: 다이어그램 분석 결과를 블록으로 래핑

사용 흐름
1) section_analyzer.build_sections → 섹션/heading 인덱스 획득
2) analyze_lists/analyze_tables → list/table 블록 생성, consumed 인덱스 수집
3) build_paragraph_blocks → 나머지 일반 문단을 블록화
4) build_diagram_blocks → 다이어그램을 블록화
5) 합쳐서 정렬 후 assign_blocks_to_sections로 섹션에 배치

자세한 설명은 docs/LAYOUT_ASSEMBLER.md 참고
"""

# mypkg/components/assembler/layout_assembler.py
from __future__ import annotations
from typing import List, Dict, Any
from mypkg.core.docjson_types import ContentBlock, Section
import re

def _collapse_spaces(s: str) -> str:
    return re.sub(r"\s{2,}", " ", s).strip()

def assign_blocks_to_sections(sections: List[Section], blocks: List[ContentBlock]) -> None:
    """섹션의 [start,end) 범위에 포함되는 블록을 재귀적으로 배치한다.

    알고리즘
    - 각 루트 섹션에 대해 put()을 호출하여, 자신의 span 내 블록을 수집
    - 자식 섹션의 span에 속하는 블록은 먼저 자식에게 위임 후 부모 후보에서 제거
    - 최종적으로 남은 블록을 doc_index 오름차순으로 자신의 blocks에 추가
    """
    def put(sec: Section, cands: List[ContentBlock]):
        s, e = sec.span
        mine = [b for b in cands if s <= b.doc_index < e]

        for child in sec.subsections:
            child_cands = [b for b in mine if child.span[0] <= b.doc_index < child.span[1]]
            put(child, child_cands)
            child_ids = {id(b) for b in child.blocks}
            mine = [b for b in mine if id(b) not in child_ids]

        mine.sort(key=lambda b: b.doc_index)
        sec.blocks.extend(mine)
        sec.block_ids.extend([b.id for b in mine])

    for root in sections:
        put(root, blocks)

def build_paragraph_blocks(paragraphs: List[Dict[str, Any]], skip_docidx: set, heading_idx: set) -> List[ContentBlock]:
    """제목/리스트 등으로 소비된 인덱스를 제외하고 순수 문단만 ContentBlock으로 생성"""
    out: List[ContentBlock] = []
    for p in sorted(paragraphs, key=lambda x: x.get("doc_index", 0)):
        di = p.get("doc_index")
        if di in skip_docidx or di in heading_idx:
            continue
        text = _collapse_spaces(p.get("text") or "")
        if not text:
            continue
        out.append(ContentBlock(
            id=f"p{di}", type="paragraph", doc_index=di,
            text=text, level=None, page=None, bbox=None, semantic=None,
            table=None, list_data=None, diagram=None
        ))
    return out

def build_diagram_blocks(diagrams: List[Dict[str, Any]] | None) -> List[ContentBlock]:
    """다이어그램 분석 결과를 diagram 타입 블록으로 래핑"""
    blks: List[ContentBlock] = []
    for d in diagrams or []:
        di = d.get("doc_index", -1)
        blks.append(ContentBlock(
            id=d.get("id", f"diagram_{di}"), type="diagram", doc_index=di,
            text=None, level=None, page=None, bbox=None, semantic=None,
            table=None, list_data=None, diagram=d
        ))
    return blks
