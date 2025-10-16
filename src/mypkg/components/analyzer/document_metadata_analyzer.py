
"""
문서 메타데이터 분석기
sanitizer.json의 내용을 기반으로 DocumentMetadata를 채웁니다.
"""

import re
import logging
from typing import Dict, Any, Optional
from mypkg.core.docjson_types import DocumentMetadata

logger = logging.getLogger(__name__)
class DocumentMetadataAnalyzer:
    """문서 메타데이터 분석기"""

    def __init__(self, docjson: Dict[str, Any]):
        """
        Args:
            docjson (Dict[str, Any]): sanitizer.json을 로드한 딕셔너리
        """
        self.docjson = docjson
        self.all_text = self._collect_all_text()
        
    def _normalize_spaces(self, s: Optional[str]) -> Optional[str]:
        """연속된 공백(2개 이상)을 한 칸으로 축약하고 앞뒤 공백을 제거."""
        if s is None:
            return None
        try:
            # 두 칸 이상의 스페이스를 한 칸으로 축약
            s2 = re.sub(r" {2,}", " ", s)
            # 탭 등 혼합 공백이 들어온 경우를 위해 한 번 더 정규화(선택)
            s2 = re.sub(r"\s{2,}", " ", s2)
            return s2.strip()
        except Exception:
            return s.strip() if isinstance(s, str) else s


    def analyze(self) -> DocumentMetadata:
        """메타데이터 분석을 수행하고 DocumentMetadata 객체를 반환합니다."""
        doc_number = self._find_doc_number()
        revision = self._find_revision()
        effective_date = self._find_effective_date()
        author = self._find_author()
        document_type = self._extract_document_type_from_header()
        if not document_type:
            document_type = self._extract_document_type_from_table()

        category = self._extract_category_from_header()
        if not category:
            category = self._extract_category_from_table()

        title = self._extract_title_from_header() # Use the new header-based title extraction
        if not title:
            title = self._extract_title_from_table()
        
        # page_count는 docjson에 있으면 가져오고, 없으면 None
        page_count = self.docjson.get("page_count")

        # 후처리: 두 칸 이상의 공백을 한 칸으로 축약
        document_type = self._normalize_spaces(document_type)
        category = self._normalize_spaces(category)
        title = self._normalize_spaces(title)
        doc_number = self._normalize_spaces(doc_number)
        revision = self._normalize_spaces(revision)
        effective_date = self._normalize_spaces(effective_date)
        author = self._normalize_spaces(author)

        return DocumentMetadata(
            document_type=document_type,
            category=category,
            title=title,
            doc_number=doc_number,
            revision=revision,
            effective_date=effective_date,
            author=author,
            page_count=page_count,
        )

    def _collect_all_text(self) -> str:
        """docjson에서 모든 텍스트를 수집합니다."""
        texts = []
        
        headers_footers = self.docjson.get('headers_footers', {})
        if headers_footers:
            for header in headers_footers.get('headers', []):
                if isinstance(header, dict) and 'text' in header:
                    texts.append(header['text'])
            for footer in headers_footers.get('footers', []):
                if isinstance(footer, dict) and 'text' in footer:
                    texts.append(footer['text'])

        for para in self.docjson.get('paragraphs', []):
            if isinstance(para, dict):
                texts.append(para.get('text', ''))
            else:
                texts.append(str(para))

        for table in self.docjson.get('tables', []):
            if isinstance(table, dict):
                rows = table.get('rows', [])
                if isinstance(rows, list):
                    for row in rows:
                        if isinstance(row, list):
                            texts.extend(str(cell) for cell in row)
        
        return '\n'.join(texts)

    def _find_doc_number(self) -> Optional[str]:
        """문서번호를 찾습니다."""
        doc_num_pattern = re.compile(r'TP-\d{3}-\d{3}-\d{3}')

        # 1. Search in headers and footers
        for hf_section in ('headers', 'footers'):
            for item in self.docjson.get(hf_section, []):
                if text := item.get('text'):
                    if match := doc_num_pattern.search(text):
                        logger.info(f"문서번호 감지 (from {hf_section}): {match.group()}")
                        return match.group()

        # 2. If not found, search in tables
        for table in self.docjson.get('tables', []):
            for row in table.get('data', []):
                for cell in row:
                    if match := doc_num_pattern.search(str(cell)):
                        logger.info(f"문서번호 감지 (from table): {match.group()}")
                        return match.group()

        # 3. As a fallback, search the whole text
        if match := doc_num_pattern.search(self.all_text):
            logger.info(f"문서번호 감지 (from all_text): {match.group()}")
            return match.group()

        return None

    def _find_revision(self) -> Optional[str]:
        """개정번호를 찾습니다."""
        rev_pattern = re.compile(r'Rev[\.\s]*:\s*(\d+)')

        # 1. Search in headers and footers
        for hf_section in ('headers', 'footers'):
            for item in self.docjson.get(hf_section, []):
                if text := item.get('text'):
                    if match := rev_pattern.search(text):
                        logger.info(f"개정번호 감지 (from {hf_section}): Rev.{match.group(1)}")
                        return match.group(1)

        # 2. If not found, search in tables
        for table in self.docjson.get('tables', []):
            for row in table.get('data', []):
                for cell in row:
                    if match := rev_pattern.search(str(cell)):
                        logger.info(f"개정번호 감지 (from table): Rev.{match.group(1)}")
                        return match.group(1)

        # 3. As a fallback, search the whole text
        if match := rev_pattern.search(self.all_text):
            logger.info(f"개정번호 감지 (from all_text): Rev.{match.group(1)}")
            return match.group(1)

        return None

    def _find_effective_date(self) -> Optional[str]:
        """시행일을 찾습니다."""
        date_pattern_1 = re.compile(r"시행일[:\s]*['\"]?\s*(\d{2,4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
        date_pattern_2 = re.compile(r"시행일.*?['\"]?\s*(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})", re.DOTALL)

        # 1. Search in headers and footers
        for hf_section in ('headers', 'footers'):
            for item in self.docjson.get(hf_section, []):
                if text := item.get('text'):
                    if match := date_pattern_1.search(text):
                        date_str = f"{match.group(1)}.{match.group(2).zfill(2)}.{match.group(3).zfill(2)}"
                        logger.info(f"시행일 감지 (from {hf_section}, 패턴1): {date_str}")
                        return date_str
                    elif match := date_pattern_2.search(text):
                        date_str = f"{match.group(1)}.{match.group(2).zfill(2)}.{match.group(3).zfill(2)}"
                        logger.info(f"시행일 감지 (from {hf_section}, 패턴2): {date_str}")
                        return date_str

        # 2. If not found, search in tables
        for table in self.docjson.get('tables', []):
            for row in table.get('data', []):
                for cell in row:
                    cell_text = str(cell)
                    if '시행일' in cell_text:
                        if match := date_pattern_1.search(cell_text):
                            date_str = f"{match.group(1)}.{match.group(2).zfill(2)}.{match.group(3).zfill(2)}"
                            logger.info(f"시행일 감지 (from table, 패턴1): {date_str}")
                            return date_str
                        elif match := date_pattern_2.search(cell_text):
                            date_str = f"{match.group(1)}.{match.group(2).zfill(2)}.{match.group(3).zfill(2)}"
                            logger.info(f"시행일 감지 (from table, 패턴2): {date_str}")
                            return date_str

        # 3. As a fallback, search the whole text
        if '시행일' in self.all_text:
            if match := date_pattern_1.search(self.all_text):
                date_str = f"{match.group(1)}.{match.group(2).zfill(2)}.{match.group(3).zfill(2)}"
                logger.info(f"시행일 감지 (from all_text, 패턴1): {date_str}")
                return date_str
            elif match := date_pattern_2.search(self.all_text):
                date_str = f"{match.group(1)}.{match.group(2).zfill(2)}.{match.group(3).zfill(2)}"
                logger.info(f"시행일 감지 (from all_text, 패턴2): {date_str}")
                return date_str

        return None

    def _find_author(self) -> Optional[str]:
        """작성자를 찾습니다."""
        # Primarily search in tables as it's the most likely location
        for table in self.docjson.get('tables', []):
            for row in table.get('data', []):
                for i, cell_text in enumerate(row):
                    if '작성자' in str(cell_text):
                        if i + 1 < len(row):
                            author = str(row[i+1]).strip()
                            if author:
                                logger.info(f"작성자 감지 (from table): {author}")
                                return author
        
        # Fallback to searching the whole text
        # This part is less reliable and kept as a last resort
        xml_struct = self.docjson.get('xml_structure', {})
        if xml_struct:
            for table in xml_struct.get('tables', []):
                if isinstance(table, dict):
                    rows = table.get('rows', [])
                    if isinstance(rows, list) and rows:
                        first_row = rows[0]
                        if isinstance(first_row, list) and len(first_row) >= 2:
                            if '작성자' in str(first_row[0]):
                                author = str(first_row[1]).strip()
                                if author:
                                    logger.info(f"XML 테이블에서 작성자 감지: {author}")
                                    return author
        return None

    def _extract_document_type_from_header(self) -> Optional[str]:
        """
        헤더 텍스트에서 문서 유형을 추출합니다.
        예: "기술기준 포항제철소 제선부 > 고로공정 노황변동시 조치기준 (XX-YY-ZZZ) Rev. 0 Page: 1 / 5"
        에서 "기술기준 포항제철소"를 추출합니다.
        """
        for item in self.docjson.get('headers', []): # Directly access 'headers'
            if text := item.get('text'):
                match = re.search(r'(기술기준\s+[^ ]+)', text)
                if match:
                    logger.info(f"문서 유형 감지 (from header): {match.group(1)}")
                    return match.group(1).strip()
        return None

    def _extract_category_from_header(self) -> Optional[str]:
        """
        헤더 텍스트에서 카테고리를 추출합니다.
        예: "기술기준 포항제철소 제선부 > 고로공정 노황변동시 조치기준 (XX-YY-ZZZ) Rev. 0 Page: 1 / 5"
        에서 "제선부 > 고로공정"을 추출합니다.
        "포항제철소" 뒤부터 두 개의 영어 레터(XX) 앞까지를 찾습니다.
        """
        for item in self.docjson.get('headers', []): # Directly access 'headers'
            if text := item.get('text'):
                # "포항제철소" 뒤부터 두 개의 영어 레터(XX) 앞까지를 찾습니다.
                match = re.search(r'포항제철소\s*(.*?)\s*[A-Z]{2}', text)
                if match:
                    category = match.group(1).strip()
                    # "기술기준" 또는 "포항제철소"가 포함되어 있으면 제거
                    category = re.sub(r'기술기준\s*', '', category)
                    category = re.sub(r'포항제철소\s*', '', category)
                    logger.info(f"카테고리 감지 (from header): {category}")
                    return category
        return None

    def _extract_title_from_header(self) -> Optional[str]:
        """
        헤더 텍스트에서 문서 제목을 추출합니다.
        예: "기술기준 포항제철소 제선부 > 고로공정 노황변동시 조치기준 (XX-YY-ZZZ) Rev. 0 Page: 1 / 5"
        에서 "노황변동시 조치기준"을 추출합니다.
        "Page: X / Y"와 같은 형식 뒤부터 "Rev." 앞까지를 찾습니다.
        """
        for item in self.docjson.get('headers', []): # Directly access 'headers'
            if text := item.get('text'):
                # "Page: X / Y" 뒤부터 "Rev." 앞까지를 찾습니다.
                match = re.search(r'Page:\s*\d+\s*/\s*\d+\s*(.*?)\s*Rev\.', text)
                if match:
                    title = match.group(1).strip()
                    logger.info(f"문서 제목 감지 (from header): {title}")
                    return title
        return None

    def _extract_document_type_from_table(self) -> Optional[str]:
        """
        테이블에서 문서 유형을 추출합니다.
        첫 번째 테이블의 첫 번째 행에서 "기술기준포항제철소"와 같은 패턴을 찾습니다.
        """
        if tables := self.docjson.get('tables'):
            if tables and tables[0].get('data'):
                first_table_data = tables[0]['data']
                for row in first_table_data:
                    for cell_text in row:
                        if "기술기준포항제철소" in str(cell_text):
                            logger.info(f"문서 유형 감지 (from table): {cell_text.strip()}")
                            return str(cell_text).strip()
        return None

    def _extract_category_from_table(self) -> Optional[str]:
        """
        테이블에서 카테고리를 추출합니다.
        첫 번째 테이블의 첫 번째 행에서 "제선부 > 고로공정"과 같은 패턴을 찾습니다.
        """
        if tables := self.docjson.get('tables'):
            if tables and tables[0].get('data'):
                first_table_data = tables[0]['data']
                for row in first_table_data:
                    for cell_text in row:
                        if "제선부 > 고로공정" in str(cell_text):
                            logger.info(f"카테고리 감지 (from table): {cell_text.strip()}")
                            return str(cell_text).strip()
        return None

    def _extract_title_from_table(self) -> Optional[str]:
        """
        테이블에서 문서 제목을 추출합니다.
        첫 번째 테이블의 두 번째 행에서 "Rev." 셀 옆 셀에서 제목을 찾습니다.
        """
        if tables := self.docjson.get('tables'):
            if tables and tables[0].get('data'):
                first_table_data = tables[0]['data']
                if len(first_table_data) > 1: # Check if there's a second row
                    second_row = first_table_data[1]
                    for i, cell_text in enumerate(second_row):
                        if "Rev." in str(cell_text):
                            # Assuming title is in the cell before "Rev." or a specific column
                            # Based on the example, it's in the second column of the second row
                            if i > 0: # Ensure there's a cell before "Rev."
                                title_cell = second_row[i-1] # Assuming title is in the cell before "Rev."
                                logger.info(f"문서 제목 감지 (from table): {title_cell.strip()}")
                                return str(title_cell).strip()
                            elif len(second_row) > 1: # If "Rev." is in the first cell, try the second cell
                                title_cell = second_row[1]
                                logger.info(f"문서 제목 감지 (from table): {title_cell.strip()}")
                                return str(title_cell).strip()
        return None






