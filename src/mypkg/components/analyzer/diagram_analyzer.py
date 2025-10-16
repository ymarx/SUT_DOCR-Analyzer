from __future__ import annotations

import logging
import re
from collections import defaultdict
from math import hypot
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import asdict, is_dataclass
from pathlib import Path

from mypkg.core.docjson_types import (
    DiagramData, ProcessStep, DiagramConnector, DiagramType,
)
from mypkg.core.io import write_json_output, save_diagram_components_from_sanitized

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# 간단한 마커 인식(①~⑳, 1., 2), I. 등)
# ──────────────────────────────────────────────────────────────────────────────
CIRCLED_MAP = {"①":1,"②":2,"③":3,"④":4,"⑤":5,"⑥":6,"⑦":7,"⑧":8,"⑨":9,"⑩":10,
               "⑪":11,"⑫":12,"⑬":13,"⑭":14,"⑮":15,"⑯":16,"⑰":17,"⑱":18,"⑲":19,"⑳":20}
ROMAN_MAP   = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,"IX":9,"X":10,
               "XI":11,"XII":12,"XIII":13,"XIV":14,"XV":15,"XVI":16,"XVII":17,"XVIII":18,"XIX":19,"XX":20}
PATTS = [
    re.compile(r"^\s*(?:STEP\s*)?(?P<num>\d{1,3})\s*[\.\)\-:>\]]\s*(?P<label>.+)$"),
    re.compile(r"^\s*(?P<num>i{1,3}|iv|v|vi{0,3}|ix|x|xi{0,3}|xiv|xv|xvi{0,3}|xix|xx)\s*[\.\)\-:>\]]\s*(?P<label>.+)$"),
    re.compile(r"^\s*(?P<num>\d{1,3})\s+(?P<label>.+)$"),
]

def _parse_marker(text: str, circled: bool) -> Tuple[int, str, Optional[str], str]:
    """(sequence>=0, title, marker_type, marker_literal)"""
    t = (text or "").strip()
    if not t:
        return 0, "", None, ""
    if circled and t[0] in CIRCLED_MAP:
        seq = CIRCLED_MAP[t[0]]
        return seq, t[1:].strip(), "circled", t[0]
    for p in PATTS:
        m = p.match(t)
        if m:
            tok = m.group("num")
            if tok.isdigit():
                return int(tok), m.group("label").strip(), "arabic", tok
            val = ROMAN_MAP.get(tok.upper(), 0)
            return val, m.group("label").strip(), ("roman" if val else None), tok
    return 0, t, None, ""

def _is_connector(d: Dict[str, Any]) -> bool:
    if d.get("connector", {}).get("is_connector"):
        return True
    preset = (d.get("preset") or "")
    return ("arrow" in preset.lower())

def _pos(s: Dict[str, Any]) -> Tuple[float, float, float, float]:
    off = (s.get("pos_offset") or (s.get("xfrm", {}) or {}).get("off") or {})
    ext = (s.get("extent") or {})
    return float(off.get("x", 0)), float(off.get("y", 0)), float(ext.get("cx", 0)), float(ext.get("cy", 0))

def _center(s: Dict[str, Any]) -> Tuple[float, float]:
    x, y, w, h = _pos(s)
    return x + w / 2.0, y + h / 2.0


class DiagramAnalyzer:
    """
    초간단 파이프라인:
      1) drawings를 doc_index별로 나눠 각 doc_index마다 DiagramData 1개 생성
      2) doc_index가 연속(예: 19→20→21)이면 순서대로 '붙여서' 스티칭
      3) step 순서는 마커가 있으면 그 순서, 없으면 좌표 x+y 로 정렬해 1..N 부여
      4) 커넥터는 간단히 '가장 가까운 두 스텝'을 추정해 from/to를 매긴다
    """

    def __init__(self, sanitized: Dict[str, Any]):
        self.data = sanitized
        self.drawings: List[Dict[str, Any]] = (
            sanitized.get("drawings", []) if isinstance(sanitized.get("drawings", []), list) else []
        )

    # ------------------------------------------------------------------ 퍼블릭
    def extract(self) -> List[DiagramData]:
        if not self.drawings:
            return []

        by_doc: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for d in self.drawings:
            doc_idx = ((d.get("context") or {}).get("doc_index"))
            if doc_idx is None:
                # doc_index 없는 것은 스킵
                continue
            by_doc[int(doc_idx)].append(d)

        # 1) doc_index별 부분 다이어그램 생성
        parts: List[DiagramData] = []
        for doc_idx in sorted(by_doc.keys()):
            part = self._build_for_doc(doc_idx, by_doc[doc_idx])
            if part and part.steps:
                parts.append(part)

        if not parts:
            return []

        # 2) 인접 doc_index만 병합(19↔20↔21 …)
        parts.sort(key=lambda d: d.doc_index)
        merged: List[DiagramData] = []
        cur = parts[0]
        for nxt in parts[1:]:
            if nxt.doc_index == cur.doc_index + 1:
                cur = self._merge_adjacent(cur, nxt)
                logger.info("[stitch:adjacent-doc] %s + %s -> %s (doc %d~%d)",
                            cur.id, nxt.id, cur.id, min(cur.doc_index, nxt.doc_index), max(cur.doc_index, nxt.doc_index))
            else:
                merged.append(cur)
                cur = nxt
        merged.append(cur)
        return merged

    # --------------------------------------------------------------- 빌더
    def _build_for_doc(self, doc_index: int, items: List[Dict[str, Any]]) -> DiagramData:
        shapes = [s for s in items if (s.get("kind") == "shape") and not _is_connector(s)]
        conns  = [s for s in items if _is_connector(s)]

        # 스텝
        steps: List[ProcessStep] = []
        for s in shapes:
            tinfo = (s.get("text") or {})
            raw = tinfo.get("norm") or (tinfo.get("raw_runs") or [""])[0]
            seq, label, mtype, literal = _parse_marker(raw, bool(tinfo.get("circled_num")))
            if seq <= 0:
                # 좌표 기반 정렬을 위해 일단 0으로 넣어두고 나중에 재부여
                pass
            steps.append(ProcessStep(
                sequence=seq,
                title=label or raw,
                details=[],
                marker=literal,
                marker_type=mtype,
                raw_text=raw,
                dids=[s.get("did")] if s.get("did") else [],
                doc_index=doc_index,
                linked_text_paragraphs=[],
                confidence=0.9 if seq > 0 else 0.6,
            ))

        # 순서 보정: 마커 없는 경우 x+y 기준 정렬 후 1..N 부여
        if steps:
            have_any = any(st.sequence > 0 for st in steps)
            if not have_any:
                order = []
                centers = {}
                for s in shapes:
                    if s.get("did"):
                        centers[s["did"]] = _center(s)
                for st in steps:
                    did = st.dids[0] if st.dids else None
                    cx, cy = centers.get(did, (0.0, 0.0))
                    order.append((cx + cy, st))
                order.sort(key=lambda x: x[0])
                for i, (_, st) in enumerate(order, 1):
                    st.sequence = i
            else:
                # 마커 있는 경우 sequence 오름차순으로만 정렬
                steps.sort(key=lambda st: (st.sequence or 10**9, st.title or ""))

        # connectors (가까운 두 스텝 연결 추정 — 선택적)
        diag_connectors: List[DiagramConnector] = []
        if conns and steps:
            # 스텝 중심좌표 맵
            centers = {}
            shape_by_did = {s.get("did"): s for s in shapes if s.get("did")}
            for st in steps:
                did = st.dids[0] if st.dids else None
                if did in shape_by_did:
                    centers[st.sequence] = _center(shape_by_did[did])

            def nearest_two(cx: float, cy: float) -> Optional[Tuple[int, int]]:
                if len(centers) < 2:
                    return None
                items = sorted(((hypot(cx - x, cy - y), seq) for seq, (x, y) in centers.items()), key=lambda t: t[0])
                return items[0][1], items[1][1]

            for c in conns:
                cx, cy = _center(c)
                pair = nearest_two(cx, cy)
                if not pair:
                    continue
                a_seq, b_seq = pair
                # 좌표 취득
                ax, ay = centers.get(a_seq, (cx, cy))
                bx, by = centers.get(b_seq, (cx, cy))
                # 좌→우 또는 상→하 대략적 방향성
                if (ax < bx) or (ay < by):
                    frm, to = a_seq, b_seq
                else:
                    frm, to = b_seq, a_seq
                diag_connectors.append(DiagramConnector(
                    did=c.get("did") or f"conn_{frm}_{to}",
                    type="arrow",
                    from_step=frm,
                    to_step=to,
                ))

        diag_id = f"diag_{doc_index}"
        dtype = DiagramType.SEQUENTIAL if len(steps) >= 2 else DiagramType.UNKNOWN

        return DiagramData(
            id=diag_id,
            doc_index=doc_index,
            diagram_type=dtype,
            anchor_heading=None,
            doc_indices=[doc_index],
            flow_direction=None,
            page_hint=self._majority_page(items),
            order_evidence=["numeric_marker"] if any(st.sequence > 0 for st in steps) else [],
            steps=steps,
            connectors=diag_connectors,
            bbox=None,
            notes=None,
        )

    # --------------------------------------------------------------- 스티치
    def _merge_adjacent(self, a: DiagramData, b: DiagramData) -> DiagramData:
        """doc_index가 연속일 때 b의 스텝/커넥터를 a 뒤에 이어 붙임.
           b의 스텝 번호가 1부터 다시 시작한다면 a의 max에 맞춰 offset을 더한다.
        """
        seqs_a = [st.sequence for st in a.steps if st.sequence > 0]
        max_a = max(seqs_a) if seqs_a else len(a.steps)

        seqs_b = [st.sequence for st in b.steps if st.sequence > 0]
        min_b = min(seqs_b) if seqs_b else 1

        # b 스텝 전체에 동일한 시퀀스 offset 적용 (커넥터도 동일하게 보정)
        offset = 0 if (min_b == max_a + 1) else (max_a - min_b + 1)

        new_steps: List[ProcessStep] = []
        new_steps.extend(a.steps)
        for st in b.steps:
            st2 = ProcessStep(
                sequence=(st.sequence + offset) if st.sequence > 0 else (len(new_steps) + 1),
                title=st.title,
                details=st.details[:],
                marker=st.marker,
                marker_type=st.marker_type,
                raw_text=st.raw_text,
                dids=st.dids[:],
                doc_index=st.doc_index,
                linked_text_paragraphs=st.linked_text_paragraphs[:],
                confidence=st.confidence,
            )
            new_steps.append(st2)

        new_conns: List[DiagramConnector] = []
        new_conns.extend(a.connectors)
        for c in b.connectors:
            new_conns.append(DiagramConnector(
                did=c.did,
                type=c.type,
                from_step=(c.from_step + offset) if c.from_step else c.from_step,
                to_step=(c.to_step + offset) if c.to_step else c.to_step,
            ))

        return DiagramData(
            id=a.id,  # 체인 유지
            doc_index=a.doc_index,  # 대표는 첫 문단
            diagram_type=a.diagram_type if a.diagram_type != DiagramType.UNKNOWN else b.diagram_type,
            anchor_heading=a.anchor_heading or b.anchor_heading,
            doc_indices=sorted(set((a.doc_indices or []) + (b.doc_indices or []))),
            flow_direction=a.flow_direction or b.flow_direction,
            page_hint=a.page_hint if a.page_hint is not None else b.page_hint,
            order_evidence=["numeric_marker"] if any(st.sequence > 0 for st in new_steps) else [],
            steps=new_steps,
            connectors=new_conns,
            bbox=None,
            notes=None,
        )

    # --------------------------------------------------------------- 헬퍼
    @staticmethod
    def _majority_page(items: List[Dict[str, Any]]) -> Optional[int]:
        counter: Dict[int, int] = defaultdict(int)
        for it in items:
            ph = it.get("page_hint")
            if isinstance(ph, int):
                counter[ph] += 1
        if not counter:
            return None
        return max(counter.items(), key=lambda kv: kv[1])[0]

def _serialize_diagram(d: Any) -> Dict[str, Any]:
    """DiagramData(또는 유사 객체) 단일 항목을 dict로 안전 직렬화."""
    # 1) 객체가 to_dict를 제공할 경우
    if hasattr(d, "to_dict") and callable(getattr(d, "to_dict")):
        return d.to_dict()  # type: ignore
    # 2) dataclass 인스턴스
    if is_dataclass(d):
        return asdict(d)  # type: ignore
    # 3) 이미 dict
    if isinstance(d, dict):
        return d
    # 4) 기타: 최소한의 안전장치
    raise TypeError(f"Unsupported diagram payload type: {type(d)}")

def extract_diagram_components(diagrams: List[Any]) -> Dict[str, Any]:
    """
    분석 결과(리스트)를 {'diagrams': [...]} 포맷으로 감쌈.
    - 내부 요소는 DiagramData 객체/데이터클래스/딕트 모두 허용
    """
    return {"diagrams": [_serialize_diagram(d) for d in (diagrams or [])]}


def _try_run_diagram_analyzer(ir: Dict[str, Any]) -> List[DiagramData]:
    try:
        analyzer = DiagramAnalyzer(ir)
        return analyzer.extract() or []
    except Exception as e:
        logger.error(f"Error running DiagramAnalyzer: {e}")
        return []

def emit_diagram_components_from_sanitized(ir: Dict[str, Any], sanitized_path: str | Path, basename: str) -> str:
    """sanitized JSON을 기반으로 다이어그램 컴포넌트를 산출해 저장한다."""
    diagrams = _try_run_diagram_analyzer(ir)  # List[DiagramData]
    payload = extract_diagram_components(diagrams)
    out_path = save_diagram_components_from_sanitized(payload, sanitized_path, basename)
    return str(out_path)
