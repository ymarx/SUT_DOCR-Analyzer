from typing import List, Dict
from mypkg.core.base_parser import ParagraphRecord, RunRecord
import re

def _merge_paragraphs(paragraphs_docx: List[ParagraphRecord], paragraphs_xml: List[ParagraphRecord]) -> List[ParagraphRecord]:
    """
    [모듈 내부 함수] 인덱스(문서 내 순서)를 기준으로 두 문단 목록을 병합합니다.
    """
    xml_map: Dict[int, ParagraphRecord] = {p.doc_index: p for p in paragraphs_xml if p.doc_index is not None}
    merged_paragraphs: List[ParagraphRecord] = []
    
    for p_docx in paragraphs_docx:
        matching_xml_p = xml_map.get(p_docx.doc_index) if p_docx.doc_index is not None else None

        if matching_xml_p:
            p_docx.numId = matching_xml_p.numId
            p_docx.ilvl = matching_xml_p.ilvl
            p_docx.numFmt = matching_xml_p.numFmt
            p_docx.list_type = matching_xml_p.list_type
        
        merged_paragraphs.append(p_docx)

    return merged_paragraphs

def _clean_runs(paragraphs: List[ParagraphRecord]) -> List[ParagraphRecord]:
    """
    [모듈 내부 함수] 문단 내의 Run(텍스트 조각)들을 정리합니다.
    """
    for p in paragraphs:
        if not p.runs:
            continue

        for r in p.runs:
            t = r.text.replace("\u00A0"," ").replace("\u200B","")
            t = " ".join(t.replace("\r"," ").replace("\t"," ").split())
            r.text = t

        merged_runs: List[RunRecord] = []
        for r in p.runs:
            if not r.text: continue
            
            if (merged_runs and 
                merged_runs[-1].b == r.b and
                merged_runs[-1].i == r.i and
                merged_runs[-1].u == r.u and
                merged_runs[-1].rStyle == r.rStyle and
                merged_runs[-1].sz == r.sz and
                merged_runs[-1].color == r.color):
                merged_runs[-1].text += " " + r.text
            else:
                merged_runs.append(r)
        
        p.runs = merged_runs
        p.text = " ".join([r.text for r in p.runs]).strip()
        
    return paragraphs

class ParagraphSanitizer:
    """
    docx 문서로부터 추출된 다양한 문단 정보들을 병합하고 정제하는 클래스입니다.
    """
    def apply(self, paragraphs_docx: List[ParagraphRecord], paragraphs_xml: List[ParagraphRecord]) -> List[ParagraphRecord]:
        """
        두 종류의 문단 목록을 입력받아 병합하고 정제한 후, 단일화된 문단 목록을 반환합니다.
        """
        merged = _merge_paragraphs(paragraphs_docx, paragraphs_xml)
        cleaned = _clean_runs(merged)
        return cleaned