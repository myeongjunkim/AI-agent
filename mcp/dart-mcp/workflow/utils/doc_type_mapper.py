"""
문서유형 매퍼
사용자 쿼리를 분석하여 적절한 DART 문서유형 코드를 자동 선택
LLM 사용 가능 시 LLM 활용, 불가능 시 규칙 기반 폴백
"""

import re
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path

from utils.logging import get_logger

logger = get_logger("doc_type_mapper")


@dataclass
class DocTypeMapping:
    """문서유형 매핑 정보"""
    code: str
    name: str
    keywords: List[str]
    priority: int = 0


class DocTypeMapper:
    """DART 문서유형 자동 매핑 (LLM + 규칙 기반)"""
    
    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: OpenAI 클라이언트 (선택적)
        """
        self.llm_client = llm_client
        self.fallback_mappings = self._initialize_mappings()
        self.prompt_template = self._load_prompt_template()
    
    def _load_prompt_template(self) -> Optional[str]:
        """프롬프트 템플릿 로드"""
        prompt_path = Path(__file__).parent.parent.parent / 'prompts' / 'doc_type_mapping.txt'
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"프롬프트 파일 로드 실패: {e}")
            return None
        
    def _initialize_mappings(self) -> List[DocTypeMapping]:
        """기본 매핑 테이블 (LLM 실패 시 폴백)"""
        return [
            # 핵심 문서유형만 유지
            DocTypeMapping("B001", "주요사항보고서", 
                         ["자기주식", "자사주", "매수선택권", "스톡옵션", "임원", "대표이사",
                          "이사", "합병", "분할", "증자", "감자", "소송", "계약"], 15),
            DocTypeMapping("A001", "사업보고서", 
                         ["사업보고서", "연간보고서", "연차보고서"], 10),
            DocTypeMapping("A002", "반기보고서", 
                         ["반기보고서", "반기", "상반기", "하반기"], 9),
            DocTypeMapping("A003", "분기보고서", 
                         ["분기보고서", "1분기", "3분기", "분기실적"], 8),
            DocTypeMapping("E001", "자기주식취득처분", 
                         ["자기주식취득", "자기주식처분", "자사주매입", "자사주매도"], 14),
            DocTypeMapping("E004", "주식매수선택권", 
                         ["주식매수선택권", "스톡옵션부여"], 13),
            DocTypeMapping("D001", "대량보유상황보고서", 
                         ["5%룰", "대량보유", "지분보고"], 13),
            DocTypeMapping("F001", "감사보고서", 
                         ["감사보고서", "외부감사", "회계감사"], 12),
        ]
    
    async def map_query_to_doc_types(self, query: str, langextract_result: Optional[Dict] = None, max_types: int = 3) -> List[Tuple[str, float]]:
        """
        쿼리와 LangExtract 결과를 종합하여 적절한 문서유형 코드 추출
        
        Args:
            query: 사용자 쿼리
            langextract_result: LangExtract에서 추출한 결과 (doc_types, keywords 등)
            max_types: 최대 반환 개수
            
        Returns:
            [(문서유형코드, 신뢰도)] 리스트
        """
        # LLM이 사용 가능한 경우
        if self.llm_client:
            try:
                llm_results = await self._analyze_with_llm(query, langextract_result)
                if llm_results:
                    return llm_results[:max_types]
            except Exception as e:
                logger.warning(f"LLM analysis failed, falling back to basic rules: {e}")
        
        # LLM 실패 시 기본 규칙 사용
        return self._fallback_mapping_with_context(query, langextract_result, max_types)
    
    def map_query_to_doc_types_sync(self, query: str, langextract_result: Optional[Dict] = None, max_types: int = 3) -> List[Tuple[str, float]]:
        """동기 버전 - LLM 호출을 동기적으로 수행"""
        # LLM이 사용 가능한 경우
        if self.llm_client:
            try:
                llm_results = self._analyze_with_llm_sync(query, langextract_result)
                if llm_results:
                    return llm_results[:max_types]
            except Exception as e:
                logger.warning(f"LLM analysis failed, falling back to basic rules: {e}")
        
        # LLM 실패 시 기본 규칙 사용
        return self._fallback_mapping_with_context(query, langextract_result, max_types)
    
    async def _analyze_with_llm(self, query: str, langextract_result: Optional[Dict] = None) -> List[Tuple[str, float]]:
        """LLM을 사용한 쿼리 분석 (비동기)"""
        if not self.llm_client:
            return []
            
        try:
            import os
            model_name = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
            
            # 프롬프트 템플릿 사용
            if self.prompt_template:
                prompt = self._build_prompt(query, langextract_result)
            else:
                prompt = f"""
다음 쿼리를 분석하여 적절한 DART 문서유형을 선택하세요.
쿼리: {query}

JSON 형식으로 답하세요: [{"code": "문서코드", "confidence": 0.0-1.0}]
"""
            
            response = self.llm_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a Korean financial document classification expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            content = response.choices[0].message.content.strip()
            
            # JSON 파싱
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return [(item["code"], item["confidence"]) for item in result]
                
        except Exception as e:
            logger.error(f"LLM analysis error: {e}")
            
        return []
    
    def _analyze_with_llm_sync(self, query: str, langextract_result: Optional[Dict] = None) -> List[Tuple[str, float]]:
        """LLM을 사용한 쿼리 분석 (동기)"""
        if not self.llm_client:
            return []
            
        try:
            import os
            model_name = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
            
            # 프롬프트 템플릿 사용
            if self.prompt_template:
                prompt = self._build_prompt(query, langextract_result)
            else:
                prompt = f"""
다음 쿼리를 분석하여 적절한 DART 문서유형을 선택하세요.
쿼리: {query}

JSON 형식으로 답하세요: [{"code": "문서코드", "confidence": 0.0-1.0}]
"""
            
            response = self.llm_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a Korean financial document classification expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            content = response.choices[0].message.content.strip()
            
            # JSON 파싱
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return [(item["code"], item["confidence"]) for item in result]
                
        except Exception as e:
            logger.error(f"LLM analysis error: {e}")
            
        return []
    
    def _build_prompt(self, query: str, langextract_result: Optional[Dict] = None) -> str:
        """
        LangExtract 결과를 포함한 프롬프트 생성
        
        Args:
            query: 원본 쿼리
            langextract_result: LangExtract 파싱 결과
            
        Returns:
            완성된 프롬프트
        """
        prompt = self.prompt_template.replace('{query}', query)
        
        # LangExtract 결과가 있으면 추가
        if langextract_result:
            context_parts = []
            
            # 추출된 문서유형
            if langextract_result.get('doc_types'):
                doc_names = [dt.get('name', '') for dt in langextract_result['doc_types'] if dt.get('name')]
                if doc_names:
                    context_parts.append(f"추출된 문서유형: {', '.join(doc_names)}")
            
            # 추출된 키워드
            if langextract_result.get('keywords'):
                keywords = [kw.get('text', '') if isinstance(kw, dict) else str(kw) 
                           for kw in langextract_result['keywords']]
                if keywords:
                    context_parts.append(f"관련 키워드: {', '.join(keywords)}")
            
            # 기업명
            if langextract_result.get('companies'):
                context_parts.append(f"기업: {', '.join(langextract_result['companies'])}")
            
            # 날짜 표현
            if langextract_result.get('date_expressions'):
                date_texts = [de.get('text', '') if isinstance(de, dict) else str(de) 
                             for de in langextract_result['date_expressions']]
                if date_texts:
                    context_parts.append(f"기간: {', '.join(date_texts)}")
            
            if context_parts:
                context = "\n\nLangExtract 분석 결과:\n" + "\n".join(context_parts)
                prompt = prompt.replace('\n\nJSON 형식으로', context + '\n\nJSON 형식으로')
        
        return prompt
    
    def _fallback_mapping_with_context(self, query: str, langextract_result: Optional[Dict], max_types: int) -> List[Tuple[str, float]]:
        """
        LangExtract 결과를 활용한 규칙 기반 매핑
        
        Args:
            query: 원본 쿼리
            langextract_result: LangExtract 파싱 결과
            max_types: 최대 반환 개수
            
        Returns:
            [(문서유형코드, 신뢰도)] 리스트
        """
        query_lower = query.lower()
        scores = {}
        
        # LangExtract에서 추출한 문서유형이 있으면 우선 처리
        if langextract_result and langextract_result.get('doc_types'):
            for doc in langextract_result['doc_types']:
                doc_name = doc.get('name', '').lower()
                
                # 직접 매핑 시도
                for mapping in self.fallback_mappings:
                    for keyword in mapping.keywords:
                        if keyword in doc_name:
                            if mapping.code not in scores:
                                scores[mapping.code] = 0
                            scores[mapping.code] += mapping.priority * 2  # LangExtract 결과는 가중치 2배
                            break
        
        # 원본 쿼리에서도 매핑
        for mapping in self.fallback_mappings:
            for keyword in mapping.keywords:
                if keyword in query_lower:
                    if mapping.code not in scores:
                        scores[mapping.code] = 0
                    scores[mapping.code] += mapping.priority
        
        # LangExtract 키워드도 고려
        if langextract_result and langextract_result.get('keywords'):
            for kw in langextract_result['keywords']:
                kw_text = kw.get('text', '') if isinstance(kw, dict) else str(kw)
                kw_lower = kw_text.lower()
                
                for mapping in self.fallback_mappings:
                    for keyword in mapping.keywords:
                        if keyword in kw_lower:
                            if mapping.code not in scores:
                                scores[mapping.code] = 0
                            scores[mapping.code] += mapping.priority * 0.5  # 키워드는 낮은 가중치
        
        # 점수 정규화 및 정렬
        if scores:
            max_score = max(scores.values())
            results = [(code, score/max_score) for code, score in scores.items()]
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:max_types]
        
        return []
    
    def _fallback_mapping(self, query: str, max_types: int) -> List[Tuple[str, float]]:
        """레거시 폴백 매핑 (하위 호환성)"""
        """LLM 없이 기본 규칙 기반 매핑"""
        query_lower = query.lower()
        scores = {}
        
        for mapping in self.fallback_mappings:
            score = 0.0
            
            for keyword in mapping.keywords:
                if keyword.lower() in query_lower:
                    score += 2.0
                elif len(keyword) >= 3 and keyword.lower()[:3] in query_lower:
                    score += 1.0
            
            if score > 0:
                score *= (1 + mapping.priority / 20)
                scores[mapping.code] = score
        
        # 정렬 및 정규화
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        
        for code, score in sorted_scores[:max_types]:
            confidence = min(score / 10, 1.0)
            results.append((code, confidence))
        
        # 기본값
        if not results:
            results = [("B001", 0.3)]
            
        return results
    
    def get_doc_type_name(self, code: str) -> str:
        """문서유형 코드의 이름 반환"""
        doc_names = {
            # A: 정기보고서
            "A001": "사업보고서", "A002": "반기보고서", "A003": "분기보고서",
            "A004": "등록법인결산서류", "A005": "소액공모법인결산서류",
            
            # B: 주요사항보고서
            "B001": "주요사항보고서", "B002": "주요경영사항신고", "B003": "최대주주등과의거래신고",
            
            # C: 증권신고서
            "C001": "증권신고(지분증권)", "C002": "증권신고(채무증권)", "C003": "증권신고(파생결합증권)",
            "C004": "증권신고(합병등)", "C005": "증권신고(기타)", "C006": "소액공모(지분증권)",
            "C007": "소액공모(채무증권)", "C008": "소액공모(파생결합증권)", "C009": "소액공모(합병등)",
            "C010": "소액공모(기타)", "C011": "호가중개시스템을통한소액매출",
            
            # D: 지분공시
            "D001": "주식등의대량보유상황보고서", "D002": "임원ㆍ주요주주특정증권등소유상황보고서",
            "D003": "의결권대리행사권유", "D004": "공개매수", "D005": "임원ㆍ주요주주특정증권등거래계획보고서",
            
            # E: 기타주요공시
            "E001": "자기주식취득/처분", "E002": "신탁계약체결/해지", "E003": "합병등종료보고서",
            "E004": "주식매수선택권부여에관한신고", "E005": "사외이사에관한신고", "E006": "주주총회소집보고서",
            "E007": "시장조성/안정조작", "E008": "합병등신고서", "E009": "금융위등록/취소",
            "E010": "이중상환청구권부채권(커버드본드)",
            
            # F: 감사보고서
            "F001": "감사보고서", "F002": "연결감사보고서", "F003": "결합감사보고서",
            "F004": "회계법인사업보고서", "F005": "감사전재무제표미제출신고서",
            
            # G: 집합투자
            "G001": "증권신고(집합투자증권-신탁형)", "G002": "증권신고(집합투자증권-회사형)",
            "G003": "증권신고(집합투자증권-합병)",
            
            # H: 자산유동화
            "H001": "자산유동화계획/양도등록", "H002": "사업/반기/분기보고서",
            "H003": "증권신고(유동화증권등)", "H004": "채권유동화계획/양도등록",
            "H005": "자산유동화관련중요사항발생등보고", "H006": "주요사항보고서",
            
            # I: 거래소공시
            "I001": "수시공시", "I002": "공정공시", "I003": "시장조치/안내",
            "I004": "지분공시", "I005": "증권투자회사", "I006": "채권공시",
            
            # J: 공정위공시
            "J001": "대규모내부거래관련", "J002": "대규모내부거래관련(구)",
            "J004": "기업집단현황공시", "J005": "비상장회사중요사항공시",
            "J006": "기타공정위공시", "J008": "대규모내부거래관련(공익법인용)",
            "J009": "하도급대금결제조건공시"
        }
        return doc_names.get(code, code)