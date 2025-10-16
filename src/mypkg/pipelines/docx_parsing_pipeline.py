1# src/mypkg/pipelines/docx_parsing_pipeline.py

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Any

# Parsers
from mypkg.components.parser.docx_parser import DocxContentParser
from mypkg.components.parser.xml_parser import DocxXmlParser

# Sanitizers
from mypkg.components.sanitizer.paragraph_sanitizer import ParagraphSanitizer
from mypkg.components.sanitizer.table_sanitizer import TableSanitizer
from mypkg.components.sanitizer.diagram_sanitizer import DiagramSanitizer

# Core
from mypkg.core.io import write_json_output

class DocxParsingPipeline:
    """
    A pipeline that takes a DOCX file, runs it through parsers and sanitizers,
    and saves the intermediate and final outputs to a specified directory.
    """

    def __init__(self):
        self.docx_parser = DocxContentParser()
        self.xml_parser = DocxXmlParser()
        self.para_sanitizer = ParagraphSanitizer()
        self.diag_sanitizer = DiagramSanitizer()
        self.table_sanitizer = TableSanitizer()

    async def run(self, file_path: Path, output_base_dir: Path) -> Dict[str, str]:
        """
        Executes the parsing and sanitizing pipeline and saves the outputs.
        Returns a dictionary of the paths to the saved files.
        """
        doc_name = file_path.stem
        # 새 디렉터리 규칙: base_dir/_sanitized
        output_dir = output_base_dir / "_sanitized"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Parsing stage
        res_docx, res_xml = await asyncio.gather(
            self.docx_parser.parse(file_path),
            self.xml_parser.parse(file_path)
        )
        if not res_docx.success or not res_xml.success:
            errors = f"DocxContentParser: {res_docx.error}, DocxXmlParser: {res_xml.error}"
            raise RuntimeError(f"Parsing failed for {file_path}. Errors: {errors}")

        # Save raw parser outputs
        docx_output_path = output_dir / f"{doc_name}_output_docx.json"
        xml_output_path = output_dir / f"{doc_name}_output_xml.json"
        write_json_output(asdict(res_docx), docx_output_path)
        write_json_output(asdict(res_xml), xml_output_path)

        # Extract content for sanitizers
        docx_content_data = res_docx.content.get("docx_content", {})
        xml_content_data = res_xml.content.get("docx_xml", {})
        paragraphs_for_context = xml_content_data.get("paragraphs_xml", [])

        # 2. Sanitizing stage
        sanitized_paragraphs = self.para_sanitizer.apply(
            docx_content_data.get("paragraphs_docx", []),
            paragraphs_for_context
        )
        sanitized_drawings = self.diag_sanitizer.apply(xml_content_data.get("drawings_raw", []), paragraphs_for_context)
        sanitized_tables = self.table_sanitizer.apply(xml_content_data.get("tables", []), paragraphs_for_context)

        # 3. Assembling and saving sanitized result
        final_result = {
            "paragraphs": [asdict(p) for p in sanitized_paragraphs],
            "drawings": [asdict(d) for d in sanitized_drawings],
            "tables": sanitized_tables,
            "headers": [asdict(h) for h in xml_content_data.get("headers", [])],
            "footers": [asdict(f) for f in xml_content_data.get("footers", [])],
            "relationships": {"map": {k: asdict(v) for k, v in xml_content_data.get("relationships", {}).get("map", {}).items()}},
            "inline_images": [asdict(i) for i in docx_content_data.get("inline_images", [])],
        }
        
        sanitized_output_path = output_dir / f"{doc_name}_sanitized.json"
        write_json_output(final_result, sanitized_output_path)

        return {
            "docx_parser_output": str(docx_output_path),
            "xml_parser_output": str(xml_output_path),
            "sanitized_output": str(sanitized_output_path),
        }
