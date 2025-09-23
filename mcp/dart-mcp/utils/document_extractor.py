"""
문서 추출기
DART 공시 문서에서 정보를 추출 (PDF, XML, HTML)
"""

import os
import re
import json
import asyncio
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET

from utils.logging import get_logger

logger = get_logger("document_extractor")

# PDF 파싱 라이브러리 (선택적)
try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logger.warning("pdfplumber not installed, PDF extraction disabled")

# HTML 파싱
try:
    from bs4 import BeautifulSoup
    HTML_SUPPORT = True
except ImportError:
    HTML_SUPPORT = False
    logger.warning("BeautifulSoup not installed, HTML parsing limited")


class DocumentExtractor:
    """DART 문서 정보 추출기"""
    
    def __init__(self, download_dir: str = "./downloads/dart"):
        """
        Args:
            download_dir: 다운로드 디렉토리
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
    async def extract_from_document(
        self,
        file_path: Union[str, Path],
        doc_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        문서에서 정보 추출
        
        Args:
            file_path: 문서 파일 경로
            doc_type: 문서 유형 (pdf, xml, html)
            
        Returns:
            추출된 정보
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return {"error": "파일을 찾을 수 없습니다"}
        
        # 파일 타입 자동 감지
        if doc_type is None:
            doc_type = file_path.suffix.lower().lstrip('.')
        
        logger.info(f"Extracting from {doc_type}: {file_path.name}")
        
        try:
            if doc_type == 'pdf':
                return await self._extract_from_pdf(file_path)
            elif doc_type in ['xml', 'xbrl']:
                return await self._extract_from_xml(file_path)
            elif doc_type in ['html', 'htm']:
                return await self._extract_from_html(file_path)
            else:
                return await self._extract_from_text(file_path)
                
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {"error": str(e)}
    
    async def _extract_from_pdf(self, file_path: Path) -> Dict[str, Any]:
        """PDF 문서에서 정보 추출"""
        if not PDF_SUPPORT:
            return {"error": "PDF 지원이 설치되지 않았습니다"}
        
        extracted_data = {
            "type": "pdf",
            "file": file_path.name,
            "pages": [],
            "tables": [],
            "text": "",
            "metadata": {}
        }
        
        try:
            with pdfplumber.open(file_path) as pdf:
                # 메타데이터
                extracted_data["metadata"] = pdf.metadata or {}
                extracted_data["page_count"] = len(pdf.pages)
                
                all_text = []
                
                for i, page in enumerate(pdf.pages[:10]):  # 최대 10페이지
                    page_data = {
                        "page_num": i + 1,
                        "text": page.extract_text() or "",
                        "tables": []
                    }
                    
                    # 텍스트 추출
                    if page_data["text"]:
                        all_text.append(page_data["text"])
                    
                    # 테이블 추출
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            if table and len(table) > 1:  # 유효한 테이블
                                page_data["tables"].append(self._process_table(table))
                                extracted_data["tables"].append({
                                    "page": i + 1,
                                    "data": table[:5]  # 첫 5행만
                                })
                    
                    extracted_data["pages"].append(page_data)
                
                extracted_data["text"] = "\n\n".join(all_text)
                
                # 핵심 정보 추출
                extracted_data["key_info"] = self._extract_key_info_from_text(
                    extracted_data["text"]
                )
                
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            extracted_data["error"] = str(e)
        
        return extracted_data
    
    async def _extract_from_xml(self, file_path: Path) -> Dict[str, Any]:
        """XML/XBRL 문서에서 정보 추출"""
        extracted_data = {
            "type": "xml",
            "file": file_path.name,
            "elements": {},
            "namespaces": {},
            "financial_data": {}
        }
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # 네임스페이스 추출
            namespaces = dict([
                node for _, node in ET.iterparse(file_path, events=['start-ns'])
            ])
            extracted_data["namespaces"] = namespaces
            
            # XBRL 재무 데이터 추출
            if 'xbrli' in str(root.tag).lower() or 'xbrl' in str(root.tag).lower():
                extracted_data["financial_data"] = self._extract_xbrl_data(root, namespaces)
            
            # 일반 XML 데이터 추출
            extracted_data["elements"] = self._xml_to_dict(root)
            
            # 텍스트 내용 추출
            all_text = []
            for elem in root.iter():
                if elem.text and elem.text.strip():
                    all_text.append(elem.text.strip())
            
            extracted_data["text"] = " ".join(all_text[:1000])  # 첫 1000개 텍스트
            
        except Exception as e:
            logger.error(f"XML extraction error: {e}")
            extracted_data["error"] = str(e)
        
        return extracted_data
    
    async def _extract_from_html(self, file_path: Path) -> Dict[str, Any]:
        """HTML 문서에서 정보 추출"""
        extracted_data = {
            "type": "html",
            "file": file_path.name,
            "title": "",
            "tables": [],
            "text": "",
            "links": []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if HTML_SUPPORT:
                soup = BeautifulSoup(content, 'html.parser')
                
                # 제목 추출
                title = soup.find('title')
                if title:
                    extracted_data["title"] = title.get_text(strip=True)
                
                # 테이블 추출
                tables = soup.find_all('table')
                for table in tables[:5]:  # 최대 5개 테이블
                    table_data = self._extract_html_table(table)
                    if table_data:
                        extracted_data["tables"].append(table_data)
                
                # 텍스트 추출
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text()
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                extracted_data["text"] = "\n".join(lines[:500])  # 첫 500줄
                
                # 링크 추출
                links = soup.find_all('a', href=True)
                extracted_data["links"] = [
                    {"text": link.get_text(strip=True), "href": link['href']}
                    for link in links[:20]  # 최대 20개
                ]
            else:
                # BeautifulSoup 없이 기본 추출
                extracted_data["text"] = self._extract_text_from_html_regex(content)
            
            # 핵심 정보 추출
            extracted_data["key_info"] = self._extract_key_info_from_text(
                extracted_data["text"]
            )
            
        except Exception as e:
            logger.error(f"HTML extraction error: {e}")
            extracted_data["error"] = str(e)
        
        return extracted_data
    
    async def _extract_from_text(self, file_path: Path) -> Dict[str, Any]:
        """텍스트 파일에서 정보 추출"""
        extracted_data = {
            "type": "text",
            "file": file_path.name,
            "text": "",
            "key_info": {}
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            extracted_data["text"] = text[:10000]  # 최대 10000자
            extracted_data["key_info"] = self._extract_key_info_from_text(text)
            
        except Exception as e:
            logger.error(f"Text extraction error: {e}")
            extracted_data["error"] = str(e)
        
        return extracted_data
    
    def _extract_key_info_from_text(self, text: str) -> Dict[str, Any]:
        """텍스트에서 핵심 정보 추출"""
        key_info = {
            "amounts": [],
            "dates": [],
            "percentages": [],
            "company_names": [],
            "keywords": []
        }
        
        # 금액 추출 (억원, 백만원 등)
        amount_pattern = r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:억원|백만원|천만원|만원|원|달러|USD)'
        amounts = re.findall(amount_pattern, text)
        key_info["amounts"] = list(set(amounts[:10]))
        
        # 날짜 추출
        date_pattern = r'\d{4}[-년.]\s*\d{1,2}[-월.]\s*\d{1,2}일?'
        dates = re.findall(date_pattern, text)
        key_info["dates"] = list(set(dates[:10]))
        
        # 퍼센트 추출
        percent_pattern = r'(\d+(?:\.\d+)?)\s*[%％]'
        percentages = re.findall(percent_pattern, text)
        key_info["percentages"] = list(set(percentages[:10]))
        
        # 주요 키워드
        keywords = [
            "유상증자", "무상증자", "자사주", "자기주식", "합병", "분할",
            "매출", "영업이익", "당기순이익", "배당", "감자", "상장",
            "계약", "투자", "인수", "매각", "청산", "파산"
        ]
        found_keywords = [kw for kw in keywords if kw in text]
        key_info["keywords"] = found_keywords
        
        return key_info
    
    def _process_table(self, table: List[List]) -> Dict[str, Any]:
        """테이블 데이터 처리"""
        if not table:
            return {}
        
        processed = {
            "headers": [],
            "rows": [],
            "row_count": len(table),
            "col_count": len(table[0]) if table else 0
        }
        
        # 첫 행을 헤더로 가정
        if len(table) > 0:
            processed["headers"] = [str(cell) if cell else "" for cell in table[0]]
        
        # 데이터 행 (최대 10행)
        if len(table) > 1:
            processed["rows"] = [
                [str(cell) if cell else "" for cell in row]
                for row in table[1:11]
            ]
        
        return processed
    
    def _extract_xbrl_data(self, root: ET.Element, namespaces: Dict) -> Dict[str, Any]:
        """XBRL 재무 데이터 추출"""
        financial_data = {
            "contexts": {},
            "units": {},
            "facts": []
        }
        
        try:
            # Context 정보 추출
            for context in root.findall('.//xbrli:context', namespaces):
                context_id = context.get('id')
                period = context.find('.//xbrli:period', namespaces)
                if period is not None:
                    instant = period.find('xbrli:instant', namespaces)
                    if instant is not None:
                        financial_data["contexts"][context_id] = instant.text
            
            # 재무 수치 추출
            for elem in root.iter():
                if '}' in elem.tag:
                    tag_name = elem.tag.split('}')[1]
                    if elem.text and elem.text.strip():
                        fact = {
                            "name": tag_name,
                            "value": elem.text.strip(),
                            "context": elem.get('contextRef'),
                            "unit": elem.get('unitRef'),
                            "decimals": elem.get('decimals')
                        }
                        financial_data["facts"].append(fact)
                        
                        if len(financial_data["facts"]) >= 100:  # 최대 100개
                            break
            
        except Exception as e:
            logger.error(f"XBRL extraction error: {e}")
        
        return financial_data
    
    def _xml_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """XML 요소를 딕셔너리로 변환"""
        result = {}
        
        # 속성 추가
        if element.attrib:
            result["@attributes"] = element.attrib
        
        # 텍스트 내용
        if element.text and element.text.strip():
            result["text"] = element.text.strip()
        
        # 자식 요소
        children = {}
        for child in element:
            child_data = self._xml_to_dict(child)
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            
            if tag in children:
                if not isinstance(children[tag], list):
                    children[tag] = [children[tag]]
                children[tag].append(child_data)
            else:
                children[tag] = child_data
        
        if children:
            result.update(children)
        
        return result if result else None
    
    def _extract_html_table(self, table) -> Optional[Dict[str, Any]]:
        """HTML 테이블 추출"""
        try:
            headers = []
            rows = []
            
            # 헤더 추출
            header_row = table.find('thead')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            elif table.find('tr'):
                first_row = table.find('tr')
                headers = [cell.get_text(strip=True) for cell in first_row.find_all(['th', 'td'])]
            
            # 데이터 행 추출
            tbody = table.find('tbody') or table
            for tr in tbody.find_all('tr')[1:11]:  # 최대 10행
                row = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if row:
                    rows.append(row)
            
            if headers or rows:
                return {
                    "headers": headers,
                    "rows": rows,
                    "row_count": len(rows),
                    "col_count": len(headers) if headers else (len(rows[0]) if rows else 0)
                }
                
        except Exception as e:
            logger.error(f"HTML table extraction error: {e}")
        
        return None
    
    def _extract_text_from_html_regex(self, html: str) -> str:
        """정규식으로 HTML에서 텍스트 추출"""
        # HTML 태그 제거
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()[:5000]  # 최대 5000자


async def extract_dart_document(
    file_path: str,
    doc_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    DART 문서 추출 (외부 호출용)
    
    Args:
        file_path: 문서 파일 경로
        doc_type: 문서 유형
        
    Returns:
        추출된 정보
    """
    extractor = DocumentExtractor()
    return await extractor.extract_from_document(file_path, doc_type)