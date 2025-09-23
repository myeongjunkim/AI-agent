"""
DART 심층 검색 오케스트레이터
사용자 쿼리를 처리하여 DART 공시를 심층 검색하고 종합적인 답변을 생성
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from workflow.utils.query_expander import QueryExpander
from workflow.utils.sufficiency_checker import SufficiencyChecker
from workflow.utils.synthesizer import DartSynthesizer
from workflow.utils.document_fetcher import DocumentFetcherV2
from workflow.utils.document_filter import DocumentFilter
from utils.logging import get_logger
from utils.cache import get_cache
from utils.config_loader import get_config, get_openai_client

# Logger 초기화
logger = get_logger("dart_orchestrator")


class DartOrchestrator:
    """DART 심층 검색 파이프라인"""
    
    def __init__(self, dart_api_tools):
        """
        Args:
            dart_api_tools: dart_api_tools 모듈 (동적 임포트)
        """
        self.dart_api = dart_api_tools
        self.dart_reader = getattr(dart_api_tools, 'dart_reader', None)
        self.query_expander = QueryExpander(self.dart_reader)
        
        # LLM 클라이언트 초기화 (선택적)
        self.llm_client = get_openai_client()
        
        # LLM 클라이언트를 충분성 검사기와 합성기에 전달
        self.sufficiency_checker = SufficiencyChecker(self.llm_client)
        self.synthesizer = DartSynthesizer(self.llm_client)
        
        # 문서 가져오기 모듈 (개선된 버전)
        self.document_fetcher = DocumentFetcherV2(dart_api_tools)
        
        # 문서 필터링 모듈
        self.document_filter = DocumentFilter(self.llm_client)
        
        # 캐시 초기화
        self.cache = get_cache()
        self.config = get_config()
        
    async def search_pipeline(
        self,
        query: str,
        max_attempts: int = 3,
        max_results_per_search: int = 30
    ) -> str:
        """
        DART 심층 검색 파이프라인 실행
        
        Args:
            query: 사용자 쿼리
            max_attempts: 최대 검색 시도 횟수
            max_results_per_search: 검색당 최대 결과 수
            
        Returns:
            JSON 형식의 검색 결과
        """
        logger.info(f"Starting DART search pipeline for query: {query}")
        
        try:
            # 1. Query Expansion Phase
            logger.info("Phase 1: Query Expansion")
            expanded_query = await self.query_expander.expand_query(query)
            logger.info(f"Expanded query: {self.query_expander.format_result(expanded_query)}")
            
            # 기업명 확인이 필요한 경우 처리
            if expanded_query.get("needs_confirmation"):
                confirmation_result = self._handle_company_confirmation(expanded_query)
                if confirmation_result["status"] == "needs_user_input":
                    return json.dumps(confirmation_result, ensure_ascii=False, indent=2)
                # 사용자가 선택한 기업으로 업데이트
                expanded_query = confirmation_result["updated_query"]
            
            # 유의미한 Params 가 없는 경우 처리
            if expanded_query.get("companies") == [] and expanded_query.get("corp_codes") == [] and expanded_query.get("doc_types") == []:
                response = {
                    "query": query,
                    "answer": "Dart 공시 관련 답변이 필요하시군요. '삼성전자', '영업이익 공시', '유상증자' 와 같이 구체적인 기업명이나 공시 관련 용어로 다시 검색해 주시면 더 정확한 결과를 얻으실 수 있습니다.",
                    "summary": {
                        "total_documents": 0,
                        "date_range": "",
                        "companies": [],
                        "confidence": 0.0
                    },
                    "documents": [],
                    "metadata": {
                        "synthesized_at": datetime.now().isoformat(),
                        "sufficiency": False
                    }
                }
                return json.dumps(response, ensure_ascii=False, indent=2)

            # 2. Search Phase
            logger.info("Phase 2: Search Execution")
            search_results = await self._execute_searches(expanded_query, max_results_per_search)
            
            if not search_results:
                logger.warning("No search results found")
                return json.dumps({
                    "status": "no_results",
                    "query": query,
                    "message": "검색 결과가 없습니다.",
                    "expanded_query": expanded_query
                }, ensure_ascii=False)
            
            logger.info(f"Found {len(search_results)} total results")
            
            # 3. Document Filtering Phase
            logger.info("Phase 3: Document Filtering")
            filtered_results = await self.document_filter.filter_documents(query, search_results, expanded_query)
            logger.info(f"Filtered to {len(filtered_results)} relevant documents from {len(search_results)}")
            
            # 4. Document Processing Phase
            logger.info("Phase 4: Document Processing")
            processed_docs = await self._process_documents(filtered_results, expanded_query)
            
            # 5. Synthesis Phase (주석 처리됨 - 테스트용)
            # logger.info("Phase 5: Synthesis")
            # synthesis_result = await self.synthesizer.synthesize(
            #     query,
            #     processed_docs,
            #     expanded_query,
            #     {
            #         "total_searched": len(search_results),
            #         "total_filtered": len(filtered_results),
            #         "total_processed": len(processed_docs)
            #     }
            # )
            
            # 캐시 통계 로깅
            cache_stats = self.cache.get_stats()
            logger.info(f"Cache stats: {cache_stats}")
            
            # 테스트용: processed_docs 직접 반환
            test_result = {
                "status": "success",
                "query": query,
                "total_searched": len(search_results),
                "total_filtered": len(filtered_results),
                "total_processed": len(processed_docs),
                "processed_docs": processed_docs
            }
            return json.dumps(test_result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"Pipeline error: {str(e)}")
            return json.dumps({
                "status": "error",
                "query": query,
                "error": str(e)
            }, ensure_ascii=False)
    
    async def _execute_searches(
        self,
        expanded_query: Dict[str, Any],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """
        확장된 쿼리를 기반으로 DART 검색 실행
        
        Args:
            expanded_query: 확장된 쿼리 정보
            max_results: 최대 결과 수
            
        Returns:
            검색 결과 리스트
        """
        all_results = []
        search_params_list = self.query_expander.create_search_params(expanded_query)
        
        # 기업코드 없는 경우 롤링 검색 알림
        if len(search_params_list) > 1 and not expanded_query.get("corp_codes"):
            logger.info(f"🔄 기업명 없는 검색: {len(search_params_list)}개 기간으로 분할 (3개월씩 롤링)")
            for i, params in enumerate(search_params_list, 1):
                start = params.get('bgn_de', '')
                end = params.get('end_de', '')
                if start and end:
                    start_fmt = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
                    end_fmt = f"{end[:4]}-{end[4:6]}-{end[6:8]}"
                    logger.info(f"  📅 구간 {i}: {start_fmt} ~ {end_fmt}")
        
        # 병렬 검색 실행
        if len(search_params_list) > 1 and expanded_query.get("search_strategy", {}).get("parallel_search"):
            logger.info(f"Executing {len(search_params_list)} parallel searches")
            
            tasks = []
            for params in search_params_list:
                tasks.append(self._search_disclosures(params))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if not isinstance(result, Exception):
                    all_results.extend(result)
        else:
            # 순차 검색
            for i, params in enumerate(search_params_list, 1):
                period_info = f"[{i}/{len(search_params_list)}]" if len(search_params_list) > 1 else ""
                logger.info(f"Executing search {period_info}: {params.get('bgn_de', 'N/A')} ~ {params.get('end_de', 'N/A')}")
                logger.info(f"  → Search params: {params}")  # 전체 파라미터 로깅
                results = await self._search_disclosures(params)
                all_results.extend(results)
                
                logger.info(f"  → {len(results)}건 검색, 누적 {len(all_results)}건")
                
                # 충분한 결과가 있으면 중단
                if len(all_results) >= max_results:
                    logger.info(f"충분한 결과 수집 ({len(all_results)}건), 검색 중단")
                    break
        
        # 중복 제거 및 정렬
        logger.info(f"Before deduplication: {len(all_results)} results")
        unique_results = self._deduplicate_results(all_results)
        logger.info(f"After deduplication: {len(unique_results)} results")
        
        # 결과 수 제한
        return unique_results[:max_results]
    
    async def _search_disclosures(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        DART 공시 검색 실행 (캐싱 적용)
        
        Args:
            params: 검색 파라미터
            
        Returns:
            검색 결과 리스트
        """
        # 캐시 키 생성용 파라미터
        cache_params = {
            "company": params.get("corp_code"),
            "start_date": self._format_date_for_api(params.get("bgn_de")),
            "end_date": self._format_date_for_api(params.get("end_de")),
            "pblntf_detail_ty": params.get("pblntf_detail_ty")  # 상세유형 그대로 사용
        }
        
        # Phase 2 Search Execution - 파라미터 로깅 (Phase 1에서 선택한 문서 유형 확인)
        logger.info(f"Phase 2 Search Execution - cache_params: {cache_params}")
        logger.info(f"  → pblntf_detail_ty (문서유형): {params.get('pblntf_detail_ty', 'None')}")
        
        # 캐시 확인
        cached_result = await self.cache.get("search_company_disclosures", cache_params)
        if cached_result is not None:
            logger.debug(f"Cache hit for search params: {cache_params}")
            return cached_result
        
        try:
            # dart_api_tools의 search_company_disclosures 함수 호출
            result_json = await self.dart_api.search_company_disclosures(
                **cache_params
            )
            
            # JSON 파싱
            if isinstance(result_json, str):
                result_data = json.loads(result_json)
            else:
                result_data = result_json
            
            # 에러 체크
            if "error" in result_data:
                logger.error(f"Search error: {result_data['error']}")
                return []
            
            # 결과 추출
            results = []
            if isinstance(result_data, list):
                results = result_data
            elif isinstance(result_data, dict) and "result" in result_data:
                if result_data["result"] == "데이터가 없습니다.":
                    results = []
                else:
                    results = result_data.get("list", [])
            
            # 캐시에 저장
            if results:
                await self.cache.set("search_company_disclosures", cache_params, results)
                logger.debug(f"Cached {len(results)} search results")
            
            return results
            
        except Exception as e:
            logger.error(f"Search execution error: {str(e)}")
            return []
    
    def _format_date_for_api(self, date_str: Optional[str]) -> Optional[str]:
        """YYYYMMDD를 YYYY-MM-DD 형식으로 변환"""
        if not date_str or len(date_str) != 8:
            return None
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    
    def _extract_kind_from_detail_type(self, detail_type: Optional[str]) -> Optional[str]:
        """상세유형에서 공시종류 추출"""
        if not detail_type:
            return None
            
        # 첫 글자가 공시종류를 나타냄
        first_chars = set()
        for dtype in detail_type.split(","):
            if dtype:
                first_chars.add(dtype[0])
        
        # 단일 종류만 있으면 반환
        if len(first_chars) == 1:
            return list(first_chars)[0]
            
        return None
    
    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """중복 결과 제거"""
        seen = set()
        unique = []
        
        for result in results:
            # rcept_no를 기준으로 중복 체크
            key = result.get("rcept_no") or result.get("rcp_no")
            if key:
                if key not in seen:
                    seen.add(key)
                    unique.append(result)
            else:
                # 접수번호가 없는 경우 디버깅용 로그
                logger.warning(f"No rcept_no found in result: {list(result.keys())}")
                # 접수번호가 없어도 결과에 포함 (다른 고유 식별자 시도)
                backup_key = f"{result.get('corp_name', '')}-{result.get('report_nm', '')}-{result.get('rcept_dt', '')}"
                if backup_key not in seen:
                    seen.add(backup_key)
                    unique.append(result)
        
        # 날짜순 정렬 (최신순)
        unique.sort(key=lambda x: x.get("rcept_dt", ""), reverse=True)
        
        return unique
    
    async def _process_documents(
        self,
        filtered_results: List[Dict[str, Any]],
        expanded_query: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        필터링된 문서 처리 및 내용 가져오기
        
        Args:
            filtered_results: 필터링된 검색 결과
            expanded_query: 확장된 쿼리 (pblntf_detail_ty 정보 포함)
            
        Returns:
            처리된 문서 리스트 (내용 포함)
        """
        if not filtered_results:
            return []
        
        report_type = expanded_query.get("doc_types")[0]['code']
        
        processed = []
        
        # 1. 기본 정보 처리 (이미 필터링되고 정렬된 문서들)
        for idx, result in enumerate(filtered_results):
            rcept_no = result.get("rcept_no") or result.get("rcp_no")

            doc_info = {
                "index": idx + 1,
                "rcept_no": rcept_no,
                "corp_name": result.get("corp_name"),
                "report_nm": result.get("report_nm"),
                "rcept_dt": result.get("rcept_dt"),
                "flr_nm": result.get("flr_nm"),  # 제출인
                "summary": self._extract_summary(result),
                "content": None,  # 나중에 채울 예정
                "key_info": {},
                "report_type": report_type,  # expanded_query에서 가져옴
            }
            
            processed.append(doc_info)
        
        # 2. 필터링된 문서의 실제 내용 가져오기
        docs_to_fetch = processed  # 이미 필터링된 문서만 처리
        
        if docs_to_fetch:
            logger.info(f"Fetching content for top {len(docs_to_fetch)} documents")
            
            # 각 문서에 corp_code 추가 (company_validator 사용)
            for doc in docs_to_fetch:
                if doc.get("corp_name") and not doc.get("corp_code"):
                    # 회사명으로 corp_code 조회 (query_expander의 company_validator 활용)
                    validation = self.query_expander.company_validator.find_company(doc["corp_name"])
                    if validation["status"] in ["exact", "fuzzy"] and validation.get("corp_code"):
                        doc["corp_code"] = validation["corp_code"]
            
            # 개선된 문서 내용 가져오기 (상세 타입 전달)
            detailed_types = expanded_query.get("detailed_types", {})
            fetched_contents = await self.document_fetcher.fetch_multiple_documents(
                docs_to_fetch,
                max_concurrent=3,
                detailed_types=detailed_types
            )
            
            # 가져온 내용을 문서 정보에 병합
            for i, fetched in enumerate(fetched_contents):
                if i < len(processed):
                    doc = processed[i]
                    
                    # fetched에서 가져온 모든 필드를 doc에 병합
                    # 기존 doc의 필드를 유지하면서 fetched의 새 필드 추가
                    for key, value in fetched.items():
                        if value is not None:  # None이 아닌 값만 업데이트
                            doc[key] = value
                    
                    if fetched.get("error"):
                        logger.warning(f"Error fetching content for {doc.get('rcept_no')}: {fetched['error']}")
        
        return processed
    
    
    def _extract_summary(self, result: Dict[str, Any]) -> str:
        """문서 요약 추출"""
        parts = []
        
        if result.get("report_nm"):
            parts.append(result["report_nm"])
            
        if result.get("rm"):  # 비고
            parts.append(f"비고: {result['rm']}")
            
        return " | ".join(parts) if parts else "요약 없음"
    
    async def _synthesize_response(
        self,
        query: str,
        processed_docs: List[Dict[str, Any]],
        expanded_query: Dict[str, Any]
    ) -> str:
        """
        최종 응답 생성
        
        Args:
            query: 원본 쿼리
            processed_docs: 처리된 문서
            expanded_query: 확장된 쿼리
            
        Returns:
            JSON 형식의 최종 응답
        """
        # 주요 문서 선택 (상위 10개)
        top_docs = processed_docs[:10]
        
        # 통계 정보 생성
        stats = {
            "total_results": len(processed_docs),
            "companies": list(set(doc["corp_name"] for doc in processed_docs if doc.get("corp_name"))),
            "date_range": {
                "earliest": min((doc["rcept_dt"] for doc in processed_docs if doc.get("rcept_dt")), default=""),
                "latest": max((doc["rcept_dt"] for doc in processed_docs if doc.get("rcept_dt")), default="")
            },
            "report_types": {}
        }
        
        # 보고서 유형별 집계
        for doc in processed_docs:
            report_type = doc.get("report_nm", "기타")
            stats["report_types"][report_type] = stats["report_types"].get(report_type, 0) + 1
        
        # 응답 구성
        response = {
            "status": "success",
            "query": query,
            "expanded_query": {
                "companies": expanded_query["companies"],
                "date_range": expanded_query["date_range"],
                "doc_types": expanded_query["doc_types"][:3],
                "keywords": expanded_query["keywords"][:5]
            },
            "statistics": stats,
            "top_results": top_docs,
            "summary": self._generate_summary(query, top_docs, stats),
            "timestamp": datetime.now().isoformat()
        }
        
        return json.dumps(response, ensure_ascii=False, indent=2)
    
    def _handle_company_confirmation(self, expanded_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        기업명 확인이 필요한 경우 처리
        
        Args:
            expanded_query: 확장된 쿼리 정보
            
        Returns:
            확인 결과 또는 사용자 입력 요청
        """
        validation_info = expanded_query.get("company_validation", {})
        validation_results = validation_info.get("validation_results", [])
        
        # 확인이 필요한 기업들 수집
        ambiguous_companies = []
        for i, result in enumerate(validation_results):
            if result["needs_confirmation"]:
                original_query = validation_info["original_queries"][i]
                ambiguous_companies.append({
                    "original_query": original_query,
                    "candidates": result["candidates"],
                    "status": result["status"]
                })
        
        if ambiguous_companies:
            # 사용자에게 확인 요청
            logger.info(f"Found {len(ambiguous_companies)} ambiguous company names")
            
            response = {
                "status": "needs_user_input",
                "type": "company_confirmation",
                "query": expanded_query["original_query"],
                "message": "입력하신 기업명을 확인해주세요.",
                "ambiguous_companies": ambiguous_companies,
                "instructions": "각 기업에 대해 정확한 기업명을 선택하거나, 원하는 기업이 없으면 '제외'를 선택해주세요."
            }
            
            # 후보 기업 정보 포함
            for item in ambiguous_companies:
                logger.info(f"  '{item['original_query']}' 후보:")
                for candidate in item["candidates"][:3]:
                    if 'score' in candidate:
                        logger.info(f"    - {candidate.get('name', candidate.get('corp_name', 'Unknown'))} (점수: {candidate['score']})")
                    else:
                        logger.info(f"    - {candidate.get('corp_name', 'Unknown')} (유사도: {candidate.get('similarity', 0):.2f})")
            
            return response
        
        # 확인 불필요 - 원래 쿼리 반환
        return {
            "status": "confirmed",
            "updated_query": expanded_query
        }
    
    def _generate_summary(
        self,
        query: str,
        top_docs: List[Dict[str, Any]],
        stats: Dict[str, Any]
    ) -> str:
        """검색 결과 요약 생성"""
        lines = []
        
        # 쿼리 정보 추가
        if query:
            lines.append(f"검색어: {query}")
        
        # 전체 결과 요약
        lines.append(f"총 {stats['total_results']}건의 공시를 찾았습니다.")
        
        # 기업별 요약
        if stats["companies"]:
            companies_str = ", ".join(stats["companies"][:5])
            lines.append(f"관련 기업: {companies_str}")
        
        # 기간 요약
        if stats["date_range"]["earliest"] and stats["date_range"]["latest"]:
            lines.append(f"공시 기간: {stats['date_range']['earliest']} ~ {stats['date_range']['latest']}")
        
        # 주요 보고서 유형
        if stats["report_types"]:
            top_types = sorted(stats["report_types"].items(), key=lambda x: x[1], reverse=True)[:3]
            types_str = ", ".join([f"{t[0]}({t[1]}건)" for t in top_types])
            lines.append(f"주요 공시: {types_str}")
        
        # 최신 공시 하이라이트
        if top_docs:
            lines.append("\n최근 주요 공시:")
            for doc in top_docs[:3]:
                lines.append(f"- [{doc['corp_name']}] {doc['report_nm']} ({doc['rcept_dt']})")
        
        return "\n".join(lines)
    
    def _map_detail_type_to_report_type(self, pblntf_detail_ty: str, report_nm: str) -> Optional[str]:
        """pblntf_detail_ty와 report_nm을 기반으로 report_type 매핑"""
        if not pblntf_detail_ty:
            # pblntf_detail_ty가 없으면 report_nm에서 추론
            return self.document_fetcher._infer_report_type({"report_nm": report_nm})
        
        # pblntf_detail_ty의 첫 글자로 대분류 판단
        if pblntf_detail_ty.startswith("A"):
            # 정기보고서
            if "사업보고서" in report_nm:
                return "A001"
            elif "반기보고서" in report_nm:
                return "A002"
            elif "분기보고서" in report_nm:
                return "A003"
            else:
                return "A001"  # 기본값
        elif pblntf_detail_ty.startswith("B"):
            # 주요사항보고서
            if "주요경영" in report_nm:
                return "B002"
            elif "최대주주" in report_nm:
                return "B003"
            else:
                return "B001"  # 기본값
        elif pblntf_detail_ty.startswith("C"):
            # 증권신고서
            if "채무" in report_nm or "채권" in report_nm:
                return "C002"
            elif "파생" in report_nm:
                return "C003"
            else:
                return "C001"  # 기본값
        elif pblntf_detail_ty.startswith("D"):
            # 지분공시
            if "임원" in report_nm and "주주" in report_nm:
                return "D002"
            elif "의결권" in report_nm:
                return "D003"
            elif "공개매수" in report_nm:
                return "D004"
            else:
                return "D001"  # 기본값
        
        # 기본적으로는 document_fetcher의 추론 로직 사용
        return self.document_fetcher._infer_report_type({"report_nm": report_nm})


async def dart_research_pipeline(query: str, dart_api_tools=None) -> str:
    """
    DART 심층 검색 파이프라인 실행 (외부 호출용)
    
    Args:
        query: 사용자 쿼리
        dart_api_tools: dart_api_tools 모듈
        
    Returns:
        JSON 형식의 검색 결과
    """
    if dart_api_tools is None:
        # 동적 임포트
        try:
            from tools import dart_api_tools
        except ImportError:
            return json.dumps({
                "status": "error",
                "error": "dart_api_tools module not found"
            }, ensure_ascii=False)
    
    orchestrator = DartOrchestrator(dart_api_tools)
    return await orchestrator.search_pipeline(query)