"""
DART API MCP Tools
한국 금융감독원 DART (전자공시시스템) API를 위한 MCP 도구 모음
"""

import os
import json
import asyncio
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import re

from utils.logging import get_logger
from utils.parse_dart import (
    parse_dart_url_content,
    parse_multiple_dart_urls,
    extract_structured_info_from_documents
)
from utils.rate_limiter import dart_rate_limit
import yaml
from pathlib import Path

# OpenDartReader 임포트 시도
try:
    import OpenDartReader
    opendart_available = True
except ImportError:
    OpenDartReader = None
    opendart_available = False

load_dotenv()

# Logger 초기화
logger = get_logger("dart-mcp")

# API 키 (환경변수에서 로드)
DART_API_KEY = os.getenv("DART_API_KEY")

# OpenDartReader 객체 초기화
dart_reader = None
if OpenDartReader and DART_API_KEY:
    dart_reader = OpenDartReader(DART_API_KEY)

# YAML 파일에서 필드 매핑 로드
def load_field_mappings():
    """YAML 파일에서 필드 매핑 로드"""
    config_path = Path(__file__).parent.parent / "config" / "dart_field_mappings.yaml"
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data.get('field_mappings', {}), data.get('corp_cls_mapping', {})
        except Exception as e:
            logger.warning(f"Failed to load field mappings from YAML: {e}")
    
    # 파일이 없거나 로드 실패시 기본값
    return {
        'rcept_dt': '접수일자',
        'flr_nm': '제출인',
        'rm': '비고',
    }, {
        'Y': '유가증권',
        'K': '코스닥',
        'N': '코넥스',
        'E': '기타'
    }

# 필드 매핑 로드
FIELD_MAPPINGS, CORP_CLS_MAPPING = load_field_mappings()

# ==================== 상수 정의 ==================== #

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

# 공시 종류
DISCLOSURE_KINDS = {
    'A': '정기보고서', 'B': '주요사항보고서', 'C': '발행공시', 'D': '지분공시', 
    'E': '기타공시', 'F': '외부감사 관련', 'G': '펀드공시', 'H': '자산유동화', 
    'I': '거래소 공시', 'J': '공정위 공시'
}

# 보고서 코드
REPORT_CODES = {
    '11011': '사업보고서', '11012': '반기보고서', 
    '11013': '1분기보고서', '11014': '3분기보고서'
}

# XBRL 분류
XBRL_CLASSIFICATIONS = {
    'BS1': '재무상태표', 'IS1': '손익계산서', 'CIS1': '포괄손익계산서',
    'CF1': '현금흐름표', 'SCE1': '자본변동표'
}



def _apply_field_mappings(data):
    """데이터에 필드 매핑 적용"""
    if isinstance(data, dict):
        mapped = {}
        for key, value in data.items():
            # 필드명 한글화
            korean_key = FIELD_MAPPINGS.get(key, key)
            
            # 특정 필드 값 변환
            if key == 'corp_cls' and value in CORP_CLS_MAPPING:
                mapped[korean_key] = CORP_CLS_MAPPING[value]
            elif value is None:
                mapped[korean_key] = ""
            else:
                mapped[korean_key] = value
        return mapped
    elif isinstance(data, list):
        return [_apply_field_mappings(item) if isinstance(item, dict) else item for item in data]
    else:
        return data


def _serialize_dataframe(df, apply_mapping=False, drop_na_values=True) -> str:
    """DataFrame, dict, list 등을 JSON 문자열로 변환
    
    Args:
        df: 변환할 데이터
        apply_mapping: 필드 매핑 적용 여부
        drop_na_values: 각 레코드에서 NaN 값을 가진 필드를 제외할지 여부
    """
    try:
        if df is None:
            return json.dumps({"result": "데이터가 없습니다."}, ensure_ascii=False)
        
        # pandas DataFrame인 경우
        if hasattr(df, 'empty'):
            if df.empty:
                return json.dumps({"result": "데이터가 없습니다."}, ensure_ascii=False)
                
            # DataFrame을 dict로 변환
            if drop_na_values:
                # NaN 값을 가진 필드를 제외하고 변환
                import pandas as pd
                result = []
                for _, row in df.iterrows():
                    # NaN이 아닌 값만 포함하는 dict 생성
                    record = {k: v for k, v in row.to_dict().items() 
                             if not (pd.isna(v) if hasattr(pd, 'isna') else v != v)}
                    result.append(record)
            else:
                result = df.to_dict('records')
            # 필드 매핑 적용
            if apply_mapping:
                result = _apply_field_mappings(result)
            return json.dumps(result, ensure_ascii=False, default=str)
        
        # dict인 경우
        elif isinstance(df, dict):
            if not df:
                return json.dumps({"result": "데이터가 없습니다."}, ensure_ascii=False)
            # 필드 매핑 적용
            if apply_mapping:
                df = _apply_field_mappings(df)
            return json.dumps(df, ensure_ascii=False, default=str)
        
        # list인 경우
        elif isinstance(df, list):
            if not df:
                return json.dumps({"result": "데이터가 없습니다."}, ensure_ascii=False)
            # 필드 매핑 적용
            if apply_mapping:
                df = _apply_field_mappings(df)
            return json.dumps(df, ensure_ascii=False, default=str)
        
        # 기타 타입인 경우 문자열로 변환
        else:
            return json.dumps({"result": str(df)}, ensure_ascii=False)
            
    except Exception as e:
        return json.dumps({"error": f"데이터 변환 오류: {str(e)}"}, ensure_ascii=False)


async def _handle_dart_error(func_name: str, error: Exception) -> str:
    """DART API 오류 처리"""
    error_msg = f"[{func_name}] DART API 오류: {str(error)}"
    logger.error(error_msg)
    return json.dumps({"error": error_msg}, ensure_ascii=False)


def _validate_company_input(company: Union[str, List[str]]) -> List[str]:
    """기업 입력값 검증 및 정규화"""
    if isinstance(company, str):
        # 쉼표로 구분된 문자열 처리
        companies = [c.strip() for c in company.split(',') if c.strip()]
    elif isinstance(company, list):
        companies = [str(c).strip() for c in company if str(c).strip()]
    else:
        companies = [str(company).strip()] if str(company).strip() else []
    
    if not companies:
        raise ValueError("기업명 또는 종목코드를 입력해주세요.")
    
    return companies


def _validate_date_format(date_str: str) -> bool:
    """날짜 형식 검증 (YYYY-MM-DD)"""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def _get_available_options(option_type: str) -> Dict[str, Any]:
    """사용 가능한 옵션들을 반환"""
    options_map = {
        'disclosure_kinds': DISCLOSURE_KINDS,
        'report_codes': REPORT_CODES,
        'major_event_types': {event: event for event in MAJOR_EVENT_TYPES},
        'securities_types': {sec: sec for sec in SECURITIES_TYPES},
        'business_report_types': {biz: biz for biz in BUSINESS_REPORT_TYPES},
        'xbrl_classifications': XBRL_CLASSIFICATIONS
    }
    return options_map.get(option_type, {})


# ==================== MCP 리소스 함수들 ==================== #

def get_dart_api_status() -> dict:
    """DART API 연결 상태와 설정 정보를 리소스로 제공"""
    return {
        "dart_api_initialized": dart_reader is not None,
        "dart_api_key_configured": DART_API_KEY is not None,
        "status": "정상" if dart_reader else "DART API 키가 설정되지 않음"
    }

def get_all_dart_options() -> dict:
    """모든 DART API 옵션 정보를 통합하여 제공"""
    return {
        "api_status": get_dart_api_status(),
        "disclosure_kinds": DISCLOSURE_KINDS,
        "report_codes": REPORT_CODES,
        "major_event_types": MAJOR_EVENT_TYPES,
        "securities_types": SECURITIES_TYPES,
        "business_report_types": BUSINESS_REPORT_TYPES,
        "xbrl_classifications": XBRL_CLASSIFICATIONS
    }


# ==================== 1. 공시정보 관련 ==================== #

@dart_rate_limit
async def search_company_disclosures(
    company: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    kind: Optional[str] = None,
    pblntf_detail_ty: Optional[str] = None,  # 상세 공시유형 추가
    final: bool = True,
) -> str:
    """
    특정 기업의 공시 목록을 검색합니다. 기업을 지정하지 않으면 모든 기업의 공시를 조회합니다.
    
    Args:
        company: 기업명 또는 종목코드 (예: '삼성전자', '005930', 선택사항)
        start_date: 시작일자 (YYYY-MM-DD 형식, 선택사항)
        end_date: 종료일자 (YYYY-MM-DD 형식, 선택사항)
        kind: 공시 종류 코드 (A:정기보고서, B:주요사항보고서, C:발행공시, D:지분공시, E:기타공시, F:외부감사관련, G:펀드공시, H:자산유동화, I:거래소공시, J:공정위공시)
        pblntf_detail_ty: 상세 공시유형 코드 (예: E004:주식매수선택권, B001:주요사항보고서 등)
        final: 최종보고서만 조회 여부 (True: 최종, False: 정정 포함)
    """
    if not dart_reader:
        return json.dumps({"error": "DART API가 초기화되지 않았습니다."}, ensure_ascii=False)
    
    try:
        # 날짜 형식 검증
        if start_date and not _validate_date_format(start_date):
            return json.dumps({"error": "시작일자는 YYYY-MM-DD 형식이어야 합니다."}, ensure_ascii=False)
        if end_date and not _validate_date_format(end_date):
            return json.dumps({"error": "종료일자는 YYYY-MM-DD 형식이어야 합니다."}, ensure_ascii=False)
            
        # 공시 종류 검증
        if kind and kind not in DISCLOSURE_KINDS:
            available_kinds = _get_available_options('disclosure_kinds')
            return json.dumps({
                "error": f"올바르지 않은 공시 종류입니다: {kind}",
                "available_kinds": available_kinds
            }, ensure_ascii=False)
        
        # 파라미터 준비
        kwargs = {}
        if start_date:
            kwargs['start'] = start_date
        if end_date:
            kwargs['end'] = end_date
        
        # pblntf_detail_ty(상세유형)가 제공되면 kind_detail로 전달
        if pblntf_detail_ty:
            kwargs['kind_detail'] = pblntf_detail_ty
        elif kind:
            kwargs['kind'] = kind
            
        kwargs['final'] = final
        
        # 공시 목록 조회 (기업 지정 없으면 모든 기업)
        if company:
            result = dart_reader.list(company, **kwargs)
        else:
            result = dart_reader.list(**kwargs)
            
        return _serialize_dataframe(result)
        
    except Exception as e:
        return await _handle_dart_error("search_company_disclosures", e)


@dart_rate_limit
async def get_company_info(company: str) -> str:
    """
    기업의 기본 개황 정보를 조회합니다.
    
    Args:
        company: 기업명 또는 종목코드 (예: '삼성전자', '005930')
    """
    if not dart_reader:
        return json.dumps({"error": "DART API가 초기화되지 않았습니다."}, ensure_ascii=False)
    
    try:
        if not company.strip():
            return json.dumps({"error": "기업명 또는 종목코드를 입력해주세요."}, ensure_ascii=False)
            
        result = dart_reader.company(company.strip())
        return _serialize_dataframe(result)
        
    except Exception as e:
        return await _handle_dart_error("get_company_info", e)


async def search_companies_by_name(company_name: str) -> str:
    """
    회사명으로 기업들을 검색합니다.
    
    Args:
        company_name: 검색할 회사명 (부분 일치)
    """
    if not dart_reader:
        return json.dumps({"error": "DART API가 초기화되지 않았습니다."}, ensure_ascii=False)
    
    try:
        if not company_name.strip():
            return json.dumps({"error": "검색할 회사명을 입력해주세요."}, ensure_ascii=False)
            
        result = dart_reader.company_by_name(company_name.strip())
        return _serialize_dataframe(result)
        
    except Exception as e:
        return await _handle_dart_error("search_companies_by_name", e)


async def find_corporation_code(company: str) -> str:
    """
    기업명이나 종목코드로 고유번호(corp_code)를 조회합니다.
    
    Args:
        company: 기업명 또는 종목코드 (예: '삼성전자', '005930')
    """
    if not dart_reader:
        return json.dumps({"error": "DART API가 초기화되지 않았습니다."}, ensure_ascii=False)
    
    try:
        if not company.strip():
            return json.dumps({"error": "기업명 또는 종목코드를 입력해주세요."}, ensure_ascii=False)
            
        result = dart_reader.find_corp_code(company.strip())
        return _serialize_dataframe(result)
        
    except Exception as e:
        return await _handle_dart_error("find_corporation_code", e)


# ==================== 2. 공시서류 원본 관련 ==================== #

@dart_rate_limit
async def get_document_content(rcp_no: str, get_all: bool = False) -> str:
    """
    공시서류의 원본 내용을 조회합니다.
    
    Args:
        rcp_no: 접수번호 (예: '20220308000798')
        get_all: 모든 문서 내용 조회 여부 (True: document_all 사용, False: document 사용)
    """
    if not dart_reader:
        return json.dumps({"error": "DART API가 초기화되지 않았습니다."}, ensure_ascii=False)
    
    try:
        if not rcp_no.strip():
            return json.dumps({"error": "접수번호를 입력해주세요."}, ensure_ascii=False)
        
        if get_all:
            result = dart_reader.document_all(rcp_no.strip())
            documents = {}
            for i, doc in enumerate(result):
                documents[f"document_{i+1}"] = doc
            return json.dumps(documents, ensure_ascii=False)
        else:
            result = dart_reader.document(rcp_no.strip())
            return json.dumps({"content": result}, ensure_ascii=False)
        
    except Exception as e:
        return await _handle_dart_error("get_document_content", e)


@dart_rate_limit
async def get_attached_documents(rcp_no: str, match: Optional[str] = None, document_type: str = "list") -> str:
    """
    첨부 문서의 제목과 URL을 조회합니다.
    
    Args:
        rcp_no: 접수번호 (예: '20220308000798')
        match: 매칭할 문서 제목 키워드 (선택사항)
        document_type: 문서 타입 (\"list\": attach_doc_list, \"docs\": attach_docs, \"files\": attach_files)
    """
    if not dart_reader:
        return json.dumps({"error": "DART API가 초기화되지 않았습니다."}, ensure_ascii=False)
    
    try:
        if not rcp_no.strip():
            return json.dumps({"error": "접수번호를 입력해주세요."}, ensure_ascii=False)
        
        rcp_no = rcp_no.strip()
        result = None
        
        try:
            if document_type == "files":
                if hasattr(dart_reader, 'attach_files'):
                    result = dart_reader.attach_files(rcp_no)
                    
            elif document_type == "docs":
                if hasattr(dart_reader, 'attach_docs'):
                    if match:
                        result = dart_reader.attach_docs(rcp_no, match=match)
                    else:
                        result = dart_reader.attach_docs(rcp_no)
                    
            else:  # "list" 또는 기본값
                if hasattr(dart_reader, 'attach_doc_list'):
                    if match:
                        result = dart_reader.attach_doc_list(rcp_no, match=match)
                    else:
                        result = dart_reader.attach_doc_list(rcp_no)
                    
        except Exception as e:
            return json.dumps({
                "error": f"문서 조회 중 오류 발생: {str(e)}",
                "document_type": document_type
            }, ensure_ascii=False)
            
        return _serialize_dataframe(result)
        
    except Exception as e:
        return await _handle_dart_error("get_attached_documents", e)


# ==================== 3. 재무정보 관련 ==================== #

@dart_rate_limit
async def get_financial_statements(
    company: str,
    year: int,
    report_code: str = '11011',
    comprehensive: bool = False
) -> str:
    """
    기업의 재무제표를 조회합니다. 쉼표로 구분하여 여러 기업을 동시에 조회할 수 있습니다.
    
    Args:
        company: 기업명/종목코드 또는 쉼표로 구분된 여러 기업 (예: '삼성전자', '005930', '005930,000660,005380')
        year: 조회 연도
        report_code: 보고서 코드 (11011:사업보고서, 11012:반기보고서, 11013:1분기보고서, 11014:3분기보고서)
        comprehensive: 포괄적 재무제표 조회 여부 (True: finstate_all 사용, False: finstate 사용)
    """
    if not dart_reader:
        return json.dumps({"error": "DART API가 초기화되지 않았습니다."}, ensure_ascii=False)
    
    try:
        companies = _validate_company_input(company)
        
        if year < 1990 or year > datetime.now().year:
            return json.dumps({"error": f"올바르지 않은 연도입니다: {year}"}, ensure_ascii=False)
        
        if report_code not in REPORT_CODES:
            available_codes = _get_available_options('report_codes')
            return json.dumps({
                "error": f"올바르지 않은 보고서 코드입니다: {report_code}",
                "available_codes": available_codes
            }, ensure_ascii=False)
        
        company_input = ','.join(companies)
        
        if comprehensive:
            result = dart_reader.finstate_all(company_input, year)
        else:
            result = dart_reader.finstate(company_input, year, reprt_code=report_code)
            
        return _serialize_dataframe(result)
        
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        return await _handle_dart_error("get_financial_statements", e)


@dart_rate_limit
async def get_xbrl_taxonomy(classification: str) -> str:
    """
    XBRL 표준계정과목체계(계정과목)를 조회합니다.
    
    Args:
        classification: 분류 코드 (BS1:재무상태표, IS1:손익계산서, CIS1:포괄손익계산서, CF1:현금흐름표, SCE1:자본변동표)
    """
    if not dart_reader:
        return json.dumps({"error": "DART API가 초기화되지 않았습니다."}, ensure_ascii=False)
    
    try:
        if classification not in XBRL_CLASSIFICATIONS:
            available_classifications = _get_available_options('xbrl_classifications')
            return json.dumps({
                "error": f"올바르지 않은 분류 코드입니다: {classification}",
                "available_classifications": available_classifications
            }, ensure_ascii=False)
            
        result = dart_reader.xbrl_taxonomy(classification)
        return _serialize_dataframe(result)
        
    except Exception as e:
        return await _handle_dart_error("get_xbrl_taxonomy", e)


# ==================== 4. 사업보고서 관련 ==================== #

@dart_rate_limit
async def get_business_report_data(
    company: str,
    business_report_type: str,
    year: int
) -> str:
    """
    사업보고서의 특정 항목 데이터를 조회합니다.
    
    Args:
        company: 기업명 또는 종목코드
        business_report_type: 조회할 사업보고서 항목 (배당, 임원, 직원, 주식총수 등)
        year: 조회 연도
    """
    if not dart_reader:
        return json.dumps({"error": "DART API가 초기화되지 않았습니다."}, ensure_ascii=False)
    
    try:
        if not company.strip():
            return json.dumps({"error": "기업명 또는 종목코드를 입력해주세요."}, ensure_ascii=False)
        
        if business_report_type not in BUSINESS_REPORT_TYPES:
            available_types = _get_available_options('business_report_types')
            return json.dumps({
                "error": f"올바르지 않은 사업보고서 항목입니다: {business_report_type}",
                "available_types": list(available_types.keys())
            }, ensure_ascii=False)
        
        if year < 1990 or year > datetime.now().year:
            return json.dumps({"error": f"올바르지 않은 연도입니다: {year}"}, ensure_ascii=False)
            
        result = dart_reader.report(company.strip(), business_report_type, year)
        return _serialize_dataframe(result, apply_mapping=True)
        
    except Exception as e:
        return await _handle_dart_error("get_business_report_data", e)


# ==================== 5. 지분공시 관련 ==================== #

@dart_rate_limit
async def get_major_shareholders(company: str, shareholder_type: str = "major") -> str:
    """
    주주 관련 보고를 조회합니다.
    
    Args:
        company: 기업명 또는 종목코드
        shareholder_type: 주주 타입 (\"major\": 대량보유상황보고, \"executive\": 임원·주요주주소유보고)
    """
    if not dart_reader:
        return json.dumps({"error": "DART API가 초기화되지 않았습니다."}, ensure_ascii=False)
    
    try:
        if not company.strip():
            return json.dumps({"error": "기업명 또는 종목코드를 입력해주세요."}, ensure_ascii=False)
        
        if shareholder_type not in ["major", "executive"]:
            return json.dumps({
                "error": f"올바르지 않은 주주 타입입니다: {shareholder_type}",
                "available_types": ["major", "executive"]
            }, ensure_ascii=False)
        
        if shareholder_type == "executive":
            result = dart_reader.major_shareholders_exec(company.strip())
        else:  # "major"
            result = dart_reader.major_shareholders(company.strip())
            
        return _serialize_dataframe(result, apply_mapping=True)
        
    except Exception as e:
        return await _handle_dart_error("get_major_shareholders", e)


# ==================== 6. 주요사항보고서 관련 ==================== #

@dart_rate_limit
async def get_major_events(
    company: str,
    event_type: str,
    start_year: Optional[str] = None,
    end_year: Optional[str] = None
) -> str:
    """
    주요사항보고서를 조회합니다.
    
    Args:
        company: 기업명 또는 종목코드
        event_type: 주요사항 종류 (회사합병, 소송, 유상증자 등)
        start_year: 시작 연도 (선택사항)
        end_year: 종료 연도 (선택사항)
    """
    if not dart_reader:
        return json.dumps({"error": "DART API가 초기화되지 않았습니다."}, ensure_ascii=False)
    
    try:
        if not company.strip():
            return json.dumps({"error": "기업명 또는 종목코드를 입력해주세요."}, ensure_ascii=False)
        
        if event_type not in MAJOR_EVENT_TYPES:
            available_types = _get_available_options('major_event_types')
            return json.dumps({
                "error": f"올바르지 않은 주요사항 종류입니다: {event_type}",
                "available_types": list(available_types.keys())
            }, ensure_ascii=False)
        
        kwargs = {}
        if start_year:
            kwargs['start'] = start_year
        if end_year:
            kwargs['end'] = end_year
            
        result = dart_reader.event(company.strip(), event_type, **kwargs)
        return _serialize_dataframe(result, apply_mapping=True)
        
    except Exception as e:
        return await _handle_dart_error("get_major_events", e)


# ==================== 7. 증권신고서 관련 ==================== #

@dart_rate_limit
async def get_securities_report(
    company: str,
    securities_type: str,
    start_year: Optional[str] = None,
    end_year: Optional[str] = None
) -> str:
    """
    증권신고서를 조회합니다.
    
    Args:
        company: 기업명 또는 종목코드
        securities_type: 증권신고서 종류 (합병, 분할, 지분증권 등)
        start_year: 시작 연도 (선택사항)
        end_year: 종료 연도 (선택사항)
    """
    if not dart_reader:
        return json.dumps({"error": "DART API가 초기화되지 않았습니다."}, ensure_ascii=False)
    
    try:
        if not company.strip():
            return json.dumps({"error": "기업명 또는 종목코드를 입력해주세요."}, ensure_ascii=False)
        
        if securities_type not in SECURITIES_TYPES:
            available_types = _get_available_options('securities_types')
            return json.dumps({
                "error": f"올바르지 않은 증권신고서 종류입니다: {securities_type}",
                "available_types": list(available_types.keys())
            }, ensure_ascii=False)
        
        kwargs = {}
        if start_year:
            kwargs['start'] = start_year
        if end_year:
            kwargs['end'] = end_year
            
        result = dart_reader.regstate(company.strip(), securities_type, **kwargs)
        return _serialize_dataframe(result, apply_mapping=True)
        
    except Exception as e:
        return await _handle_dart_error("get_securities_report", e)


# ==================== 8. 옵션 조회 기능 ==================== #

@dart_rate_limit
async def get_available_options(option_type: str) -> str:
    """
    사용 가능한 옵션들을 조회합니다.
    
    Args:
        option_type: 옵션 타입 (disclosure_kinds, report_codes, major_event_types, securities_types, business_report_types, xbrl_classifications)
    """
    try:
        options = _get_available_options(option_type)
        if not options:
            return json.dumps({
                "error": f"올바르지 않은 옵션 타입입니다: {option_type}",
                "available_option_types": [
                    "disclosure_kinds", "report_codes", "major_event_types", 
                    "securities_types", "business_report_types", "xbrl_classifications"
                ]
            }, ensure_ascii=False)
        
        return json.dumps({
            "option_type": option_type,
            "options": options
        }, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({"error": f"옵션 조회 오류: {str(e)}"}, ensure_ascii=False)


# ==================== URL 파싱 기능 ==================== #

async def dart_parse_url_content(url: str) -> str:
    """
    DART viewer URL의 실제 내용을 파싱하여 구조화된 텍스트로 반환합니다.
    
    Args:
        url: DART viewer URL (예: 'http://dart.fss.or.kr/report/viewer.do?rcpNo=...')
    """
    return await parse_dart_url_content(url)


async def dart_parse_multiple_urls(urls: str) -> str:
    """
    여러 DART URL의 내용을 한번에 파싱합니다.
    
    Args:
        urls: 쉼표로 구분된 URL 목록 또는 '@'로 구분된 URL 목록
    """
    return await parse_multiple_dart_urls(urls)


async def dart_extract_structured_info(rcp_no: str, info_types: Optional[List[str]] = None) -> str:
    """
    공시 문서에서 구조화된 정보를 추출합니다.
    
    Args:
        rcp_no: 접수번호
        info_types: 추출할 정보 유형 ['financial', 'business', 'audit', 'all']
    """
    # 비동기 함수들을 위한 래퍼 함수들 정의
    async def get_doc_content_wrapper(rcp_no):
        return await get_document_content(rcp_no, get_all=False)
    
    async def get_sub_docs_wrapper(rcp_no, match=None):
        return await get_attached_documents(rcp_no, match, "sub")
    
    async def get_attached_docs_wrapper(rcp_no, match=None):
        return await get_attached_documents(rcp_no, match, "list")
    
    return await extract_structured_info_from_documents(
        rcp_no=rcp_no,
        info_types=info_types,
        dart_reader=dart_reader,
        get_document_content_func=get_doc_content_wrapper,
        get_sub_documents_func=get_sub_docs_wrapper,
        get_attached_document_list_func=get_attached_docs_wrapper
    )


def register_tools(mcp: FastMCP):
    """
    DART API MCP 도구들과 리소스들을 등록합니다.
    """
    
    # ==================== MCP 리소스 등록 ==================== #
    @mcp.resource("dart://api/status")
    def dart_api_status_resource() -> str:
        """DART API 연결 상태와 설정 정보"""
        return json.dumps(get_dart_api_status(), ensure_ascii=False, indent=2)
    
    @mcp.resource("dart://options/all")
    def all_dart_options_resource() -> str:
        """모든 DART API 옵션 정보를 통합하여 제공"""
        return json.dumps(get_all_dart_options(), ensure_ascii=False, indent=2)
    
    # ==================== 공시정보 관련 도구들 ==================== #
    mcp.tool(
        name="search_company_disclosures",
        description="특정 기업의 공시 목록을 검색하거나 전체 공시를 조회합니다. 기업명이나 종목코드로 검색 가능하며, 날짜 범위나 공시 종류를 지정할 수 있습니다."
    )(search_company_disclosures)
    
    mcp.tool(
        name="get_company_info",
        description="기업의 기본 개황 정보를 조회합니다. 기업명이나 종목코드로 검색할 수 있습니다."
    )(get_company_info)
    
    mcp.tool(
        name="search_companies_by_name",
        description="회사명으로 기업들을 검색합니다. 부분 일치로 검색이 가능합니다."
    )(search_companies_by_name)
    
    mcp.tool(
        name="find_corporation_code",
        description="기업명이나 종목코드로 고유번호(corp_code)를 조회합니다."
    )(find_corporation_code)
    
    # ==================== 공시서류 원본 관련 도구들 ==================== #
    mcp.tool(
        name="get_document_content",
        description="공시서류의 원본 내용을 조회합니다."
    )(get_document_content)
    
    mcp.tool(
        name="get_attached_documents",
        description="첨부 문서의 제목과 URL을 조회합니다."
    )(get_attached_documents)
    
    # ==================== 재무정보 관련 도구들 ==================== #
    mcp.tool(
        name="get_financial_statements",
        description="기업의 재무제표를 조회합니다. 쉼표로 구분하여 여러 기업을 동시에 조회할 수 있습니다."
    )(get_financial_statements)
    
    mcp.tool(
        name="get_xbrl_taxonomy",
        description="XBRL 표준계정과목체계(계정과목)를 조회합니다."
    )(get_xbrl_taxonomy)
    
    # ==================== 사업보고서 관련 도구들 ==================== #
    mcp.tool(
        name="get_business_report_data",
        description="사업보고서의 특정 항목 데이터를 조회합니다."
    )(get_business_report_data)
    
    # ==================== 지분공시 관련 도구들 ==================== #
    mcp.tool(
        name="get_major_shareholders",
        description="주주 관련 보고를 조회합니다."
    )(get_major_shareholders)
    
    # ==================== 주요사항보고서 관련 도구들 ==================== #
    mcp.tool(
        name="get_major_events",
        description="주요사항보고서를 조회합니다."
    )(get_major_events)
    
    # ==================== 증권신고서 관련 도구들 ==================== #
    mcp.tool(
        name="get_securities_report",
        description="증권신고서를 조회합니다."
    )(get_securities_report)
    
    # ==================== 옵션 조회 도구들 ==================== #
    mcp.tool(
        name="get_available_options",
        description="사용 가능한 옵션들을 조회합니다."
    )(get_available_options)
    
    # ==================== URL 파싱 및 내용 추출 도구들 ==================== #
    mcp.tool(
        name="parse_dart_url_content",
        description="DART viewer URL의 실제 내용을 파싱하여 구조화된 텍스트로 반환합니다."
    )(dart_parse_url_content)
    
    mcp.tool(
        name="parse_multiple_dart_urls",
        description="여러 DART URL의 내용을 한번에 파싱합니다."
    )(dart_parse_multiple_urls)
    
    mcp.tool(
        name="extract_structured_info_from_documents",
        description="공시 문서에서 구조화된 정보를 추출합니다."
    )(dart_extract_structured_info)