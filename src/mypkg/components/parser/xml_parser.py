import logging, time, zipfile, xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Union, BinaryIO, Optional
from mypkg.core.base_parser import (
    BaseParser,
    ParseResult,
    TableRecord,
    TableCellRecord,
    HeaderFooterRecord,
    DrawingRecord, # 얘는 drawings_raw로 처리되고 나중에 정제됨
    RelationshipRecord,
    ParagraphRecord
)

log = logging.getLogger(__name__)

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic":"http://schemas.openxmlformats.org/drawingml/2006/picture",
    "wps":"http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "wpg":"http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

class DocxXmlParser(BaseParser):
    def __init__(self):
        super().__init__();
        self.supported_formats=['.docx']

    @property
    def provides(self) -> set:
        return {"tables","headers","footers","relationships","drawings_raw","paragraphs_xml"}

    async def parse(self, file_path: Union[str, Path, BinaryIO]) -> ParseResult:
        t0 = time.time()
        tables: List[TableRecord] = []
        headers: List[HeaderFooterRecord] = []
        footers: List[HeaderFooterRecord] = []
        relationships: Dict[str, RelationshipRecord] = {}
        drawings_raw: List[Dict[str, Any]] = []
        paragraphs_xml: List[ParagraphRecord] = []
        numbering_info: Dict[str, Dict[str, Any]] = {}

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                # 번호 포맷 정보 추출
                if "word/numbering.xml" in zf.namelist():
                    numbering_info = self._parse_numbering(zf.read("word/numbering.xml"))

                # 본문 처리
                if "word/document.xml" in zf.namelist():
                    root = ET.fromstring(zf.read("word/document.xml"))
                    body = root.find(".//w:body", NS)
                    if body is not None:
                        doc_index = 0
                        for elem in body:
                            if elem.tag == f'{{{NS["w"]}}}p':
                                para_record, drawing_records = self._parse_paragraph_element(elem, doc_index, numbering_info)
                                if para_record:
                                    paragraphs_xml.append(para_record)
                                if drawing_records:
                                    drawings_raw.extend(drawing_records)
                                doc_index += 1
                            elif elem.tag == f'{{{NS["w"]}}}tbl':
                                table_record = self._parse_table_element(elem, doc_index)
                                if table_record:
                                    tables.append(table_record)
                                doc_index += 1

                # 헤더/푸터
                for name in zf.namelist():
                    if name.startswith("word/header") and name.endswith(".xml"):
                        headers.append(HeaderFooterRecord(part=name, text=self._extract_text(zf.read(name))))
                    if name.startswith("word/footer") and name.endswith(".xml"):
                        footers.append(HeaderFooterRecord(part=name, text=self._extract_text(zf.read(name))))

                # rels
                if "word/_rels/document.xml.rels" in zf.namelist():
                    rels_root = ET.fromstring(zf.read("word/_rels/document.xml.rels"))
                    for rel in rels_root.findall('.//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
                        rid = rel.attrib.get("Id")
                        if rid:
                            relationships[rid] = RelationshipRecord(
                                rid=rid,
                                type=rel.attrib.get("Type",""),
                                target=rel.attrib.get("Target","")
                            )

            out = {
                "tables": tables,
                "headers": headers,
                "footers": footers,
                "relationships": {"map": relationships},
                "drawings_raw": drawings_raw,
                "paragraphs_xml": paragraphs_xml,
            }
            return ParseResult(True, {"docx_xml": out}, processing_time=time.time()-t0, payload_tag="docx_xml")

        except Exception as e:
            log.exception("xml parser failed")
            return ParseResult(False, error=str(e), processing_time=time.time()-t0, payload_tag="docx_xml")

    # ---- helpers ----
    def _extract_text(self, xml_bytes: bytes) -> str:
        root = ET.fromstring(xml_bytes)
        return " ".join(t.text for t in root.findall(".//w:t", NS) if t.text).strip()

    def _parse_numbering(self, numbering_xml_bytes: bytes) -> Dict[str, Dict[str, Any]]:
        numbering_info = {}
        root = ET.fromstring(numbering_xml_bytes)
        abstract_nums = {}
        for an in root.findall("w:abstractNum", NS):
            an_id = an.attrib.get(f'{{{NS["w"]}}}abstractNumId')
            if an_id is None:
                continue
            abstract_nums[an_id] = {}
            for lvl in an.findall("w:lvl", NS):
                lvl_idx = lvl.attrib.get(f'{{{NS["w"]}}}ilvl')
                numFmt_tag = lvl.find("w:numFmt", NS)
                if lvl_idx is not None and numFmt_tag is not None:
                    numFmt = numFmt_tag.attrib.get(f'{{{NS["w"]}}}val')
                    list_type = 'number' if numFmt not in ['bullet'] else 'bullet'
                    abstract_nums[an_id][lvl_idx] = {"numFmt": numFmt, "list_type": list_type}

        for num in root.findall("w:num", NS):
            num_id = num.attrib.get(f'{{{NS["w"]}}}numId')
            abstract_id_tag = num.find("w:abstractNumId", NS)
            if num_id is None or abstract_id_tag is None:
                continue
            abstract_id = abstract_id_tag.attrib.get(f'{{{NS["w"]}}}val')
            if abstract_id in abstract_nums:
                numbering_info[num_id] = abstract_nums[abstract_id]
        return numbering_info

    def _parse_paragraph_element(self, p: ET.Element, doc_index: int, numbering_info: Dict[str, Dict[str, Any]]):
        text = "".join(t.text for t in p.findall(".//w:t", NS) if t.text).strip()
        
        para_record = None
        if text:
            numId, ilvl, numFmt, list_type = None, None, None, None
            pPr = p.find("w:pPr", NS)
            if pPr is not None:
                numPr = pPr.find("w:numPr", NS)
                if numPr is not None:
                    numId_tag = numPr.find("w:numId", NS)
                    ilvl_tag = numPr.find("w:ilvl", NS)
                    if numId_tag is not None:
                        numId = numId_tag.attrib.get(f'{{{NS["w"]}}}val')
                    if ilvl_tag is not None:
                        ilvl = ilvl_tag.attrib.get(f'{{{NS["w"]}}}val')

                    if numId and ilvl and numId in numbering_info and ilvl in numbering_info[numId]:
                        fmt_info = numbering_info[numId][ilvl]
                        numFmt = fmt_info.get('numFmt')
                        list_type = fmt_info.get('list_type')
            
            para_record = ParagraphRecord(
                text=text,
                doc_index=doc_index,
                numId=numId,
                ilvl=ilvl,
                numFmt=numFmt,
                list_type=list_type
            )

        drawing_records = self._parse_drawings_in_paragraph(p, doc_index)
        
        return para_record, drawing_records

    def _parse_table_element(self, tbl: ET.Element, doc_index: int) -> Optional[TableRecord]:
        rows_data: List[List[TableCellRecord]] = []
        for tr in tbl.findall("./w:tr", NS):
            row_data: List[TableCellRecord] = []
            for tc in tr.findall("./w:tc", NS):
                tcPr = tc.find("w:tcPr", NS)
                gridSpan = 1
                vMerge = None
                if tcPr is not None:
                    gs = tcPr.find("w:gridSpan", NS)
                    if gs is not None:
                        try:
                            gridSpan = int(gs.attrib.get('{%s}val' % NS["w"], "1"))
                        except:
                            gridSpan = 1
                    vm = tcPr.find("w:vMerge", NS)
                    if vm is not None:
                        vMerge = vm.attrib.get('{%s}val' % NS["w"]) or "restart"
                texts = [t.text for t in tc.findall(".//w:t", NS) if t.text]
                row_data.append(TableCellRecord(
                    text="".join(texts).strip(),
                    gridSpan=gridSpan,
                    vMerge=vMerge
                ))
            rows_data.append(row_data)
        
        # t_idx를 어떻게 할지 고민 필요, 여기서는 doc_index를 사용
        return TableRecord(tid=f"t{doc_index}", rows=rows_data, doc_index=doc_index)

    def _parse_drawings_in_paragraph(self, p: ET.Element, doc_index: int) -> List[Dict[str, Any]]:
        drawings = []
        d_idx_in_p = 0
        
        # 이전에 _parse_drawings_raw_with_context에 있던 로직을 여기로 가져옴
        # 페이지/섹션 정보는 단락별로 처리되므로, 이 함수가 호출되는 시점의 컨텍스트를 알아야 함.
        # 지금은 단순화를 위해 페이지/섹션 정보를 제외하고 doc_index만 사용.
        
        def _texts(node):
            items = []
            for path in (".//a:t", ".//w:t", ".//wps:txBody//a:t", ".//a:txBody//a:t"):
                for t in node.findall(path, NS):
                    if t.text:
                        items.append({"text": t.text, "xpath": path})
            return items

        def _wrap(anchor):
            if anchor is None:
                return None
            for t in ("wrapNone","wrapSquare","wrapThrough","wrapTopAndBottom","wrapTight"):
                if anchor.find(f"./wp:{t}", NS) is not None:
                    return t
            return None

        for drawing in p.findall(".//w:drawing", NS):
            entry = {
                "did": f"d{doc_index}_{d_idx_in_p}",
                "kind": None,
                "texts_raw": _texts(drawing),
                "image": None,
                "shape": None,
                "group": None,
                "bbox": None,
                "page": None, # 페이지 정보는 별도 계산 필요
                "context": {
                    "p_idx": None, # p_idx는 전체 단락 기준이라 doc_index로 대체
                    "doc_index": doc_index,
                    "sect_idx": 0, # 섹션 정보는 별도 계산 필요
                    "in_header": False,
                    "in_footer": False
                },
                "xml_snippet": ET.tostring(drawing, encoding="unicode", method="xml")[:4000]
            }

            sp_root = (
                drawing.find(".//wps:wsp", NS) or
                drawing.find(".//wps:cxnSp", NS) or
                drawing.find(".//a:sp", NS) or
                drawing.find(".//a:cxnSp", NS)
            )
            if sp_root is not None:
                prst = None
                spPr = sp_root.find("./wps:spPr", NS) or sp_root.find("./a:spPr", NS) or sp_root.find(".//a:spPr", NS)
                if spPr is not None:
                    pg = spPr.find("./a:prstGeom", NS) or spPr.find(".//a:prstGeom", NS)
                    if pg is not None:
                        prst = pg.get("prst")
                entry["kind"] = "shape"
                entry["shape"] = {
                    "preset": prst,
                    "texts_raw": _texts(sp_root),
                    "tag": sp_root.tag
                }

            anchor = drawing.find(".//wp:anchor", NS)
            inline = drawing.find(".//wp:inline", NS)
            if anchor is not None:
                rel_h = anchor.find("./wp:positionH", NS)
                rel_v = anchor.find("./wp:positionV", NS)
                ph = anchor.find("./wp:positionH/wp:posOffset", NS)
                pv = anchor.find("./wp:positionV/wp:posOffset", NS)
                ext = anchor.find("./wp:extent", NS)
                entry["anchor"] = {
                    "type": "anchor",
                    "rel_from_h": rel_h.get("relativeFrom") if rel_h is not None else None,
                    "rel_from_v": rel_v.get("relativeFrom") if rel_v is not None else None,
                    "pos_offset": {"x": int(ph.text) if ph is not None else 0, "y": int(pv.text) if pv is not None else 0},
                    "extent": {"w": int(ext.get("cx")) if ext is not None else 0, "h": int(ext.get("cy")) if ext is not None else 0},
                    "wrap": _wrap(anchor),
                    "z": int(anchor.get("relativeHeight") or 0)
                }
            elif inline is not None:
                ext = inline.find("./wp:extent", NS)
                entry["anchor"] = {
                    "type": "inline",
                    "rel_from_h": None,
                    "rel_from_v": None,
                    "pos_offset": {"x": 0, "y": 0},
                    "extent": {"w": int(ext.get("cx")) if ext is not None else 0, "h": int(ext.get("cy")) if ext is not None else 0},
                    "wrap": None,
                    "z": 0
                }
            drawings.append(entry)
            d_idx_in_p += 1
        return drawings

