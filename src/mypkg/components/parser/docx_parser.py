# src/mypkg/components/parser/docx_parser.py
import time, logging
from pathlib import Path
from typing import Any, Dict, List, Union, BinaryIO
from docx import Document
from docx.text.paragraph import Paragraph
from mypkg.core.base_parser import BaseParser, ParseResult, ParagraphRecord, RunRecord, InlineImageRecord

log = logging.getLogger(__name__)

class DocxContentParser(BaseParser):
    def __init__(self):
        super().__init__()
        self.supported_formats = ['.docx']

    @property
    def provides(self) -> set:
        """python-docx에서 얻을 수 있는 것 -> 문단, 인라인 이미지"""
        return {'paragraphs_docx','inline_images'}

    def _runs(self, p: Paragraph) -> List[RunRecord]:
        out = []
        for r in p.runs:
            out.append(RunRecord(
                text=r.text or "",
                b=bool(r.bold),
                i=bool(r.italic),
                u=bool(r.underline),
                rStyle=r.style.name if r.style else None,
                sz=getattr(getattr(r.font, "size", None), "pt", None),
                color=getattr(getattr(r.font, "color", None), "rgb", None),
            ))
        return out

    async def parse(self, file_path: Union[str, Path, BinaryIO]) -> ParseResult:
        t0 = time.time()
        try:
            doc = Document(file_path)
            paragraphs: List[ParagraphRecord] = []
            inline_images: List[InlineImageRecord] = []

            # paragraphs
            for idx, p in enumerate(doc.paragraphs):
                if p.text.strip() or p.runs:
                    paragraphs.append(ParagraphRecord(
                        doc_index=idx,
                        style=p.style.name if p.style else "Normal",
                        text=p.text or "",
                        runs=self._runs(p),
                    ))

            # 인라인 이미지(간단 메타)
            try:
                part = doc.part
                if hasattr(part, "related_parts"):
                    for rid, rel in part.related_parts.items():
                        ct = getattr(rel, "content_type", "")
                        if ct.startswith("image/"):
                            inline_images.append(InlineImageRecord(
                                rId=rid,
                                content_type=ct,
                                filename=getattr(getattr(rel, "partname", None), "basename", None)
                            ))
            except Exception:
                pass
            
            payload = {
                "paragraphs_docx": paragraphs,
                "inline_images": inline_images
            }

            return ParseResult(True, {"docx_content": payload}, processing_time=time.time()-t0, payload_tag="docx_python")
        except Exception as e:
            log.exception("docx parser failed")
            return ParseResult(False, error=str(e), processing_time=time.time()-t0, payload_tag="docx_python")
