"""
충분성 검사기
수집된 정보가 사용자 질의에 답변하기에 충분한지 평가
"""

import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from utils.logging import get_logger

logger = get_logger("sufficiency_checker")


@dataclass
class SufficiencyResult:
    """충분성 검사 결과"""
    is_sufficient: bool
    confidence: float  # 0.0 ~ 1.0
    missing_aspects: List[str]
    suggestions: List[str]
    reason: str


class SufficiencyChecker:
    """정보 충분성 검사 (LLM 기반)"""
    
    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: LLM 클라이언트 (필수)
        """
        self.llm_client = llm_client
        self.prompt_template = self._load_prompt_template()
        self.filter_prompt_template = self._load_filter_prompt_template()
    
    def _load_prompt_template(self) -> Optional[str]:
        """프롬프트 템플릿 로드"""
        try:
            prompt_path = Path("prompts/sufficiency_analysis.txt")
            if prompt_path.exists():
                with open(prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            else:
                logger.warning(f"Prompt template not found: {prompt_path}")
        except Exception as e:
            logger.error(f"Failed to load prompt template: {e}")
        return None
    
    def _load_filter_prompt_template(self) -> Optional[str]:
        """문서 필터링 프롬프트 템플릿 로드"""
        try:
            prompt_path = Path("prompts/document_filter.txt")
            if prompt_path.exists():
                with open(prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            else:
                logger.debug(f"Filter prompt template not found: {prompt_path}, using default")
        except Exception as e:
            logger.error(f"Failed to load filter prompt template: {e}")
        return None
    
    async def check_sufficiency(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        expanded_query: Dict[str, Any]
    ) -> SufficiencyResult:
        """
        정보 충분성 검사 (LLM 기반)
        
        Args:
            query: 원본 쿼리
            documents: 수집된 문서들
            expanded_query: 확장된 쿼리 정보
            
        Returns:
            충분성 검사 결과
        """
        logger.info(f"Checking sufficiency for {len(documents)} documents")
        
        # 문서 필터링 - 관련성 있는 문서만 선별
        filtered_documents = await self.filter_relevant_documents(
            query, documents, expanded_query
        )
        logger.info(f"Filtered to {len(filtered_documents)} relevant documents from {len(documents)}")
        
        # LLM 사용 가능 여부 확인
        if not self.llm_client:
            logger.warning("LLM client not available, using simple fallback")
            return self._simple_fallback(query, filtered_documents, expanded_query)
        
        if not self.prompt_template:
            logger.warning("Prompt template not available, using simple fallback")
            return self._simple_fallback(query, filtered_documents, expanded_query)
        
        try:
            # 메트릭 계산
            metrics = self._calculate_basic_metrics(filtered_documents, expanded_query)
            
            # 프롬프트 생성
            if self.prompt_template:
                prompt = self.prompt_template.format(
                    query=query,
                    doc_count=len(filtered_documents),
                    companies_covered=len(metrics["companies"]),
                    companies_expected=len(expanded_query.get("companies", [])),
                    date_coverage=metrics["date_coverage"],
                    doc_type_match=metrics["doc_type_match"]
                )
            else:
                # 기본 프롬프트
                prompt = f"""
                사용자 질의: {query}
                수집된 문서: {len(filtered_documents)}개
                
                충분성을 평가하고 다음 JSON 형식으로 응답하세요:
                {{
                    "is_sufficient": true/false,
                    "confidence_score": 0.5,
                    "missing_aspects": [],
                    "recommendations": [],
                    "summary": "평가 요약"
                }}
                """
            
            # 환경변수에서 모델명 가져오기
            import os
            model_name = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
            
            # LLM 호출
            logger.debug("Calling LLM for sufficiency check")
            response = self.llm_client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "당신은 DART 공시 정보의 충분성을 평가하는 전문가입니다. JSON 형식으로 응답해주세요."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=500
            )
            
            # 응답 파싱
            response_text = response.choices[0].message.content
            logger.debug(f"LLM response: {response_text[:200]}...")
            
            # JSON 추출
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result_data = json.loads(json_match.group())
                
                result = SufficiencyResult(
                    is_sufficient=result_data.get("is_sufficient", False),
                    confidence=float(result_data.get("confidence_score", 0.5)),
                    missing_aspects=result_data.get("missing_aspects", []),
                    suggestions=result_data.get("recommendations", []),
                    reason=result_data.get("summary", "충분성 평가 완료")
                )
                
                logger.info(f"Sufficiency check complete: {result.is_sufficient} "
                          f"(confidence: {result.confidence:.2f})")
                return result
            else:
                logger.error("Failed to parse JSON from LLM response")
                return self._simple_fallback(query, filtered_documents, expanded_query)
                
        except Exception as e:
            logger.error(f"LLM sufficiency check error: {e}")
            return self._simple_fallback(query, filtered_documents, expanded_query)
    
    async def filter_relevant_documents(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        expanded_query: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        사용자 질의와 관련된 문서만 필터링
        
        Args:
            query: 원본 사용자 질의
            documents: 검색된 모든 문서들
            expanded_query: 확장된 쿼리 정보
            
        Returns:
            처리가 필요한 관련 문서들만 필터링된 리스트
        """
        if not documents:
            return []
        
        # LLM이 없으면 간단한 규칙 기반 필터링
        if not self.llm_client:
            return self._simple_filter(query, documents, expanded_query)
        
        try:
            filtered_docs = []
            batch_size = 5  # 배치 처리를 위한 크기
            
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i+batch_size]
                
                # 배치 문서 정보 준비
                doc_summaries = []
                for doc in batch:
                    summary = {
                        "index": i + batch.index(doc),
                        "report_nm": doc.get("report_nm", ""),
                        "corp_name": doc.get("corp_name", ""),
                        "rcept_dt": doc.get("rcept_dt", ""),
                        "extract_result": doc.get("extract_result", {})
                    }
                    doc_summaries.append(summary)
                
                # 필터링 프롬프트 생성
                if self.filter_prompt_template:
                    prompt = self.filter_prompt_template.format(
                        query=query,
                        doc_summaries=json.dumps(doc_summaries, ensure_ascii=False, indent=2),
                        expanded_query=json.dumps(expanded_query, ensure_ascii=False, indent=2)
                    )
                else:
                    prompt = f"""
                    사용자 질의: {query}
                    
                    다음 공시 문서들 중 사용자 질의에 답변하기 위해 실제로 처리가 필요한 문서만 선별해주세요.
                    
                    문서 목록:
                    {json.dumps(doc_summaries, ensure_ascii=False, indent=2)}
                    
                    다음 기준으로 평가해주세요:
                    1. report_nm(공시 제목)과 사용자 질의의 관련성
                    2. extract_result의 내용이 질의와 직접적인 관련이 있는지
                    3. 중복되거나 불필요한 정보는 제외
                    
                    JSON 형식으로 응답:
                    {{
                        "relevant_indices": [0, 2, 3],  // 관련 있는 문서의 인덱스
                        "reason": "선별 이유 간단 설명"
                    }}
                    """
                
                # LLM 호출
                import os
                model_name = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
                
                response = self.llm_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "당신은 DART 공시 문서의 관련성을 평가하는 전문가입니다. 사용자 질의에 직접적으로 필요한 문서만 선별해주세요."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=300
                )
                
                # 응답 파싱
                response_text = response.choices[0].message.content
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                
                if json_match:
                    result_data = json.loads(json_match.group())
                    relevant_indices = result_data.get("relevant_indices", [])
                    
                    # 선별된 문서 추가
                    for idx in relevant_indices:
                        if 0 <= idx < len(batch):
                            filtered_docs.append(batch[idx])
                    
                    logger.debug(f"Batch filtering: {len(relevant_indices)}/{len(batch)} documents selected. "
                               f"Reason: {result_data.get('reason', 'N/A')}")
                else:
                    # 파싱 실패시 전체 배치 포함
                    logger.warning("Failed to parse filter response, including all documents in batch")
                    filtered_docs.extend(batch)
            
            # 필터링 결과가 없으면 상위 N개 반환
            if not filtered_docs and documents:
                logger.warning("No documents passed filtering, returning top 5")
                return documents[:5]
            
            return filtered_docs
            
        except Exception as e:
            logger.error(f"Document filtering error: {e}")
            return self._simple_filter(query, documents, expanded_query)
    
    def _simple_filter(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        expanded_query: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """간단한 규칙 기반 문서 필터링"""
        filtered = []
        query_lower = query.lower()
        
        # 쿼리에서 키워드 추출
        keywords = []
        if expanded_query.get("companies"):
            keywords.extend([c.lower() for c in expanded_query["companies"]])
        if expanded_query.get("report_types"):
            keywords.extend([r.lower() for r in expanded_query["report_types"]])
        
        # 질의에서 추가 키워드 추출 (간단한 방법)
        import re
        additional_keywords = re.findall(r'\b[가-힣]+\b', query)
        keywords.extend([k.lower() for k in additional_keywords if len(k) > 1])
        
        for doc in documents:
            report_nm = doc.get("report_nm", "").lower()
            corp_name = doc.get("corp_name", "").lower()
            
            # 키워드 매칭 검사
            has_keyword = False
            
            # 제목과 기업명에서 키워드 매칭
            for keyword in keywords:
                if keyword in report_nm or keyword in corp_name:
                    has_keyword = True
                    break
            
            # extract_result에서도 키워드 찾기
            if not has_keyword:
                extract_result = doc.get("extract_result", {})
                if extract_result and isinstance(extract_result, dict):
                    extract_text = json.dumps(extract_result, ensure_ascii=False).lower()
                    for keyword in keywords:
                        if keyword in extract_text:
                            has_keyword = True
                            break
            
            # 키워드가 있으면 포함
            if has_keyword:
                filtered.append(doc)
        
        # 상위 N개 반환
        if not filtered:
            # 필터링된 것이 없으면 최소 3개는 반환
            return documents[:3] if documents else []
        
        return filtered[:10]  # 최대 10개까지만 반환
    
    def _calculate_basic_metrics(
        self, 
        documents: List[Dict[str, Any]], 
        expanded_query: Dict[str, Any]
    ) -> Dict[str, Any]:
        """기본 메트릭 계산"""
        metrics = {
            "companies": set(),
            "date_coverage": 0,
            "doc_type_match": 0
        }
        
        # 기업 추출
        for doc in documents:
            if doc.get("corp_name"):
                metrics["companies"].add(doc["corp_name"])
        
        # 날짜 커버리지 계산 (간단히)
        if documents and expanded_query.get("date_range"):
            # 문서가 있으면 기본 50% 커버리지
            metrics["date_coverage"] = 50 + min(len(documents) * 5, 50)
        else:
            metrics["date_coverage"] = 0
        
        # 문서유형 매칭 계산 (간단히)
        if documents:
            # 문서가 있으면 기본 60% 매칭
            metrics["doc_type_match"] = 60 + min(len(documents) * 4, 40)
        else:
            metrics["doc_type_match"] = 0
        
        return metrics
    
    def _simple_fallback(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        expanded_query: Dict[str, Any]
    ) -> SufficiencyResult:
        """간단한 폴백 충분성 검사"""
        doc_count = len(documents)
        
        # 단순 규칙: 3개 이상 문서면 충분
        is_sufficient = doc_count >= 3
        confidence = min(doc_count / 10, 1.0)  # 10개면 100% 신뢰도
        
        missing_aspects = []
        suggestions = []
        
        if doc_count < 3:
            missing_aspects.append(f"문서 수 부족 (현재: {doc_count}개)")
            suggestions.append("검색 기간을 확대하여 재검색")
        
        if not expanded_query.get("companies") and doc_count < 5:
            suggestions.append("특정 기업을 지정하여 검색")
        
        reason = f"{'충분한' if is_sufficient else '부족한'} 정보 ({doc_count}개 문서)"
        
        return SufficiencyResult(
            is_sufficient=is_sufficient,
            confidence=confidence,
            missing_aspects=missing_aspects,
            suggestions=suggestions,
            reason=reason
        )