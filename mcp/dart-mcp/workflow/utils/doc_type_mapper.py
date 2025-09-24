"""
문서유형 매퍼
사용자 쿼리를 분석하여 적절한 DART 문서유형 코드를 자동 선택
LLM 사용 가능 시 LLM 활용, 불가능 시 규칙 기반 폴백
"""

import re
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

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
        
    def _initialize_mappings(self) -> List[DocTypeMapping]:
        """기본 매핑 테이블 (LLM 실패 시 폴백)"""
        return [
            # 증권신고서 (C코드) - 가장 높은 우선순위
            DocTypeMapping("C001", "증권신고(지분증권)", 
                         ["증권신고서", "증권신고", "지분증권", "주식발행", "공모", "상장", "유상증자", "무상증자"], 20),
            DocTypeMapping("C002", "증권신고(채무증권)", 
                         ["채무증권", "회사채", "사채발행", "채권발행", "전환사채", "신주인수권부사채"], 19),
            DocTypeMapping("C003", "증권신고(파생결합증권)", 
                         ["파생결합증권", "파생상품", "구조화상품"], 18),
            DocTypeMapping("C004", "증권신고(합병등)", 
                         ["합병신고", "증권신고합병", "주식교환신고", "회사합병", "주식교환"], 17),
            DocTypeMapping("C006", "소액공모(지분증권)", 
                         ["소액공모", "소액지분증권"], 16),
            
            # 주요사항보고서 (B코드)
            DocTypeMapping("B001", "주요사항보고서", 
                         ["주요사항보고서", "주요사항", "자기주식", "자사주", "매수선택권", "스톡옵션", 
                          "임원", "대표이사", "이사", "소송", "계약", "영업양도", "영업양수", "자산양수도"], 15),
            
            # 정기보고서 (A코드)
            DocTypeMapping("A001", "사업보고서", 
                         ["사업보고서", "연간보고서", "연차보고서", "연례보고서"], 12),
            DocTypeMapping("A002", "반기보고서", 
                         ["반기보고서", "반기", "상반기", "하반기"], 11),
            DocTypeMapping("A003", "분기보고서", 
                         ["분기보고서", "1분기", "2분기", "3분기", "4분기", "분기실적"], 10),
            
            # 기타주요공시 (E코드)
            DocTypeMapping("E001", "자기주식취득/처분", 
                         ["자기주식취득", "자기주식처분", "자사주매입", "자사주매도", "자기주식"], 14),
            DocTypeMapping("E004", "주식매수선택권부여에관한신고", 
                         ["주식매수선택권", "스톡옵션부여", "스톡옵션"], 13),
            DocTypeMapping("E006", "주주총회소집보고서", 
                         ["주주총회", "정기주주총회", "임시주주총회"], 12),
            
            # 지분공시 (D코드)
            DocTypeMapping("D001", "주식등의대량보유상황보고서", 
                         ["대량보유", "5%룰", "지분보고", "대량보유상황"], 13),
            DocTypeMapping("D004", "공개매수", 
                         ["공개매수", "인수합병"], 12),
            
            # 감사보고서 (F코드)
            DocTypeMapping("F001", "감사보고서", 
                         ["감사보고서", "외부감사", "회계감사"], 11),
            DocTypeMapping("F002", "연결감사보고서", 
                         ["연결감사보고서", "연결감사"], 10),
            
            # 수시공시 (I코드)
            DocTypeMapping("I001", "수시공시", 
                         ["수시공시"], 9),
            DocTypeMapping("I002", "공정공시", 
                         ["공정공시"], 8),
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
        # LLM이 사용 가능한 경우 - 개선된 컨텍스트 기반 분석
        if self.llm_client:
            try:
                llm_results = await self._analyze_with_llm_context(query, langextract_result)
                if llm_results:
                    return llm_results[:max_types]
            except Exception as e:
                logger.warning(f"LLM analysis failed, falling back to rule-based mapping: {e}")
        
        # LLM 실패 시 향상된 규칙 기반 매핑 사용
        return self._enhanced_fallback_mapping(query, langextract_result, max_types)
    
    def map_query_to_doc_types_sync(self, query: str, langextract_result: Optional[Dict] = None, max_types: int = 3) -> List[Tuple[str, float]]:
        """동기 버전 - LLM 호출을 동기적으로 수행"""
        # LLM이 사용 가능한 경우 - 개선된 컨텍스트 기반 분석
        if self.llm_client:
            try:
                llm_results = self._analyze_with_llm_context_sync(query, langextract_result)
                if llm_results:
                    return llm_results[:max_types]
            except Exception as e:
                logger.warning(f"LLM analysis failed, falling back to rule-based mapping: {e}")
        
        # LLM 실패 시 향상된 규칙 기반 매핑 사용
        return self._enhanced_fallback_mapping(query, langextract_result, max_types)
    
    
    async def _analyze_with_llm_context(self, query: str, langextract_result: Optional[Dict] = None) -> List[Tuple[str, float]]:
        """
        컨텍스트 기반 LLM 분석 (비동기)
        _initialize_mappings의 정보를 컨텍스트로 제공하여 더 정확한 매핑 수행
        """
        if not self.llm_client:
            return []
            
        try:
            import os
            model_name = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
            
            # 매핑 컨텍스트 생성
            context = self._build_mapping_context()
            
            # 파싱 결과 정리
            parsed_info = self._format_langextract_result(langextract_result)
            
            # 개선된 프롬프트 구성
            prompt = f"""
다음 사용자 쿼리를 분석하여 가장 적절한 DART 문서유형을 선택하세요.

**사용자 쿼리**: {query}

**파싱된 정보**:
{parsed_info}

**사용 가능한 DART 문서유형**:
{context}

**지시사항**:
1. 사용자 쿼리의 의도와 파싱된 정보를 종합적으로 분석하세요
2. 위의 문서유형 중에서 가장 적절한 것을 최대 3개 선택하세요
3. 각 선택에 대한 신뢰도(0.0-1.0)를 제공하세요
4. 반드시 JSON 형식으로 답변하세요

**응답 형식**:
[{{"code": "문서코드", "confidence": 0.0-1.0, "reason": "선택 이유"}}]
"""
            
            response = self.llm_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a DART document classification expert. Analyze queries and select the most appropriate document types based on the given context."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            content = response.choices[0].message.content.strip()
            
            # JSON 파싱
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                results = [(item["code"], item["confidence"]) for item in result if item.get("code") and item.get("confidence")]
                logger.info(f"LLM 컨텍스트 분석 결과: {results}")
                return results
                
        except Exception as e:
            logger.error(f"LLM context analysis error: {e}")
            
        return []

    def _analyze_with_llm_context_sync(self, query: str, langextract_result: Optional[Dict] = None) -> List[Tuple[str, float]]:
        """
        컨텍스트 기반 LLM 분석 (동기)
        """
        if not self.llm_client:
            return []
            
        try:
            import os
            model_name = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
            
            # 매핑 컨텍스트 생성
            context = self._build_mapping_context()
            
            # 파싱 결과 정리
            parsed_info = self._format_langextract_result(langextract_result)
            
            # 개선된 프롬프트 구성
            prompt = f"""
다음 사용자 쿼리를 분석하여 가장 적절한 DART 문서유형을 선택하세요.

**사용자 쿼리**: {query}

**파싱된 정보**:
{parsed_info}

**사용 가능한 DART 문서유형**:
{context}

**지시사항**:
1. 사용자 쿼리의 의도와 파싱된 정보를 종합적으로 분석하세요
2. 위의 문서유형 중에서 가장 적절한 것을 최대 3개 선택하세요
3. 각 선택에 대한 신뢰도(0.0-1.0)를 제공하세요
4. 반드시 JSON 형식으로 답변하세요

**응답 형식**:
[{{"code": "문서코드", "confidence": 0.0-1.0, "reason": "선택 이유"}}]
"""
            
            response = self.llm_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a DART document classification expert. Analyze queries and select the most appropriate document types based on the given context."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            content = response.choices[0].message.content.strip()
            
            # JSON 파싱
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                results = [(item["code"], item["confidence"]) for item in result if item.get("code") and item.get("confidence")]
                logger.info(f"LLM 컨텍스트 분석 결과: {results}")
                return results
                
        except Exception as e:
            logger.error(f"LLM context analysis error: {e}")
            
        return []

    def _build_mapping_context(self) -> str:
        """매핑 컨텍스트 구성 - _initialize_mappings의 정보를 문자열로 변환"""
        context_lines = []
        
        for mapping in self.fallback_mappings:
            keywords_str = ", ".join(mapping.keywords)
            context_lines.append(f"- {mapping.code}: {mapping.name}")
            context_lines.append(f"  키워드: {keywords_str}")
            context_lines.append("")
        
        return "\n".join(context_lines)

    def _format_langextract_result(self, langextract_result: Optional[Dict]) -> str:
        """LangExtract 결과를 읽기 쉬운 형태로 포맷"""
        if not langextract_result:
            return "파싱된 정보가 없습니다."
        
        info_parts = []
        
        # 추출된 문서유형
        if langextract_result.get('doc_types'):
            doc_names = [dt.get('name', '') for dt in langextract_result['doc_types'] if dt.get('name')]
            if doc_names:
                info_parts.append(f"추출된 문서유형: {', '.join(doc_names)}")
        
        # 추출된 키워드
        if langextract_result.get('keywords'):
            keywords = [kw.get('text', '') if isinstance(kw, dict) else str(kw) 
                       for kw in langextract_result['keywords']]
            if keywords:
                info_parts.append(f"관련 키워드: {', '.join(keywords)}")
        
        # 기업명
        if langextract_result.get('companies'):
            info_parts.append(f"기업: {', '.join(langextract_result['companies'])}")
        
        # 날짜 표현
        if langextract_result.get('date_expressions'):
            date_texts = [de.get('text', '') if isinstance(de, dict) else str(de) 
                         for de in langextract_result['date_expressions']]
            if date_texts:
                info_parts.append(f"기간: {', '.join(date_texts)}")
        
        return "\n".join(info_parts) if info_parts else "특별한 파싱 정보가 없습니다."

    def _enhanced_fallback_mapping(self, query: str, langextract_result: Optional[Dict], max_types: int) -> List[Tuple[str, float]]:
        """
        향상된 규칙 기반 매핑 - doc_types와 keywords를 우선적으로 고려
        
        Args:
            query: 원본 쿼리
            langextract_result: LangExtract 파싱 결과
            max_types: 최대 반환 개수
            
        Returns:
            [(문서유형코드, 신뢰도)] 리스트
        """
        logger.info("향상된 규칙 기반 매핑 시작")
        scores = {}
        
        # 1. LangExtract doc_types 우선 처리 (가장 높은 가중치)
        if langextract_result and langextract_result.get('doc_types'):
            for doc in langextract_result['doc_types']:
                doc_name = doc.get('name', '').lower()
                logger.info(f"LangExtract 문서유형 분석: '{doc_name}'")
                
                # 정확한 문서명 매칭
                best_match = self._find_best_document_match(doc_name)
                if best_match:
                    code, confidence = best_match
                    scores[code] = scores.get(code, 0) + confidence * 100  # 최고 가중치
                    logger.info(f"  → 문서명 매칭: {code} (신뢰도: {confidence:.3f})")

        # 2. LangExtract keywords 처리
        if langextract_result and langextract_result.get('keywords'):
            for kw in langextract_result['keywords']:
                kw_text = kw.get('text', '') if isinstance(kw, dict) else str(kw)
                kw_lower = kw_text.lower()
                
                for mapping in self.fallback_mappings:
                    for keyword in mapping.keywords:
                        if keyword in kw_lower or kw_lower in keyword:
                            if mapping.code not in scores:
                                scores[mapping.code] = 0
                            scores[mapping.code] += mapping.priority * 2  # 키워드 매칭
                            logger.info(f"  → 키워드 매칭: {mapping.code} (키워드: {kw_text})")

        # 3. 원본 쿼리에서도 매핑 (낮은 가중치)
        query_lower = query.lower()
        for mapping in self.fallback_mappings:
            for keyword in mapping.keywords:
                if keyword in query_lower:
                    if mapping.code not in scores:
                        scores[mapping.code] = 0
                    scores[mapping.code] += mapping.priority * 0.5  # 낮은 가중치
        
        # 점수 정규화 및 정렬
        if scores:
            max_score = max(scores.values())
            results = [(code, min(score/max_score, 1.0)) for code, score in scores.items()]
            results.sort(key=lambda x: x[1], reverse=True)
            logger.info(f"향상된 규칙 매핑 결과: {results[:max_types]}")
            return results[:max_types]
        
        # 결과가 없으면 기본값 반환
        logger.warning("향상된 규칙 매핑 실패, 기본값 사용: B001 (주요사항보고서)")
        return [("B001", 0.3)]

    def _find_best_document_match(self, doc_name: str) -> Optional[Tuple[str, float]]:
        """
        문서명과 가장 일치도가 높은 매핑 찾기
        
        Args:
            doc_name: 문서명 (소문자)
            
        Returns:
            (코드, 신뢰도) 또는 None
        """
        best_match = None
        best_score = 0.0
        
        for mapping in self.fallback_mappings:
            mapping_name_lower = mapping.name.lower()
            
            # 정확한 매칭
            if doc_name == mapping_name_lower or doc_name in mapping_name_lower or mapping_name_lower in doc_name:
                confidence = 1.0 if doc_name == mapping_name_lower else 0.9
                if confidence > best_score:
                    best_match = (mapping.code, confidence)
                    best_score = confidence
                    
            # 키워드 매칭
            for keyword in mapping.keywords:
                if keyword in doc_name or doc_name in keyword:
                    confidence = 0.8
                    if confidence > best_score:
                        best_match = (mapping.code, confidence)
                        best_score = confidence
        
        return best_match
    
    
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