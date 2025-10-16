# src/mypkg/components/sanitizer/diagram_sanitizer.py

from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from mypkg.core.base_parser import DrawingRecord, ParagraphRecord

NS = {
    "w":   "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp":  "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a":   "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "wpg": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "v":   "urn:schemas-microsoft-com:vml",
}

_CIRCLED_NUM_RE = re.compile(r"[\u2460-\u2473\u3251-\u325F\u32B1-\u32BF]")  # ① ~ ⑳ 등

class DiagramSanitizer:
    """
    drawings_raw(dict 리스트)를 받아 DrawingRecord 리스트로 변환.
    - 다양한 후처리(군집/정렬)는 이후 단계에서 수행
    - 여기서는 '필수 스키마' 채우기에 집중
    """
    def apply(self, drawings_raw: List[Dict[str, Any]], paragraphs: List[ParagraphRecord]) -> List[DrawingRecord]:
        recs: List[DrawingRecord] = []
        all_paragraphs = {p.doc_index: p for p in paragraphs if p.doc_index is not None}

        for d in drawings_raw or []:
            did = d.get("did")
            # kind가 비어있거나 preset만 있는 경우 보정
            kind = d.get("kind") or "shape"
            if not d.get("kind"):
                preset_guess = (d.get("shape") or {}).get("preset", "") or ""
                if "arrow" in preset_guess.lower() or "connector" in preset_guess.lower():
                    kind = "connector"

            # preset
            preset = None
            if isinstance(d.get("shape"), dict):
                preset = d["shape"].get("preset")

            # 텍스트 수집/정규화
            raw_runs: List[str] = []
            # 1차: drawings_raw.texts_raw
            for n in (d.get("texts_raw") or []):
                t = n.get("text")
                if t: raw_runs.append(str(t))
            # 2차: shape.texts_raw 보강
            if not raw_runs and isinstance(d.get("shape"), dict):
                for n in (d["shape"].get("texts_raw") or []):
                    t = n.get("text")
                    if t: raw_runs.append(str(t))
            norm = _clean_text(" ".join(raw_runs)) if raw_runs else ""
            circled = bool(_CIRCLED_NUM_RE.search(norm)) if norm else False

            # xml 파싱
            xml_snippet = d.get("xml_snippet") or "<w:drawing/>"
            try:
                root = ET.fromstring(xml_snippet)
            except Exception:
                root = ET.fromstring("<w:drawing xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'/>")
            # ① drawings_raw.anchor가 있으면 우선 사용(재파싱 최소화)
            anchor_dict = d.get("anchor") if isinstance(d.get("anchor"), dict) else None
            if anchor_dict:
                anchor_type = anchor_dict.get("type")
                rel_h = anchor_dict.get("rel_from_h")
                rel_v = anchor_dict.get("rel_from_v")
                pos_x = int((anchor_dict.get("pos_offset") or {}).get("x", 0))
                pos_y = int((anchor_dict.get("pos_offset") or {}).get("y", 0))
                ext_w = int((anchor_dict.get("extent") or {}).get("w", 0))
                ext_h = int((anchor_dict.get("extent") or {}).get("h", 0))
                wrap  = anchor_dict.get("wrap")
                z     = int(anchor_dict.get("z") or 0)
                xfrm  = {"off":{"x":0,"y":0},"ext":{"w":0,"h":0},"rotation":0}
                simple_pos = {"enabled": False, "x": 0, "y": 0}
            else:
                # ② anchor 사전이 없으면 XML에서 파생(기존 로직 유지)
                anchor_type = _detect_anchor_type(root)
                anchor = root.find(".//wp:anchor", NS) if anchor_type == "anchor" else None
                inline = root.find(".//wp:inline", NS) if anchor_type == "inline" else None

                rel_h = rel_v = None
                pos_x = pos_y = 0
                ext_w = ext_h = 0
                z = 0
                wrap = None
                simple_pos = {"enabled": False, "x": 0, "y": 0}
                
                if anchor is not None:
                    # relFrom
                    hnode = anchor.find("./wp:positionH", NS)
                    vnode = anchor.find("./wp:positionV", NS)
                    rel_h = hnode.get("relativeFrom") if hnode is not None else None
                    rel_v = vnode.get("relativeFrom") if vnode is not None else None
                    # posOffset
                    ph = anchor.find("./wp:positionH/wp:posOffset", NS)
                    pv = anchor.find("./wp:positionV/wp:posOffset", NS)
                    pos_x = _to_int(ph.text) if ph is not None else 0
                    pos_y = _to_int(pv.text) if pv is not None else 0
                    # extent
                    ext = anchor.find("./wp:extent", NS)
                    ext_w = _to_int(ext.get("cx")) if ext is not None else 0
                    ext_h = _to_int(ext.get("cy")) if ext is not None else 0
                    # z-order
                    z = _to_int(anchor.get("relativeHeight"))
                    # wrap
                    wrap = _extract_wrap(anchor)
                    # simplePos
                    sp = anchor.find("./wp:simplePos", NS)
                    if sp is not None and anchor.get("simplePos") == "1":
                        simple_pos = {"enabled": True, "x": _to_int(sp.get("x")), "y": _to_int(sp.get("y"))}
                    # xfrm
                    graphic_data = anchor.find(".//a:graphic/a:graphicData", NS)
                    xfrm = _extract_xfrm(graphic_data if graphic_data is not None else anchor)
                    
                elif inline is not None:
                    # posOffset 없음(인라인), extent만
                    ext = inline.find("./wp:extent", NS)
                    ext_w = _to_int(ext.get("cx")) if ext is not None else 0
                    ext_h = _to_int(ext.get("cy")) if ext is not None else 0
                    wrap = None
                    z = 0
                    xfrm = _extract_xfrm(inline.find(".//a:graphic/a:graphicData", NS))
                    
                else:
                    # VML 등
                    xfrm = {"off": {"x": 0, "y": 0}, "ext": {"w": 0, "h": 0}, "rotation": 0}


            # connector 연결 id 추출(있으면)
            st_cxn_id = end_cxn_id = None
            cxn = root.find(".//a:nvCxnSpPr/a:cNvCxnSpPr", NS)
            if cxn is not None:
                st = cxn.find("./a:stCxn", NS)
                en = cxn.find("./a:endCxn", NS)
                st_cxn_id = st.get("id") if st is not None else None
                end_cxn_id = en.get("id") if en is not None else None

            # 이미지 정보(있으면)
            image_obj = None
            if isinstance(d.get("image"), dict):
                # 원본이 rIds 리스트만 줄 수도 있음
                rids = d["image"].get("rIds") or d["image"].get("rids") or []
                filename = d["image"].get("filename")
                image_obj = {"rIds": rids}
                if filename:
                    image_obj["filename"] = filename

            # 포지션 신뢰도
            pos_conf = _position_confidence(anchor_type, rel_h, rel_v)
            
            # context 주입: xml_parser 단계에서 올린 값 우선
            ctx = d.get("context", {})
            doc_index = ctx.get("doc_index")
            preceding_text = None
            if doc_index is not None and doc_index > 0:
                preceding_para = all_paragraphs.get(doc_index - 1)
                if preceding_para:
                    preceding_text = preceding_para.text
            ctx["preceding_text"] = preceding_text
                
            recs.append(DrawingRecord(
                did=did,
                kind=kind,
                preset=preset,
                anchor_type=anchor_type,
                rel_from_h=rel_h,
                rel_from_v=rel_v,
                pos_offset={"x": pos_x, "y": pos_y},
                extent={"w": ext_w, "h": ext_h},
                wrap=wrap,
                z=z,
                context=ctx,
                text={
                    "raw_runs": [_clean_text(t) for t in (d.get("texts_raw") and [x.get("text","") for x in d["texts_raw"]] or []) if t],
                    "norm": norm,
                    "circled_num": circled
                },
                connector={
                    "is_connector": _is_connector(kind, preset),
                    "st_cxn_id": st_cxn_id,
                    "end_cxn_id": end_cxn_id,
                    "has_arrow_head": None,
                    "has_arrow_tail": None
                },
                xfrm=xfrm,
                simple_pos=simple_pos,
                position_confidence=pos_conf,
                page_hint=d.get("page"),   # xml_parser가 넣어준 page 값
                group_hierarchy={"parents": []},
                image=image_obj,
                provenance={
                    "xml_snippet": d.get("xml_snippet"),
                    "node_path_hint": None
                }
            ))

        return recs


def _to_int(text: Optional[str], default: int = 0) -> int:
    try:
        return int(text) if text is not None else default
    except Exception:
        return default

def _clean_text(s: str) -> str:
    s = s.replace("\u00A0", " ").replace("\u200B", "")
    return " ".join(s.split())

def _detect_anchor_type(root: ET.Element) -> Optional[str]:
    if root.find(".//wp:anchor", NS) is not None:
        return "anchor"
    if root.find(".//wp:inline", NS) is not None:
        return "inline"
    if root.find(".//v:shape", NS) is not None:
        return "vml"
    return None

def _extract_wrap(anchor: Optional[ET.Element]) -> Optional[str]:
    if anchor is None:
        return None
    for t in ["wrapNone","wrapSquare","wrapThrough","wrapTopAndBottom","wrapTight"]:
        if anchor.find(f"./wp:{t}", NS) is not None:
            return t
    return None

def _extract_xfrm(elem: Optional[ET.Element]) -> Dict[str, Any]:
    out = {"off": {"x": 0, "y": 0}, "ext": {"w": 0, "h": 0}, "rotation": 0}
    if elem is None:
        return out
    xfrm = elem.find(".//a:xfrm", NS)
    if xfrm is None:
        return out
    off = xfrm.find("./a:off", NS)
    ext = xfrm.find("./a:ext", NS)
    out["off"]["x"] = _to_int(off.get("x")) if off is not None else 0
    out["off"]["y"] = _to_int(off.get("y")) if off is not None else 0
    out["ext"]["w"] = _to_int(ext.get("cx")) if ext is not None else 0
    out["ext"]["h"] = _to_int(ext.get("cy")) if ext is not None else 0
    rot = xfrm.get("rot")
    out["rotation"] = _to_int(rot) if rot is not None else 0
    return out

def _position_confidence(anchor_type: Optional[str], rel_h: Optional[str], rel_v: Optional[str]) -> float:
    if anchor_type == "inline":
        return 0.0
    if anchor_type == "vml":
        return 0.8
    # anchor:
    vals = {rel_h, rel_v}
    if "page" in vals or "margin" in vals:
        return 1.0
    if "column" in vals or "paragraph" in vals or "character" in vals:
        return 0.6
    return 0.5

def _is_connector(kind: str, preset: Optional[str]) -> bool:
    if kind == "connector":
        return True
    if not preset:
        return False
    p = preset.lower()
    return ("arrow" in p) or ("connector" in p)