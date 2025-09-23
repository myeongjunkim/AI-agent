"""
DART 원본 문서 다운로더
공시서류 원본파일 API를 통해 실제 문서를 다운로드하고 텍스트 추출
"""

import os
import zipfile
import asyncio
import httpx
from pathlib import Path
from typing import Optional, Dict, Any
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import json

from utils.logging import get_logger

logger = get_logger("document_downloader")


class DartDocumentDownloader:
    """DART 원본 문서 다운로드 및 텍스트 추출"""
    
    def __init__(self, api_key: str, download_dir: str = "./downloads/dart"):
        """
        Args:
            api_key: DART API 키
            download_dir: 다운로드 디렉토리
        """
        self.api_key = api_key
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # DART 원본파일 다운로드 API
        self.document_url = "https://opendart.fss.or.kr/api/document.xml"
        
    async def download_document(self, rcept_no: str) -> Dict[str, Any]:
        """
        원본 문서 다운로드 및 텍스트 추출
        
        Args:
            rcept_no: 접수번호
            
        Returns:
            문서 내용 딕셔너리
        """
        try:
            logger.info(f"Downloading original document for {rcept_no}")
            
            # 다운로드 경로 설정
            zip_path = self.download_dir / f"{rcept_no}.zip"
            extract_dir = self.download_dir / rcept_no
            
            # 이미 다운로드된 경우 캐시 사용
            if extract_dir.exists():
                logger.info(f"Using cached document: {extract_dir}")
                return await self._extract_text_from_files(extract_dir)
            
            # API 파라미터
            params = {
                "crtfc_key": self.api_key,
                "rcept_no": rcept_no
            }
            
            # 파일 다운로드
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    self.document_url,
                    params=params,
                    follow_redirects=True
                )
                
                if response.status_code != 200:
                    logger.error(f"Download failed: {response.status_code}")
                    return {
                        "error": f"Download failed: {response.status_code}",
                        "rcept_no": rcept_no
                    }
                
                # Content-Type 확인
                content_type = response.headers.get("content-type", "")
                
                # 에러 응답 확인 (XML 형식의 에러)
                if "xml" in content_type or "text" in content_type:
                    content = response.text
                    if "err_code" in content or "err_msg" in content:
                        logger.error(f"API error: {content}")
                        return {
                            "error": f"API error: {content}",
                            "rcept_no": rcept_no
                        }
                
                # ZIP 파일 저장
                with open(zip_path, "wb") as f:
                    f.write(response.content)
                
                logger.info(f"Downloaded {len(response.content)} bytes to {zip_path}")
            
            # ZIP 파일 압축 해제
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                logger.info(f"Extracted to {extract_dir}")
            except zipfile.BadZipFile:
                logger.error(f"Invalid ZIP file: {zip_path}")
                return {
                    "error": "Invalid ZIP file",
                    "rcept_no": rcept_no
                }
            
            # 텍스트 추출
            result = await self._extract_text_from_files(extract_dir)
            
            # ZIP 파일 삭제 (공간 절약)
            if zip_path.exists():
                zip_path.unlink()
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to download document {rcept_no}: {e}")
            return {
                "error": str(e),
                "rcept_no": rcept_no
            }
    
    async def _extract_text_from_files(self, extract_dir: Path) -> Dict[str, Any]:
        """
        압축 해제된 파일들에서 텍스트 추출
        
        Args:
            extract_dir: 압축 해제 디렉토리
            
        Returns:
            추출된 텍스트 정보
        """
        result = {
            "rcept_no": extract_dir.name,
            "files": [],
            "content": "",
            "main_text": "",
            "tables": []
        }
        
        all_text = []
        
        # 디렉토리 내 파일 탐색
        for file_path in extract_dir.glob("**/*"):
            if file_path.is_file():
                file_info = {
                    "name": file_path.name,
                    "path": str(file_path.relative_to(extract_dir)),
                    "size": file_path.stat().st_size
                }
                result["files"].append(file_info)
                
                # XML 파일 처리
                if file_path.suffix.lower() == '.xml':
                    text = self._extract_text_from_xml(file_path)
                    if text:
                        all_text.append(f"=== {file_path.name} ===\n{text}")
                        
                        # 메인 문서 확인
                        if any(keyword in file_path.name.lower() for keyword in ['main', 'body', '본문']):
                            result["main_text"] = text[:10000]
                
                # HTML 파일 처리
                elif file_path.suffix.lower() in ['.html', '.htm']:
                    text = self._extract_text_from_html(file_path)
                    if text:
                        all_text.append(f"=== {file_path.name} ===\n{text}")
                        
                        if not result["main_text"]:
                            result["main_text"] = text[:10000]
        
        # 전체 텍스트 결합 (최대 20000자)
        result["content"] = "\n\n".join(all_text)[:20000]
        
        # 메인 텍스트가 없으면 전체 내용 일부 사용
        if not result["main_text"] and result["content"]:
            result["main_text"] = result["content"][:10000]
        
        logger.info(f"Extracted {len(result['content'])} characters from {len(result['files'])} files")
        
        return result
    
    def _extract_text_from_xml(self, file_path: Path) -> str:
        """XML 파일에서 텍스트 추출"""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # 모든 텍스트 노드 수집
            texts = []
            for elem in root.iter():
                if elem.text and elem.text.strip():
                    # 태그명과 함께 저장 (중요 정보 식별용)
                    tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                    texts.append(f"[{tag_name}]: {elem.text.strip()}")
            
            return "\n".join(texts[:500])  # 최대 500개 요소
            
        except Exception as e:
            logger.error(f"Failed to parse XML {file_path}: {e}")
            return ""
    
    def _extract_text_from_html(self, file_path: Path) -> str:
        """HTML 파일에서 텍스트 추출"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # 스크립트와 스타일 제거
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 테이블 추출 (중요 정보)
            tables = soup.find_all('table')
            table_texts = []
            for table in tables[:5]:  # 최대 5개 테이블
                table_text = self._extract_table_text(table)
                if table_text:
                    table_texts.append(table_text)
            
            # 본문 텍스트 추출
            text = soup.get_text()
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            main_text = "\n".join(lines[:500])  # 최대 500줄
            
            # 테이블과 본문 결합
            if table_texts:
                return "=== 테이블 ===\n" + "\n".join(table_texts) + "\n\n=== 본문 ===\n" + main_text
            else:
                return main_text
                
        except Exception as e:
            logger.error(f"Failed to parse HTML {file_path}: {e}")
            return ""
    
    def _extract_table_text(self, table) -> str:
        """HTML 테이블에서 텍스트 추출"""
        try:
            rows = []
            for tr in table.find_all('tr')[:20]:  # 최대 20행
                cells = []
                for td in tr.find_all(['td', 'th'])[:10]:  # 최대 10열
                    cells.append(td.get_text(strip=True))
                if cells:
                    rows.append(" | ".join(cells))
            
            return "\n".join(rows) if rows else ""
            
        except Exception as e:
            logger.error(f"Failed to extract table: {e}")
            return ""


async def download_dart_document(rcept_no: str, api_key: str = None) -> Dict[str, Any]:
    """
    DART 원본 문서 다운로드 (외부 호출용)
    
    Args:
        rcept_no: 접수번호
        api_key: DART API 키
        
    Returns:
        문서 내용 딕셔너리
    """
    if not api_key:
        # 환경변수에서 가져오기
        import os
        api_key = os.getenv("DART_API_KEY")
        
    if not api_key:
        return {"error": "DART API key not provided"}
    
    downloader = DartDocumentDownloader(api_key)
    return await downloader.download_document(rcept_no)