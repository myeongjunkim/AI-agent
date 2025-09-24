"""
DART 문서 필터링 유틸리티
검색 결과에서 사용자 질의와 관련된 문서만 선별
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from utils.logging import get_logger

logger = get_logger("document_filter")


class DocumentFilter:
    """DART 문서 필터링 클래스"""
    
    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: OpenAI 클라이언트 (선택적)
        """
        self.llm_client = llm_client
        self.prompt_template = self._load_prompt_template()
    
    async def filter_documents(
        self,
        query: str,
        search_results: List[Dict[str, Any]],
        expanded_query: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        검색 결과 필터링 - 사용자 질의와 관련된 문서만 선별
        
        Args:
            query: 원본 사용자 질의
            search_results: 검색된 모든 문서들
            expanded_query: 확장된 쿼리 정보
            
        Returns:
            처리가 필요한 관련 문서들만 필터링된 리스트
        """
        if not search_results:
            return []
        
        # LLM 기반 필터링 사용 가능한 경우
        if self.llm_client:
            return await self._llm_based_filtering(query, search_results, expanded_query)
        else:
            # 간단한 규칙 기반 필터링
            return self._rule_based_filtering(query, search_results, expanded_query)
    
    def _load_prompt_template(self) -> Optional[str]:
        """문서 필터링 프롬프트 템플릿 로드"""
        try:
            # workflow 디렉토리에서 상대 경로로 찾기 (workflow/utils에서 실행됨)
            prompt_path = Path("prompts/document_filter.txt")
            if prompt_path.exists():
                with open(prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            else:
                logger.debug(f"Filter prompt template not found: {prompt_path}, using default")
        except Exception as e:
            logger.error(f"Failed to load filter prompt template: {e}")
        return None
    
    def _parse_filter_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """LLM 응답을 파싱하여 결과 추출"""
        try:
            # 1. 표준 JSON 파싱 시도
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            # 2. 코드 블록 안의 JSON 파싱 시도
            code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response_text)
            if code_block_match:
                try:
                    return json.loads(code_block_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # 3. relevant_indices 패턴 직접 추출
            indices_match = re.search(r'relevant_indices["\s]*:[\s]*\[([^\]]*)\]', response_text)
            if indices_match:
                try:
                    indices_str = indices_match.group(1)
                    indices = [int(x.strip()) for x in indices_str.split(',') if x.strip().isdigit()]
                    
                    # reason 패턴도 찾기
                    reason_match = re.search(r'reason["\s]*:[\s]*["\']([^"\']*)["\']', response_text)
                    reason = reason_match.group(1) if reason_match else "자동 추출됨"
                    
                    return {
                        "relevant_indices": indices,
                        "reason": reason
                    }
                except (ValueError, AttributeError):
                    pass
            
            # 4. 숫자만 추출하여 인덱스로 사용
            numbers = re.findall(r'\b(\d+)\b', response_text)
            if numbers:
                indices = [int(x) for x in numbers[:10]]  # 최대 10개만 
                return {
                    "relevant_indices": indices,
                    "reason": "응답에서 숫자 패턴 추출"
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing filter response: {e}")
            return None
    
    async def _llm_based_filtering(
        self,
        query: str,
        search_results: List[Dict[str, Any]],
        expanded_query: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """LLM 기반 문서 필터링"""
        try:
            filtered_docs = []
            batch_size = 100  # 배치 처리를 위한 크기
            max_to_filter = min(100, len(search_results))  # 최대 100개만 필터링
            
            for i in range(0, min(max_to_filter, len(search_results)), batch_size):
                batch = search_results[i:i+batch_size]
                
                # 배치 문서 정보 준비
                doc_summaries = []
                for doc in batch:
                    summary = {
                        "index": i + batch.index(doc),
                        "report_nm": doc.get("report_nm", ""),
                        "corp_name": doc.get("corp_name", ""),
                        "rcept_dt": doc.get("rcept_dt", ""),
                    }
                    doc_summaries.append(summary)
                
                # 프롬프트 생성
                if self.prompt_template:
                    prompt = self.prompt_template.format(
                        query=query,
                        expanded_query=json.dumps(expanded_query, ensure_ascii=False, indent=2),
                        doc_summaries=json.dumps(doc_summaries, ensure_ascii=False, indent=2)
                    )
                else:
                    # 기본 프롬프트 (fallback)
                    prompt = f"""
                    사용자 질의: {query}
                    
                    다음 공시 문서들 중 사용자 질의에 답변하기 위해 실제로 처리가 필요한 문서만 선별해주세요.
                    
                    문서 목록:
                    {json.dumps(doc_summaries, ensure_ascii=False, indent=2)}
                    
                    다음 기준으로 평가해주세요:
                    1. report_nm(공시 제목)과 사용자 질의의 관련성
                    2. 최신성과 중요도
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
                
                # 응답 파싱 - 더 견고한 파싱 로직
                response_text = response.choices[0].message.content
                logger.debug(f"LLM filter response: {response_text[:500]}...")  # 응답 로깅
                
                parsed_result = self._parse_filter_response(response_text)
                
                if parsed_result:
                    relevant_indices = parsed_result.get("relevant_indices", [])
                    
                    # 선별된 문서 추가
                    for idx in relevant_indices:
                        if 0 <= idx < len(batch):
                            filtered_docs.append(batch[idx])
                    
                    logger.info(f"Batch filtering: {len(relevant_indices)}/{len(batch)} documents selected. "
                               f"Reason: {parsed_result.get('reason', 'N/A')}")
                else:
                    # 파싱 실패시 상위 문서 포함
                    logger.warning(f"Failed to parse filter response: {response_text[:200]}...")
                    logger.warning("Including top documents as fallback")
                    filtered_docs.extend(batch[:5])
            
            # 필터링 결과가 없으면 상위 N개 반환
            if not filtered_docs and search_results:
                logger.warning("No documents passed filtering, returning top 5")
                return search_results[:5]
            
            return filtered_docs
            
        except Exception as e:
            logger.error(f"LLM filtering error: {e}")
            return self._rule_based_filtering(query, search_results, expanded_query)
    
    def _rule_based_filtering(
        self,
        query: str,
        search_results: List[Dict[str, Any]],
        expanded_query: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """규칙 기반 문서 필터링"""
        _ = query, expanded_query  # 미사용 변수 표시
        # 상위 30개 문서 반환
        return search_results[:30]