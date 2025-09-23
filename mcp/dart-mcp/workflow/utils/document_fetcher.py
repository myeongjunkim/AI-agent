"""
문서 내용 가져오기 (개선된 버전)
DART API의 구조에 맞게 문서 상세정보를 가져오는 모듈
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Tuple
from utils.logging import get_logger
from utils.cache import cached, get_cache
from utils.content_cleaner import clean_content, clean_for_llm

logger = get_logger("document_fetcher_v2")

# 문서 유형별 상세 API 매핑
DETAILED_API_MAPPING = {
    # 정기보고서 (A로 시작)
    "A001": "periodic_report",  # 사업보고서
    "A002": "periodic_report",  # 반기보고서  
    "A003": "periodic_report",  # 분기보고서
    
    # 주요사항보고서 (B로 시작)
    "B001": "major_report",  # 주요사항보고서
    "B002": "major_report",  # 주요경영사항
    "B003": "major_report",  # 최대주주등과의거래
    
    # 증권신고서 (C로 시작)
    "C001": "securities_registration",  # 증권신고(지분증권)
    "C002": "securities_registration",  # 증권신고(채무증권)
    "C003": "securities_registration",  # 증권신고(파생결합증권)
    
    # 지분공시 (D로 시작)
    "D001": "ownership_disclosure",  # 대량보유상황보고서
    "D002": "ownership_disclosure",  # 임원주요주주보고서
    "D003": "ownership_disclosure",  # 의결권대리행사
    "D004": "ownership_disclosure",  # 공개매수
}


class DocumentFetcherV2:
    """DART 문서 내용 가져오기 (개선된 버전)"""
    
    def __init__(self, dart_api_tools):
        """
        Args:
            dart_api_tools: dart_api_tools 모듈
        """
        self.dart_api = dart_api_tools
        self.dart_reader = getattr(dart_api_tools, 'dart_reader', None)
        self.cache = get_cache()
        
    async def fetch_document_content(
        self,
        rcept_no: str,
        corp_code: str = None,
        report_type: str = None,
        fetch_mode: str = "auto",
        detailed_types: Dict[str, List[str]] = None
    ) -> Dict[str, Any]:
        """
        문서 내용 가져오기 (상세 API 우선, 실패시 원본)
        
        Args:
            rcept_no: 접수번호
            corp_code: 회사 고유번호 (상세 API 사용시 필요)
            report_type: 보고서 유형 코드 (ex: B001, A001)
            fetch_mode: 
                - "auto": 자동 선택 (상세 API 시도 후 원본)
                - "detailed": 상세 API만 사용
                - "original": 원본 문서만 사용
            detailed_types: 상세 문서 타입 딕셔너리 (major_events, securities, business_reports)
                
        Returns:
            문서 내용 딕셔너리
        """
        # 캐시 키 생성
        cache_params = {
            "rcept_no": rcept_no,
            "corp_code": corp_code,
            "report_type": report_type,
            "fetch_mode": fetch_mode
        }
        
        # 캐시 확인
        cached_result = await self.cache.get("fetch_document_content", cache_params)
        if cached_result is not None:
            logger.debug(f"Cache hit for document {rcept_no}")
            return cached_result
        
        try:
            logger.info(f"Fetching document {rcept_no} (mode: {fetch_mode}, type: {report_type}, corp: {corp_code})")
            
            result = {
                "rcept_no": rcept_no,
                "corp_code": corp_code,
                "report_type": report_type,
                "content": None,
                "structured_data": None,
                "source": None,
                "error": None
            }
            
            # 1. 문서 유형 확인 및 상세 API 사용 가능 여부 판단
            api_type = self._get_api_type(report_type)
            
            if fetch_mode in ["auto", "detailed"] and api_type and corp_code:
                # 2. 상세 API로 구조화된 데이터 가져오기
                print(corp_code, rcept_no, api_type, detailed_types)
                structured_data = await self._fetch_structured_data(
                    corp_code, rcept_no, api_type, detailed_types
                )
                
                if structured_data and isinstance(structured_data, dict) and not structured_data.get("error"):
                    result["structured_data"] = structured_data
                    result["content"] = self._extract_content_from_structured(structured_data)
                    result["source"] = "detailed_api"
                    logger.info(f"Successfully fetched structured data for {rcept_no}")
                    return result
                elif fetch_mode == "detailed":
                    # detailed 모드에서 실패시 에러 반환
                    error_msg = "Failed to fetch detailed data"
                    if structured_data and isinstance(structured_data, dict):
                        error_msg = structured_data.get("error", error_msg)
                    result["error"] = error_msg
                    return result
            
            # 3. 원본 문서 가져오기 (상세 API 실패 또는 미지원)
            if fetch_mode in ["auto", "original"]:
                original_content = await self._fetch_original_document(rcept_no)
                
                if original_content and not original_content.get("error"):
                    result["content"] = original_content.get("content")
                    result["source"] = "original_document"
                    logger.info(f"Successfully fetched original document for {rcept_no}")
                else:
                    result["error"] = original_content.get("error", "Failed to fetch original document")
            
            # 성공적으로 가져온 경우 캐시에 저장
            if result and not result.get("error"):
                await self.cache.set("fetch_document_content", cache_params, result)
                logger.debug(f"Cached document content for {rcept_no}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch document {rcept_no}: {e}")
            return {
                "rcept_no": rcept_no,
                "content": None,
                "error": str(e)
            }
    
    def _get_api_type(self, report_type: str) -> Optional[str]:
        """보고서 유형에서 API 타입 결정"""
        if not report_type:
            return None
            
        # 문서 코드의 첫 글자로 대략적인 유형 판단
        if report_type.startswith("A"):
            return "periodic_report"
        elif report_type.startswith("B"):
            return "major_report"
        elif report_type.startswith("C"):
            return "securities_registration"
        elif report_type.startswith("D"):
            return "ownership_disclosure"
        
        # 정확한 매핑 확인
        return DETAILED_API_MAPPING.get(report_type)
    
    async def _fetch_structured_data(
        self,
        corp_code: str,
        rcept_no: str,
        api_type: str,
        detailed_types: Dict[str, List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """구조화된 상세 데이터 가져오기"""
        # 캐시 키 생성
        cache_params = {
            "corp_code": corp_code,
            "rcept_no": rcept_no,
            "api_type": api_type
        }
        
        # 캐시 확인
        cached_result = await self.cache.get("_fetch_structured_data", cache_params)
        if cached_result is not None:
            return cached_result
        
        try:
            logger.info(f"[_fetch_structured_data] Fetching {api_type} for {corp_code} / {rcept_no}")
            
            # API 타입별 호출 - dart_api_tools의 공개 함수 사용
            data = {}
            year = self._extract_year_from_rcept_no(rcept_no)
            
            if api_type == "periodic_report":
                # 정기보고서는 사업보고서 타입으로 조회
                if detailed_types and detailed_types.get("business_reports"):
                    biz_reports = detailed_types.get("business_reports")
                    
                    # 상세 타입이 있으면 각각 조회
                    for biz_type in biz_reports:
                        if hasattr(self.dart_api, 'get_business_report_data'):
                            logger.info(f"[_fetch_structured_data] Calling get_business_report_data({corp_code}, {biz_type}, {year})")
                            biz_data = await self.dart_api.get_business_report_data(
                                company=corp_code,
                                business_report_type=biz_type,
                                year=year
                            )
                            
                            if biz_data:
                                parsed = json.loads(biz_data) if isinstance(biz_data, str) else biz_data
                                # rcept_no로 필터링이 필요한 경우
                                if isinstance(parsed, list):
                                    filtered = [item for item in parsed if 
                                              item.get("rcept_no") == rcept_no or 
                                              item.get("rcp_no") == rcept_no]
                                    if filtered:
                                        data[f"business_{biz_type}"] = filtered[0]
                                else:
                                    data[f"business_{biz_type}"] = parsed
                else:
                    # 기본 정기보고서 정보 가져오기
                    data = await self._fetch_periodic_report_details(corp_code, rcept_no)
                
            elif api_type == "major_report":
                # 주요사항보고서 - get_major_events 사용
                if detailed_types and detailed_types.get("major_events"):
                    major_events = detailed_types.get("major_events")
                    
                    for event_type in major_events:
                        if hasattr(self.dart_api, 'get_major_events'):
                            logger.info(f"[_fetch_structured_data] Calling get_major_events({corp_code}, {event_type}, {year})")
                            event_data = await self.dart_api.get_major_events(
                                company=corp_code,
                                event_type=event_type,
                                start_year=str(year)
                            )
                            
                            if event_data:
                                parsed = json.loads(event_data) if isinstance(event_data, str) else event_data
                                
                                # API 응답 내용 확인 (처음 100자만)
                                if isinstance(parsed, dict):
                                    if 'result' in parsed or 'status' in parsed:
                                        logger.warning(f"[_fetch_structured_data] API returned status/result: {parsed.get('result', parsed.get('status'))}")
                                
                                # rcept_no로 필터링
                                if isinstance(parsed, list):
                                    logger.info('qq')
                                    filtered = [item for item in parsed if 
                                              item.get("rcept_no") == rcept_no or 
                                              item.get("rcp_no") == rcept_no]
                                    if filtered:
                                        data[f"event_{event_type}"] = filtered[0]
                                        logger.info(f"[_fetch_structured_data] Found {len(filtered)} matching events for type {event_type}")
                                elif isinstance(parsed, dict) and (
                                    parsed.get("rcept_no") == rcept_no or 
                                    parsed.get("rcp_no") == rcept_no):
                                    data[f"event_{event_type}"] = parsed
                
            elif api_type == "securities_registration":
                # 증권신고서 - get_securities_report 사용
                if detailed_types and detailed_types.get("securities"):
                    for sec_type in detailed_types["securities"]:
                        if hasattr(self.dart_api, 'get_securities_report'):
                            sec_data = await self.dart_api.get_securities_report(
                                company=corp_code,
                                securities_type=sec_type,
                                start_year=str(year)
                            )
                            logger.info("[_fetch_structured_data] Calling get_securities_report")
                            if sec_data:
                                parsed = json.loads(sec_data) if isinstance(sec_data, str) else sec_data
                                # rcept_no로 필터링
                                if isinstance(parsed, list):
                                    filtered = [item for item in parsed if 
                                              item.get("rcept_no") == rcept_no or 
                                              item.get("rcp_no") == rcept_no]
                                    if filtered:
                                        logger.info(f"[_fetch_structured_data] Found {len(filtered)} matching securities for type {sec_type}")
                                        data[f"securities_{sec_type}"] = filtered[0]
                                elif isinstance(parsed, dict) and (
                                    parsed.get("rcept_no") == rcept_no or 
                                    parsed.get("rcp_no") == rcept_no):
                                    data[f"securities_{sec_type}"] = parsed
                
            elif api_type == "ownership_disclosure":
                # 지분공시 - get_major_shareholders 사용
                if hasattr(self.dart_api, 'get_major_shareholders'):
                    shareholders_data = await self.dart_api.get_major_shareholders(corp_code)
                    if shareholders_data:
                        parsed = json.loads(shareholders_data) if isinstance(shareholders_data, str) else shareholders_data
                        # rcept_no로 필터링
                        if isinstance(parsed, list):
                            filtered = [item for item in parsed if 
                                      item.get("rcept_no") == rcept_no or 
                                      item.get("rcp_no") == rcept_no]
                            if filtered:
                                data["major_shareholders"] = filtered[0]
                        else:
                            data["major_shareholders"] = parsed
            else:
                return None
            
            
            if not data:
                logger.info(f"[_fetch_structured_data] ⚠️ No data collected, returning None")
                return None
                
            # 성공적으로 가져온 경우 캐시에 저장
            if data and not data.get("error"):
                await self.cache.set("_fetch_structured_data", cache_params, data)
                logger.info(f"[_fetch_structured_data] ✅ Cached structured data for {rcept_no}, keys: {list(data.keys())}")
            else:
                logger.warning(f"[_fetch_structured_data] ⚠️ Data contains error, not caching")
                
            return data
            
        except Exception as e:
            logger.error(f"[_fetch_structured_data] 💥 Exception occurred: {type(e).__name__}: {e}")
            return {"error": str(e)}
    
    async def _fetch_periodic_report_details(self, corp_code: str, rcept_no: str) -> Dict[str, Any]:
        """정기보고서 상세 정보 가져오기"""
        result = {}
        
        try:
            # 재무제표 정보
            if hasattr(self.dart_api, 'get_financial_statements'):
                year = self._extract_year_from_rcept_no(rcept_no)
                if year:
                    fs_data = await self.dart_api.get_financial_statements(
                        company=corp_code,
                        year=year,
                        comprehensive=True
                    )
                    if fs_data:
                        result["financial_statements"] = json.loads(fs_data) if isinstance(fs_data, str) else fs_data
            
            # 배당 정보
            if hasattr(self.dart_api, 'get_business_report_data'):
                dividend_data = await self.dart_api.get_business_report_data(
                    company=corp_code,
                    business_report_type="배당",
                    year=self._extract_year_from_rcept_no(rcept_no)
                )
                if dividend_data:
                    result["dividend"] = json.loads(dividend_data) if isinstance(dividend_data, str) else dividend_data
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching periodic report details: {e}")
            return {"error": str(e)}
    
    
    
    
    async def _fetch_original_document(self, rcept_no: str) -> Dict[str, Any]:
        """원본 문서 가져오기 (실제 파일 다운로드)"""
        # 캐시 키 생성
        cache_params = {
            "rcept_no": rcept_no,
            "document_type": "original"
        }
        
        # 캐시 확인
        cached_result = await self.cache.get("_fetch_original_document", cache_params)
        if cached_result is not None:
            logger.debug(f"Cache hit for original document {rcept_no}")
            return cached_result
        
        try:
            # 1. 먼저 간단한 문서 정보 API 시도
            if hasattr(self.dart_api, 'get_document_content'):
                content_result = await self.dart_api.get_document_content(
                    rcp_no=rcept_no,  # 파라미터명 수정
                    get_all=False  # 요약본
                )
                
                if isinstance(content_result, str):
                    content_data = json.loads(content_result)
                else:
                    content_data = content_result
                
                # 내용이 충분히 있으면 반환 (실제 내용인지 확인)
                if "error" not in content_data and content_data.get("content"):
                    parsed_content = self._parse_document_content(content_data)
                    # OpenDartReader의 document()는 보통 URL이나 간단한 정보만 반환
                    # 실제 내용이 1000자 이상이어야 유효한 문서로 간주
                    if parsed_content and len(parsed_content) > 1000 and not parsed_content.startswith("http"):
                        # XML/HTML 태그 정리
                        cleaned_content = clean_content(parsed_content, preserve_structure=True)
                        logger.info(f"Using document API content ({len(cleaned_content)} chars after cleaning)")
                        result = {
                            "content": cleaned_content,
                            "raw_data": content_data,
                            "source": "document_api"
                        }
                        # 캐시에 저장
                        await self.cache.set("_fetch_original_document", cache_params, result)
                        return result
                    else:
                        logger.info(f"Document API content insufficient ({len(parsed_content) if parsed_content else 0} chars), will download")
            
            # 2. 실제 원본 파일 다운로드 시도
            logger.info(f"Attempting to download original file for {rcept_no}")
            
            # document_downloader 임포트
            from utils.document_downloader import download_dart_document
            import os
            
            api_key = os.getenv("DART_API_KEY")
            if api_key:
                download_result = await download_dart_document(rcept_no, api_key)
                
                if not download_result.get("error"):
                    # 다운로드 성공
                    content = download_result.get("main_text") or download_result.get("content")
                    if content:
                        # XML/HTML 태그 정리
                        cleaned_content = clean_content(content, preserve_structure=True)
                        logger.info(f"Successfully downloaded and extracted {len(cleaned_content)} characters after cleaning")
                        result = {
                            "content": cleaned_content,
                            "files": download_result.get("files", []),
                            "source": "downloaded_file"
                        }
                        # 캐시에 저장
                        await self.cache.set("_fetch_original_document", cache_params, result)
                        return result
                else:
                    logger.warning(f"Download failed: {download_result['error']}")
            
            # 3. 다운로드 실패시 URL만 제공
            download_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
            return {
                "content": None,
                "download_url": download_url,
                "message": "원본 문서는 다운로드 URL에서 확인 가능합니다",
                "source": "url_only"
            }
            
        except Exception as e:
            logger.error(f"Error fetching original document: {e}")
            return {"error": str(e)}
    
    def _extract_content_from_structured(self, structured_data: Dict[str, Any]) -> str:
        """구조화된 데이터에서 텍스트 내용 추출 (이미 매핑된 데이터 처리)"""
        content_parts = []
        
        # 데이터의 모든 키를 순회하면서 내용 추출
        for key, value in structured_data.items():
            if value and key != "error":
                # 키를 보기 좋게 포맷팅
                if key.startswith("business_"):
                    section_name = key.replace("business_", "사업보고서 - ")
                elif key.startswith("event_"):
                    section_name = key.replace("event_", "주요사항 - ")
                elif key.startswith("securities_"):
                    section_name = key.replace("securities_", "증권신고 - ")
                elif key == "financial_statements":
                    section_name = "재무제표"
                elif key == "dividend":
                    section_name = "배당 정보"
                elif key == "executives":
                    section_name = "임원 정보"
                elif key == "total_shares":
                    section_name = "주식총수"
                elif key == "major_shareholders":
                    section_name = "주요주주"
                else:
                    section_name = key
                
                content_parts.append(f"\n=== {section_name} ===")
                
                # 값의 타입에 따라 처리 (이미 매핑된 데이터)
                if isinstance(value, dict):
                    # 딕셔너리인 경우 키-값 쌍으로 출력
                    for sub_key, sub_value in value.items():
                        if sub_value and sub_key not in ["error", "status", "result", "message"]:
                            content_parts.append(f"  • {sub_key}: {str(sub_value)[:500]}")
                    
                elif isinstance(value, list):
                    # 리스트인 경우 각 항목 처리
                    for i, item in enumerate(value[:5], 1):  # 상위 5개만
                        if isinstance(item, dict):
                            content_parts.append(f"\n  [{i}번째 항목]")
                            # 주요 필드들 표시 (이미 한글로 변환된 상태)
                            important_fields = ['접수번호', '회사명', '보고서명', '접수일자', 
                                              '보고사유', '제출인', '비고', '주주명', '성명', '직위']
                            for field in important_fields:
                                if field in item and item[field]:
                                    content_parts.append(f"    • {field}: {item[field]}")
                            
                            # 중요 필드가 없으면 모든 필드 표시
                            if not any(field in item for field in important_fields):
                                for sub_key, sub_value in item.items():
                                    if sub_value and sub_key not in ["error", "status", "result", "message"]:
                                        content_parts.append(f"    • {sub_key}: {str(sub_value)[:300]}")
                        else:
                            content_parts.append(f"  [{i}] {str(item)[:500]}")
                else:
                    # 기타 타입
                    content_parts.append(str(value)[:1000])
        
        return "\n".join(content_parts) if content_parts else "구조화된 데이터 없음"
    
    def _parse_document_content(self, doc_data: Any) -> str:
        """문서 데이터 파싱 - XML/HTML 태그 제거 및 구조화"""
        content = ""
        
        if isinstance(doc_data, str):
            content = doc_data
        elif isinstance(doc_data, dict):
            # content 필드가 있으면 우선 사용
            if "content" in doc_data:
                content = str(doc_data["content"])
            # DataFrame 형태의 데이터
            elif "data" in doc_data:
                content = str(doc_data["data"])
            # 텍스트 필드들
            else:
                text_parts = []
                for key in ["text", "body", "document"]:
                    if key in doc_data:
                        text_parts.append(str(doc_data[key]))
                content = "\n".join(text_parts)
        else:
            content = str(doc_data)
        
        # XML 태그 제거 및 내용 추출
        if content and ("<?xml" in content or "<DOCUMENT" in content):
            import re
            
            # 주요 정보 추출을 위한 패턴
            patterns = {
                "회사명": r"<COMPANY-NAME[^>]*>([^<]+)</COMPANY-NAME>",
                "문서명": r"<DOCUMENT-NAME[^>]*>([^<]+)</DOCUMENT-NAME>",
                "대표이사": r"<REPRESENTATIVE[^>]*>([^<]+)</REPRESENTATIVE>",
                
                # 테이블 데이터 추출
                "항목명": r"<TH[^>]*>([^<]+)</TH>",
                "테이블내용": r"<TE[^>]*>([^<]+)</TE>",
                "테이블숫자": r"<TN[^>]*>([^<]+)</TN>",
                "단락": r"<P[^>]*>([^<]+)</P>",
            }
            
            result = []
            
            # 기본 정보 추출
            for label, pattern in patterns.items():
                matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                if matches:
                    # 공백 제거 및 정리
                    cleaned_matches = []
                    for match in matches:
                        cleaned = match.strip()
                        cleaned = re.sub(r'\s+', ' ', cleaned)
                        if cleaned and len(cleaned) > 1:  # 너무 짧은 내용 제외
                            cleaned_matches.append(cleaned)
                    
                    if cleaned_matches:
                        if label in ["회사명", "문서명", "대표이사"]:
                            # 메타 정보는 첫 번째만
                            result.append(f"【{label}】 {cleaned_matches[0]}")
                        else:
                            # 테이블 데이터는 구조화
                            result.append(f"\n【{label}】")
                            unique_items = list(set(cleaned_matches))[:30]  # 중복 제거 & 제한
                            for item in unique_items:
                                if len(item) > 100:  # 긴 텍스트는 단락으로
                                    result.append(f"\n{item}\n")
                                else:
                                    result.append(f"  • {item}")
            
            # 테이블 구조 파싱
            table_pattern = r"<TABLE[^>]*>(.*?)</TABLE>"
            tables = re.findall(table_pattern, content, re.IGNORECASE | re.DOTALL)
            
            if tables:
                result.append("\n【테이블 데이터】")
                for i, table in enumerate(tables[:5], 1):  # 최대 5개 테이블
                    rows = re.findall(r"<TR[^>]*>(.*?)</TR>", table, re.IGNORECASE | re.DOTALL)
                    if rows:
                        result.append(f"\n[표 {i}]")
                        for row in rows[:10]:  # 각 테이블당 최대 10행
                            cells = re.findall(r"<T[DHE][^>]*>([^<]+)</T[DHE]>", row, re.IGNORECASE)
                            if cells:
                                cleaned_cells = [re.sub(r'\s+', ' ', cell.strip()) for cell in cells]
                                cleaned_cells = [c for c in cleaned_cells if c]  # 빈 셀 제거
                                if cleaned_cells:
                                    result.append("  " + " | ".join(cleaned_cells))
            
            # 전체 텍스트 추출 (태그 제거)
            clean_text = re.sub(r'<[^>]+>', ' ', content)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
            if result:
                final_result = "\n".join(result)
                # 너무 짧으면 clean text 추가
                if len(final_result) < 800 and clean_text:
                    final_result += f"\n\n【추가 텍스트】\n{clean_text[:2000]}"
                return final_result
            else:
                return clean_text[:5000]
        
        # XML이 아닌 경우 그대로 반환
        return content[:5000] if len(content) > 5000 else content
    
    def _extract_year_from_rcept_no(self, rcept_no: str) -> Optional[int]:
        """접수번호에서 연도 추출"""
        try:
            # rcept_no 형식: YYYYMMDD...
            if len(rcept_no) >= 4:
                year = int(rcept_no[:4])
                if 2000 <= year <= 2030:
                    return year
        except:
            pass
        return None
    
    async def fetch_multiple_documents(
        self,
        documents: List[Dict[str, Any]],
        max_concurrent: int = 3,
        detailed_types: Dict[str, List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        여러 문서 동시 가져오기 (검색 결과 기반)
        
        Args:
            documents: 검색 결과 문서 리스트 (rcept_no, corp_code, report_type 포함)
            max_concurrent: 동시 처리 수
            detailed_types: 상세 문서 타입 딕셔너리
            
        Returns:
            문서 내용 리스트
        """
        results = []
        
        # 배치 처리
        for i in range(0, len(documents), max_concurrent):
            batch = documents[i:i + max_concurrent]
            
            # 동시 처리
            tasks = []
            for doc in batch:
                rcept_no = doc.get("rcept_no") or doc.get("rcp_no")
                corp_code = doc.get("corp_code")
                # orchestrator에서 전달된 report_type 우선 사용, 없으면 추론
                report_type = doc.get("report_type") or self._infer_report_type(doc)
                
                tasks.append(
                    self.fetch_document_content(
                        rcept_no=rcept_no,
                        corp_code=corp_code,
                        report_type=report_type,
                        fetch_mode="auto",  # auto로 변경하여 실패시 원본 문서로 폴백
                        detailed_types=detailed_types
                    )
                )
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for doc, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to fetch {doc.get('rcept_no')}: {result}")
                    results.append({
                        "rcept_no": doc.get("rcept_no"),
                        "content": None,
                        "error": str(result)
                    })
                else:
                    # 원본 문서 정보와 병합
                    result.update({
                        "corp_name": doc.get("corp_name"),
                        "report_nm": doc.get("report_nm"),
                        "rcept_dt": doc.get("rcept_dt")
                    })
                    results.append(result)
        
        return results
    
    def _infer_report_type(self, doc: Dict[str, Any]) -> Optional[str]:
        """문서 정보에서 보고서 유형 추론"""
        report_nm = doc.get("report_nm", "").lower()
        
        # 정기보고서
        if "사업보고서" in report_nm:
            return "A001"
        elif "반기보고서" in report_nm:
            return "A002"
        elif "분기보고서" in report_nm:
            return "A003"
        
        # 주요사항보고서
        elif "주요사항" in report_nm:
            return "B001"
        elif "주요경영" in report_nm:
            return "B002"
        
        # 지분공시
        elif "대량보유" in report_nm or "5%" in report_nm:
            return "D001"
        elif "임원" in report_nm and "주주" in report_nm:
            return "D002"
        
        # 증권신고서
        elif "증권신고" in report_nm:
            if "지분" in report_nm:
                return "C001"
            elif "채무" in report_nm or "채권" in report_nm:
                return "C002"
            elif "파생" in report_nm:
                return "C003"
        
        return None