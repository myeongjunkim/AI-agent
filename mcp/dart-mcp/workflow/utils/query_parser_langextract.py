"""
LangExtract 쿼리 파서
자연어 쿼리에서 기업명, 문서유형 등을 추출
"""

from typing import Dict, List, Optional, Any
import re
from pathlib import Path

# LangExtract import
try:
    import langextract as lx
    LANGEXTRACT_AVAILABLE = True
except ImportError:
    LANGEXTRACT_AVAILABLE = False
    print("⚠️ LangExtract가 설치되지 않았습니다. pip install langextract")


class QueryParserLangExtract:
    """LangExtract를 사용한 자연어 쿼리 파서"""
    
    def __init__(self, api_key: Optional[str] = None, model_id: Optional[str] = None):
        """
        Args:
            api_key: Gemini API 키 (None일 경우 환경변수에서 로드)
            model_id: 사용할 모델 ID (기본값: gemini-2.0-flash-exp)
        """
        if not LANGEXTRACT_AVAILABLE:
            raise ImportError("LangExtract가 설치되지 않았습니다. pip install langextract")
        
        # API 설정
        import os
        from dotenv import load_dotenv
        load_dotenv('.env')
        
        self.api_key = api_key or os.getenv('LANGEXTRACT_API_KEY') or os.getenv('GEMINI_API_KEY')
        self.model_id = model_id or os.getenv('LANGEXTRACT_MODEL', 'gemini-2.0-flash-exp')
        
        if not self.api_key:
            print("⚠️ LANGEXTRACT_API_KEY가 설정되지 않았습니다.")
            print("   .env 파일에 LANGEXTRACT_API_KEY를 설정하거나")
            print("   https://aistudio.google.com/apikey 에서 API 키를 발급받으세요.")
        
        # 프롬프트 및 예제 설정
        self._setup_extraction()
    
    def _setup_extraction(self):
        """추출 설정"""
        # 프롬프트 로드
        self.extraction_prompt = self._load_prompt('query_extraction.txt')
        
        # LangExtract 예제 데이터
        self.examples = [
            self._create_example(
                text="삼성전자의 올해 사업보고서 보여줘",
                extractions=[
                    {"class": "company", "text": "삼성전자", "attributes": {"type": "company_name"}},
                    {"class": "date_range", "text": "올해", "attributes": {"type": "current_year"}},
                    {"class": "doc_type", "text": "사업보고서", "attributes": {"code": "A001"}}
                ]
            ),
            self._create_example(
                text="005930 2024년 1분기 실적",
                extractions=[
                    {"class": "company", "text": "005930", "attributes": {"type": "stock_code"}},
                    {"class": "date_range", "text": "2024년 1분기", "attributes": {"year": 2024, "quarter": 1}},
                    {"class": "keywords", "text": "실적", "attributes": {"type": "financial"}}
                ]
            ),
            self._create_example(
                text="네이버와 카카오의 최근 3년간 매출 비교",
                extractions=[
                    {"class": "company", "text": "네이버", "attributes": {"type": "company_name"}},
                    {"class": "company", "text": "카카오", "attributes": {"type": "company_name"}},
                    {"class": "date_range", "text": "최근 3년간", "attributes": {"type": "relative", "years": 3}},
                    {"class": "keywords", "text": "매출", "attributes": {"type": "financial"}}
                ]
            ),
            self._create_example(
                text="LG전자 주요사항보고서 중 자기주식 관련",
                extractions=[
                    {"class": "company", "text": "LG전자", "attributes": {"type": "company_name"}},
                    {"class": "doc_type", "text": "주요사항보고서", "attributes": {"code": "B001"}},
                    {"class": "keywords", "text": "자기주식", "attributes": {"type": "corporate_action"}}
                ]
            )
        ]
    
    def _load_prompt(self, filename: str) -> str:
        """프롬프트 파일 로드"""
        prompt_path = Path(__file__).parent.parent.parent / 'prompts' / filename
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"프롬프트 파일 로드 실패 ({filename}): {e}")
            # 기본 프롬프트
            return """한국어 금융/공시 관련 쿼리에서 다음 정보를 추출하세요:
- company: 기업명 또는 종목코드
- doc_type: 문서 유형
- date_range: 날짜 관련 표현
- keywords: 핵심 키워드"""
    
    def _create_example(self, text: str, extractions: List[Dict]) -> Any:
        """LangExtract 예제 데이터 생성"""
        extraction_objects = []
        for ext in extractions:
            extraction_objects.append(
                lx.data.Extraction(
                    extraction_class=ext['class'],
                    extraction_text=ext['text'],
                    attributes=ext.get('attributes', {})
                )
            )
        return lx.data.ExampleData(text=text, extractions=extraction_objects)
    
    async def parse_query(self, query: str) -> Dict[str, Any]:
        """
        자연어 쿼리 파싱
        
        Args:
            query: 사용자 쿼리
            
        Returns:
            파싱된 정보 딕셔너리
        """
        try:
            return self._parse_with_langextract(query)
        except Exception as e:
            print(f"LangExtract 파싱 실패: {e}")
            return self._fallback_parse(query)
    
    def parse_query_sync(self, query: str) -> Dict[str, Any]:
        """동기 버전 쿼리 파싱"""
        try:
            return self._parse_with_langextract(query)
        except Exception as e:
            print(f"LangExtract 파싱 실패: {e}")
            return self._fallback_parse(query)
    
    def _parse_with_langextract(self, query: str) -> Dict[str, Any]:
        """LangExtract를 사용한 파싱"""
        if not self.api_key:
            print("API 키가 설정되지 않아 폴백 파서를 사용합니다.")
            return self._fallback_parse(query)
        
        # LangExtract로 정보 추출
        result = lx.extract(
            text_or_documents=query,
            prompt_description=self.extraction_prompt,
            examples=self.examples,
            model_id=self.model_id,
            api_key=self.api_key
        )
        
        # 추출 결과 구조화
        parsed = {
            "companies": [],
            "stock_codes": [],
            "doc_types": [],
            "date_expressions": [],
            "keywords": []
        }
        
        # 추출 결과 처리
        for extraction in result.extractions:
            if extraction.extraction_class == "company":
                if extraction.attributes.get("type") == "stock_code":
                    parsed["stock_codes"].append(extraction.extraction_text)
                else:
                    parsed["companies"].append(extraction.extraction_text)
                    
            elif extraction.extraction_class == "doc_type":
                doc_info = {
                    "name": extraction.extraction_text,
                    "code": extraction.attributes.get("code", ""),
                    "category": self._get_doc_category(extraction.extraction_text)
                }
                parsed["doc_types"].append(doc_info)
                
            elif extraction.extraction_class == "date_range":
                date_info = {
                    "text": extraction.extraction_text,
                    "type": extraction.attributes.get("type", ""),
                    "attributes": extraction.attributes
                }
                parsed["date_expressions"].append(date_info)
                
            elif extraction.extraction_class == "keywords":
                keyword_info = {
                    "text": extraction.extraction_text,
                    "type": extraction.attributes.get("type", ""),
                    "category": extraction.attributes.get("category", "")
                }
                parsed["keywords"].append(keyword_info)
        
        return parsed
    
    def _get_doc_category(self, doc_name: str) -> str:
        """문서유형 카테고리 반환"""
        if doc_name in ["사업보고서", "반기보고서", "분기보고서"]:
            return "정기공시"
        elif doc_name in ["감사보고서"]:
            return "감사보고서"
        else:
            return "주요사항"
    
    def _fallback_parse(self, query: str) -> Dict[str, Any]:
        """
        API 실패 시 규칙 기반 폴백 파싱
        
        Args:
            query: 사용자 쿼리
            
        Returns:
            기본 파싱 결과
        """
        parsed = {
            "companies": [],
            "stock_codes": [],
            "doc_types": [],
            "date_expressions": [],
            "keywords": []
        }
        
        # 종목코드 패턴 (6자리 숫자)
        stock_codes = re.findall(r'\b\d{6}\b', query)
        parsed["stock_codes"] = stock_codes
        
        # 기업명 패턴 (주요 기업들)
        company_patterns = [
            '삼성전자', 'LG전자', 'SK하이닉스', '현대차', '현대자동차',
            '네이버', '카카오', '쿠팡', '배달의민족', '토스',
            '포스코', '롯데', '신세계', '한화', '두산',
            'CJ', 'GS', 'KT', 'LG화학', 'SK이노베이션'
        ]
        for pattern in company_patterns:
            if pattern in query:
                parsed["companies"].append(pattern)
        
        # 문서유형 패턴
        doc_type_patterns = {
            '사업보고서': ('A001', '정기공시'),
            '반기보고서': ('A002', '정기공시'),
            '분기보고서': ('A003', '정기공시'),
            '주요사항보고서': ('B001', '주요사항'),
            '감사보고서': ('F001', '감사보고서'),
            '증권신고서': ('C001', '증권신고'),
            '자기주식': ('E001', '기타공시'),
            '주식매수선택권': ('E004', '기타공시')
        }
        
        for doc_name, (doc_code, category) in doc_type_patterns.items():
            if doc_name in query:
                parsed["doc_types"].append({
                    "name": doc_name,
                    "code": doc_code,
                    "category": category
                })
        
        # 날짜 표현
        date_patterns = [
            (r'올해', 'current_year'),
            (r'작년', 'last_year'),
            (r'최근', 'recent'),
            (r'\d{4}년', 'specific_year'),
            (r'\d분기', 'quarter'),
            (r'상반기', 'first_half'),
            (r'하반기', 'second_half')
        ]
        
        for pattern, date_type in date_patterns:
            matches = re.findall(pattern, query)
            for match in matches:
                parsed["date_expressions"].append({
                    "text": match,
                    "type": date_type
                })
        
        # 키워드 추출
        keyword_patterns = [
            '매출', '영업이익', '순이익', '배당', '증자', '감자',
            '인수합병', 'M&A', '실적', '재무제표', '자산', '부채'
        ]
        
        for keyword in keyword_patterns:
            if keyword in query:
                parsed["keywords"].append({
                    "text": keyword,
                    "type": "financial"
                })
        
        return parsed