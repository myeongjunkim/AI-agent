"""
쿼리 확장기
LangExtract/vLLM → 검증 → 파라미터 반환의 명확한 흐름
"""

from typing import Dict, List, Any
from datetime import datetime

from utils.date_parser import extract_date_range_from_query
from utils.company_validator import CompanyValidator
from workflow.utils.doc_type_mapper import DocTypeMapper
from workflow.utils.query_parser_langextract import QueryParserLangExtract
from utils.config_loader import get_openai_client

# 주요사항보고서 이벤트 타입
MAJOR_EVENT_TYPES = [
    '부도발생', '영업정지', '회생절차', '해산사유', '유상증자', '무상증자', '유무상증자', 
    '감자', '관리절차개시', '소송', '해외상장결정', '해외상장폐지결정', '해외상장', 
    '해외상장폐지', '전환사채발행', '신주인수권부사채발행', '교환사채발행', '관리절차중단', 
    '조건부자본증권발행', '자산양수도', '타법인증권양도', '유형자산양도', '유형자산양수', 
    '타법인증권양수', '영업양도', '영업양수', '자기주식취득신탁계약해지', 
    '자기주식취득신탁계약체결', '자기주식처분', '자기주식취득', '주식교환', 
    '회사분할합병', '회사분할', '회사합병', '사채권양수', '사채권양도결정'
]

# 증권신고서 타입
SECURITIES_TYPES = [
    '주식의포괄적교환이전', '합병', '증권예탁증권', '채무증권', '지분증권', '분할'
]

# 사업보고서 타입
BUSINESS_REPORT_TYPES = [
    '조건부자본증권미상환', '미등기임원보수', '회사채미상환', '단기사채미상환', '기업어음미상환', 
    '채무증권발행', '사모자금사용', '공모자금사용', '임원전체보수승인', '임원전체보수유형', 
    '주식총수', '회계감사', '감사용역', '회계감사용역계약', '사외이사', '신종자본증권미상환', 
    '증자', '배당', '자기주식', '최대주주', '최대주주변동', '소액주주', '임원', '직원', 
    '임원개인보수', '임원전체보수', '개인별보수', '타법인출자'
]


class QueryExpander:
    """단순화된 쿼리 확장 및 파라미터 생성"""
    
    def __init__(self, dart_reader=None):
        """
        Args:
            dart_reader: OpenDartReader 인스턴스
        """
        # 1. LangExtract 파서 (필수)
        self.langextract_parser = QueryParserLangExtract()
        
        # 2. 검증 도구들
        self.company_validator = CompanyValidator(dart_reader)
        self.doc_mapper = DocTypeMapper(get_openai_client())
        
        # 3. 상세 타입 매핑
        self.major_event_types = MAJOR_EVENT_TYPES
        self.securities_types = SECURITIES_TYPES
        self.business_report_types = BUSINESS_REPORT_TYPES
    
    def _extract_detailed_types(self, query: str, keywords: List[str] = None) -> Dict[str, List[str]]:
        """
        쿼리에서 상세 문서 타입 추출
        
        Args:
            query: 사용자 쿼리
            keywords: 추출된 키워드 리스트
            
        Returns:
            상세 타입 딕셔너리
        """
        detailed_types = {
            "major_events": [],
            "securities": [],
            "business_reports": []
        }
        
        # 쿼리와 키워드를 결합하여 검색 (공백 제거 및 소문자 변환)
        search_text = query.lower().replace(" ", "").replace("\t", "").replace("\n", "")
        if keywords:
            search_text += "".join(keywords).lower().replace(" ", "")
        
        # 주요사항보고서 이벤트 타입 검색
        for event_type in self.major_event_types:
            event_normalized = event_type.lower().replace(" ", "")
            if event_normalized in search_text:
                detailed_types["major_events"].append(event_type)
        
        # 증권신고서 타입 검색
        for sec_type in self.securities_types:
            sec_normalized = sec_type.lower().replace(" ", "")
            if sec_normalized in search_text:
                detailed_types["securities"].append(sec_type)
        
        # 사업보고서 타입 검색
        for biz_type in self.business_report_types:
            biz_normalized = biz_type.lower().replace(" ", "")
            if biz_normalized in search_text:
                detailed_types["business_reports"].append(biz_type)
        
        return detailed_types
        
    async def expand_query(self, query: str) -> Dict[str, Any]:
        """
        사용자 쿼리를 DART API 파라미터로 확장
        
        흐름:
        1. LangExtract로 파싱
        2. 각 요소 검증
        3. DART API 파라미터 생성
        
        Args:
            query: 사용자 쿼리
            
        Returns:
            확장된 검색 파라미터 딕셔너리
        """
        # 결과 파라미터 초기화
        params = {
            "original_query": query,
            "companies": [],
            "corp_codes": [],
            "date_range": None,
            "doc_types": [],
            "keywords": [],
            "search_params": {},
            "needs_confirmation": False
        }
        
        # Step 1: LangExtract로 파싱
        try:
            parsed = await self.langextract_parser.parse_query(query)
        except Exception as e:
            print(f"LangExtract 파싱 실패: {e}")
            # 폴백: 기본 파싱
            parsed = self._fallback_parse(query)
        
        # Step 2: 날짜 검증 및 변환
        if parsed.get("date_expressions"):
            # 추출된 날짜 표현들을 하나의 문자열로 합침
            date_text = " ".join([expr["text"] for expr in parsed["date_expressions"]])
            date_range = extract_date_range_from_query(date_text)
            
            if date_range:
                params["date_range"] = {
                    "start": date_range[0],
                    "end": date_range[1]
                }
                params["search_params"]["bgn_de"] = date_range[0]
                params["search_params"]["end_de"] = date_range[1]
        
        # Step 3: 기업명 검증
        companies_to_validate = []
        companies_to_validate.extend(parsed.get("companies", []))
        companies_to_validate.extend(parsed.get("stock_codes", []))
        
        for company in companies_to_validate:
            # 종목코드인 경우 바로 처리
            if company.isdigit() and len(company) == 6:
                stock_result = self.company_validator.get_company_by_stock_code(company)
                if stock_result:
                    params["companies"].append(stock_result["company"])
                    params["corp_codes"].append(stock_result["corp_code"])
                    continue
            
            # 기업명 검증
            validation = self.company_validator.find_company(company, threshold=80)
            
            if validation["status"] in ["exact", "fuzzy"]:
                if validation["company"] and validation["corp_code"]:
                    params["companies"].append(validation["company"])
                    params["corp_codes"].append(validation["corp_code"])
                    
                    # 신뢰도가 낮으면 확인 필요
                    if validation.get("score", 100) < 90:
                        params["needs_confirmation"] = True
        
        # Step 4: 문서유형 검증 - 전체 파싱 결과를 전달
        if parsed.get("doc_types") or parsed.get("keywords"):
            # LangExtract 파싱 결과 전체를 doc_mapper에 전달
            if hasattr(self.doc_mapper, 'map_query_to_doc_types_sync'):
                mapped_types = self.doc_mapper.map_query_to_doc_types_sync(query, parsed)
            else:
                mapped_types = await self.doc_mapper.map_query_to_doc_types(query, parsed)
            
            # 가장 신뢰도 높은 것만 사용
            if mapped_types:
                code, confidence = mapped_types[0]
                params["doc_types"].append({
                    "code": code,
                    "name": self.doc_mapper.get_doc_type_name(code),
                    "confidence": confidence
                })
                
                # DART API 파라미터 설정
                if confidence >= 0.5:
                    params["search_params"]["pblntf_detail_ty"] = code
        
        # Step 5: 키워드 추출
        if parsed.get("keywords"):
            params["keywords"] = [kw["text"] for kw in parsed["keywords"]]
        
        # Step 6: 상세 문서 타입 추출
        detailed_types = self._extract_detailed_types(query, params["keywords"])
        params["detailed_types"] = detailed_types
        
        # 상세 타입이 있으면 해당 정보도 doc_types에 추가
        if detailed_types["major_events"]:
            params["major_events"] = detailed_types["major_events"]
        if detailed_types["securities"]:
            params["securities"] = detailed_types["securities"]
        if detailed_types["business_reports"]:
            params["business_reports"] = detailed_types["business_reports"]
        
        return params
    
    def _fallback_parse(self, query: str) -> Dict[str, Any]:
        """
        LangExtract 실패 시 간단한 폴백 파싱
        
        Args:
            query: 사용자 쿼리
            
        Returns:
            기본 파싱 결과
        """
        import re
        
        result = {
            "companies": [],
            "stock_codes": [],
            "doc_types": [],
            "date_expressions": [],
            "keywords": []
        }
        
        # 6자리 숫자는 종목코드로 추정
        stock_codes = re.findall(r'\b\d{6}\b', query)
        result["stock_codes"] = stock_codes
        
        # 간단한 문서유형 매칭
        doc_type_keywords = {
            "사업보고서": "사업보고서",
            "반기보고서": "반기보고서",
            "분기보고서": "분기보고서",
            "감사보고서": "감사보고서",
            "주요사항보고서": "주요사항보고서"
        }
        
        for keyword, name in doc_type_keywords.items():
            if keyword in query:
                result["doc_types"].append({"name": name})
                break
        
        # 날짜 표현 추출
        date_keywords = ["올해", "작년", "최근", "어제", "오늘"]
        for keyword in date_keywords:
            if keyword in query:
                result["date_expressions"].append({"text": keyword})
                break
        
        return result
    
    def create_search_params(self, expanded_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        확장된 쿼리를 기반으로 DART API 검색 파라미터 생성
        기업명이 없는 경우 3개월씩 분할하여 검색
        
        Args:
            expanded_query: 확장된 쿼리 정보
            
        Returns:
            DART API 검색 파라미터 리스트
        """
        search_params_list = []
        base_params = expanded_query.get("search_params", {})
        
        # 기업별 검색
        if expanded_query["corp_codes"]:
            for corp_code in expanded_query["corp_codes"]:
                params = base_params.copy()
                params["corp_code"] = corp_code
                params["page_count"] = 100
                search_params_list.append(params)
        else:
            # 기업명 없는 전체 검색 - 3개월 단위로 분할
            from datetime import timedelta
            
            # 날짜 범위 결정
            if "bgn_de" in base_params and "end_de" in base_params:
                start_date = datetime.strptime(base_params["bgn_de"], "%Y%m%d")
                end_date = datetime.strptime(base_params["end_de"], "%Y%m%d")
            else:
                # 날짜 범위가 없으면 최근 3개월
                end_date = datetime.now()
                start_date = end_date - timedelta(days=90)
            
            # 기간 계산
            total_days = (end_date - start_date).days
            
            # 3개월(90일) 초과시 분할 검색
            if total_days > 90:
                # 3개월씩 역순으로 분할 (최신 데이터부터)
                current_end = end_date
                
                while current_end > start_date:
                    current_start = max(current_end - timedelta(days=89), start_date)  # 89일 = 3개월 - 1일
                    
                    params = base_params.copy()
                    params["bgn_de"] = current_start.strftime("%Y%m%d")
                    params["end_de"] = current_end.strftime("%Y%m%d")
                    params["page_count"] = 100
                    search_params_list.append(params)
                    
                    # 다음 구간으로 이동 (1일 겹침 방지)
                    current_end = current_start - timedelta(days=1)
            else:
                # 3개월 이하는 그대로 검색
                params = base_params.copy()
                params["bgn_de"] = start_date.strftime("%Y%m%d") if "bgn_de" not in params else params["bgn_de"]
                params["end_de"] = end_date.strftime("%Y%m%d") if "end_de" not in params else params["end_de"]
                params["page_count"] = 100
                search_params_list.append(params)
        
        return search_params_list
    
    def format_result(self, expanded: Dict[str, Any]) -> str:
        """
        확장된 쿼리 정보를 읽기 쉬운 형식으로 포맷
        
        Args:
            expanded: 확장된 쿼리 정보
            
        Returns:
            포맷된 문자열
        """
        lines = []
        lines.append(f"📝 원본 쿼리: {expanded['original_query']}")
        
        if expanded['companies']:
            lines.append(f"🏢 기업: {', '.join(expanded['companies'])}")
            
        if expanded['date_range']:
            start = expanded['date_range']['start']
            end = expanded['date_range']['end']
            # YYYYMMDD를 YYYY-MM-DD로 변환
            start_fmt = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
            end_fmt = f"{end[:4]}-{end[4:6]}-{end[6:8]}"
            lines.append(f"📅 기간: {start_fmt} ~ {end_fmt}")
            
        if expanded['doc_types']:
            doc_names = [dt['name'] for dt in expanded['doc_types']]
            lines.append(f"📄 문서유형: {', '.join(doc_names)}")
            
        if expanded['keywords']:
            lines.append(f"🔍 키워드: {', '.join(expanded['keywords'][:10])}")
        
        # 상세 문서 타입들
        detailed_types = expanded.get('detailed_types', {})
        if any(detailed_types.values()):
            detail_info = []
            if detailed_types.get('major_events'):
                detail_info.append(f"주요사항: {len(detailed_types['major_events'])}개")
            if detailed_types.get('securities'):
                detail_info.append(f"증권신고서: {len(detailed_types['securities'])}개")
            if detailed_types.get('business_reports'):
                detail_info.append(f"사업보고서: {len(detailed_types['business_reports'])}개")
            lines.append(f"📋 상세타입: {', '.join(detail_info)}")
        
        if expanded.get('needs_confirmation'):
            lines.append("⚠️ 일부 항목은 확인이 필요합니다")
            
        return "\n".join(lines)