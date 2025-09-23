"""
Content Cleaner
XML/HTML 태그를 제거하고 텍스트를 정리하는 유틸리티
"""

import re
from typing import Optional
from bs4 import BeautifulSoup
import html

from utils.logging import get_logger

logger = get_logger("content_cleaner")


class ContentCleaner:
    """문서 내용 정리 유틸리티"""
    
    @staticmethod
    def clean_content(content: Optional[str], preserve_structure: bool = True) -> str:
        """
        XML/HTML 태그를 제거하고 깨끗한 텍스트로 변환
        
        Args:
            content: 원본 내용
            preserve_structure: 구조 보존 여부 (줄바꿈, 단락 등)
            
        Returns:
            정리된 텍스트
        """
        if not content:
            return ""
            
        try:
            # HTML 엔티티 디코딩
            content = html.unescape(content)
            
            # BeautifulSoup으로 파싱
            soup = BeautifulSoup(content, 'html.parser')
            
            # 스크립트와 스타일 태그 완전 제거
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 테이블 처리 (구조 보존)
            if preserve_structure:
                # 테이블을 텍스트 형식으로 변환
                for table in soup.find_all('table'):
                    table_text = ContentCleaner._format_table(table)
                    table.replace_with(table_text)
            
            # 텍스트 추출
            text = soup.get_text(separator='\n' if preserve_structure else ' ')
            
            # 정리 작업
            text = ContentCleaner._clean_text(text, preserve_structure)
            
            return text
            
        except Exception as e:
            logger.warning(f"Content cleaning failed, returning raw text: {e}")
            # 폴백: 간단한 정규식 기반 정리
            return ContentCleaner._simple_clean(content)
    
    @staticmethod
    def _format_table(table) -> str:
        """테이블을 텍스트 형식으로 변환"""
        rows = []
        for tr in table.find_all('tr'):
            cells = []
            for td in tr.find_all(['td', 'th']):
                cell_text = td.get_text(strip=True)
                cells.append(cell_text)
            if cells:
                rows.append(' | '.join(cells))
        
        return '\n'.join(rows) if rows else ''
    
    @staticmethod
    def _clean_text(text: str, preserve_structure: bool = True) -> str:
        """텍스트 정리"""
        # 연속된 공백 제거
        text = re.sub(r'[ \t]+', ' ', text)
        
        if preserve_structure:
            # 연속된 줄바꿈을 최대 2개로 제한
            text = re.sub(r'\n{3,}', '\n\n', text)
            # 각 줄의 앞뒤 공백 제거
            lines = [line.strip() for line in text.split('\n')]
            # 빈 줄 제거 (단, 단락 구분용 빈 줄은 유지)
            cleaned_lines = []
            prev_empty = False
            for line in lines:
                if line:
                    cleaned_lines.append(line)
                    prev_empty = False
                elif not prev_empty:
                    cleaned_lines.append('')
                    prev_empty = True
            text = '\n'.join(cleaned_lines)
        else:
            # 모든 줄바꿈을 공백으로 변환
            text = re.sub(r'\s+', ' ', text)
        
        # 특수 문자 정리
        text = re.sub(r'[^\w\s\-.,;:!?()[\]{}\'"/₩%@#&*+=~`|\\가-힣]', '', text)
        
        # 앞뒤 공백 제거
        text = text.strip()
        
        return text
    
    @staticmethod
    def _simple_clean(content: str) -> str:
        """간단한 정규식 기반 정리 (폴백용)"""
        # 모든 HTML/XML 태그 제거
        text = re.sub(r'<[^>]+>', '', content)
        # HTML 엔티티 변환
        text = html.unescape(text)
        # 연속된 공백 정리
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    @staticmethod
    def clean_for_llm(content: str, max_length: int = 10000) -> str:
        """
        LLM 입력용으로 내용 정리 및 트리밍
        
        Args:
            content: 원본 내용
            max_length: 최대 길이
            
        Returns:
            LLM 입력에 적합한 정리된 텍스트
        """
        # 먼저 기본 정리
        cleaned = ContentCleaner.clean_content(content, preserve_structure=True)
        
        # 길이 제한
        if len(cleaned) > max_length:
            # 중요한 부분 우선 보존 (시작과 끝)
            half_length = max_length // 2 - 50
            cleaned = (
                cleaned[:half_length] + 
                "\n\n... [중간 내용 생략] ...\n\n" + 
                cleaned[-half_length:]
            )
        
        return cleaned
    
    @staticmethod
    def extract_key_sections(content: str) -> dict:
        """
        주요 섹션 추출
        
        Args:
            content: 원본 내용
            
        Returns:
            섹션별로 분리된 딕셔너리
        """
        cleaned = ContentCleaner.clean_content(content, preserve_structure=True)
        sections = {}
        
        # 일반적인 섹션 패턴
        section_patterns = [
            (r'(?:제\s*\d+\s*[항장절]|I+\.|\d+\.)\s*([^\n]+)', 'headers'),
            (r'(\d{4}[년\.\-]\d{1,2}[월\.\-]\d{1,2})', 'dates'),
            (r'([가-힣]+(?:주식)?회사)', 'companies'),
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:원|주|%)', 'numbers'),
        ]
        
        for pattern, section_name in section_patterns:
            matches = re.findall(pattern, cleaned)
            if matches:
                sections[section_name] = list(set(matches))[:10]  # 중복 제거, 최대 10개
        
        # 본문 요약
        sections['summary'] = cleaned[:500] if len(cleaned) > 500 else cleaned
        
        return sections


# 편의 함수들
def clean_content(content: Optional[str], preserve_structure: bool = True) -> str:
    """ContentCleaner.clean_content의 래퍼"""
    return ContentCleaner.clean_content(content, preserve_structure)


def clean_for_llm(content: str, max_length: int = 10000) -> str:
    """ContentCleaner.clean_for_llm의 래퍼"""
    return ContentCleaner.clean_for_llm(content, max_length)