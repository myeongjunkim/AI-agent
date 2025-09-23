"""
OpenDartReader 기반 MCP용 경량 래퍼 도구 모음

목표:
- LLM이 의도를 명확히 파악할 수 있도록, OpenDartReader의 핵심 기능을 목적지향 함수로 래핑
- 각 함수는 명확한 함수명과 엄격한 Docstring(Description, Args 타입/제약)을 제공
- 반환은 JSON 문자열 위주로 일관화하여 MCP 상호운용성 확보

주의:
- 이 모듈은 OpenDartReader의 동기 API를 직접 호출합니다. I/O는 외부 서비스 호출이므로
  호출 빈도를 제어할 상위 레이어에서의 레이트 리밋 적용을 권장합니다.
"""

from __future__ import annotations

import os
import json
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP

try:
    import OpenDartReader  # type: ignore
    _opendart_available = True
except Exception:  # pragma: no cover - 런타임 환경에 따라 미설치 가능
    OpenDartReader = None  # type: ignore
    _opendart_available = False


# ==================== OpenDartReader 클라이언트 ==================== #
DART_API_KEY = os.getenv("DART_API_KEY")

_dart: Any = None
if _opendart_available and DART_API_KEY:
    _dart = OpenDartReader(DART_API_KEY)  # type: ignore[call-arg]


# ==================== 상수/코드 테이블 ==================== #
DISCLOSURE_KINDS: Dict[str, str] = {
    # pblntf_ty (OpenDart 공시종류 대분류)
    "A": "정기공시",
    "B": "주요사항보고",
    "C": "발행공시",
    "D": "지분공시",
    "E": "기타공시",
    "F": "외부감사관련",
    "G": "펀드공시",
    "H": "자산유동화",
    "I": "거래소공시",
    "J": "공정위공시",
}

REPORT_CODES: Dict[str, str] = {
    "11011": "사업보고서",
    "11012": "반기보고서",
    "11013": "1분기보고서",
    "11014": "3분기보고서",
}

XBRL_CLASSIFICATIONS: Dict[str, str] = {
    "BS1": "재무상태표",
    "IS1": "손익계산서",
    "CIS1": "포괄손익계산서",
    "CF1": "현금흐름표",
    "SCE1": "자본변동표",
}

MAJOR_EVENT_TYPES: List[str] = [
    "부도발생",
    "영업정지",
    "회생절차",
    "해산사유",
    "유상증자",
    "무상증자",
    "유무상증자",
    "감자",
    "관리절차개시",
    "소송",
    "해외상장결정",
    "해외상장폐지결정",
    "해외상장",
    "해외상장폐지",
    "전환사채발행",
    "신주인수권부사채발행",
    "교환사채발행",
    "관리절차중단",
    "조건부자본증권발행",
    "자산양수도",
    "타법인증권양도",
    "유형자산양도",
    "유형자산양수",
    "타법인증권양수",
    "영업양도",
    "영업양수",
    "자기주식취득신탁계약해지",
    "자기주식취득신탁계약체결",
    "자기주식처분",
    "자기주식취득",
    "주식교환",
    "회사분할합병",
    "회사분할",
    "회사합병",
    "사채권양수",
    "사채권양도결정",
]

SECURITIES_TYPES: List[str] = [
    "주식의포괄적교환이전",
    "합병",
    "증권예탁증권",
    "채무증권",
    "지분증권",
    "분할",
]

# 공시 상세유형 코드 표 (pblntf_detail_ty)
DISCLOSURE_KIND_DETAILS: Dict[str, str] = {
    "A001": "사업보고서",
    "A002": "반기보고서",
    "A003": "분기보고서",
    "A004": "등록법인결산서류(자본시장법이전)",
    "A005": "소액공모법인결산서류",
    "B001": "주요사항보고서",
    "B002": "주요경영사항신고(자본시장법 이전)",
    "B003": "최대주주등과의거래신고(자본시장법 이전)",
    "C001": "증권신고(지분증권)",
    "C002": "증권신고(채무증권)",
    "C003": "증권신고(파생결합증권)",
    "C004": "증권신고(합병등)",
    "C005": "증권신고(기타)",
    "C006": "소액공모(지분증권)",
    "C007": "소액공모(채무증권)",
    "C008": "소액공모(파생결합증권)",
    "C009": "소액공모(합병등)",
    "C010": "소액공모(기타)",
    "C011": "호가중개시스템을통한소액매출",
    "D001": "주식등의대량보유상황보고서",
    "D002": "임원ㆍ주요주주특정증권등소유상황보고서",
    "D003": "의결권대리행사권유",
    "D004": "공개매수",
    "E001": "자기주식취득/처분",
    "E002": "신탁계약체결/해지",
    "E003": "합병등종료보고서",
    "E004": "주식매수선택권부여에관한신고",
    "E005": "사외이사에관한신고",
    "E006": "주주총회소집공고",
    "E007": "시장조성/안정조작",
    "E008": "합병등신고서(자본시장법 이전)",
    "E009": "금융위등록/취소(자본시장법 이전)",
    "F001": "감사보고서",
    "F002": "연결감사보고서",
    "F003": "결합감사보고서",
    "F004": "회계법인사업보고서",
    "F005": "감사전재무제표미제출신고서",
    "G001": "증권신고(집합투자증권-신탁형)",
    "G002": "증권신고(집합투자증권-회사형)",
    "G003": "증권신고(집합투자증권-합병)",
    "H001": "자산유동화계획/양도등록",
    "H002": "사업/반기/분기보고서",
    "H003": "증권신고(유동화증권등)",
    "H004": "채권유동화계획/양도등록",
    "H005": "수시보고",
    "H006": "주요사항보고서",
    "I001": "수시공시",
    "I002": "공정공시",
    "I003": "시장조치/안내",
    "I004": "지분공시",
    "I005": "증권투자회사",
    "I006": "채권공시",
    "J001": "대규모내부거래관련",
    "J002": "대규모내부거래관련(구)",
    "J004": "기업집단현황공시",
    "J005": "비상장회사중요사항공시",
    "J006": "기타공정위공시",
}


# 상장시장 구분 (corp_cls)
CORP_CLASS: Dict[str, str] = {
    "Y": "유가증권",
    "K": "코스",
    "N": "코넥스",
    "E": "etc",
}

# 비고/주석 코드 (rm)
REMARK_CODES: Dict[str, str] = {
    "유": "본 공시사항은 한국거래소 유가증권시장본부 소관임",
    "코": "본 공시사항은 한국거래소 코스닥시장본부 소관임",
    "채": "본 문서는 한국거래소 채권상장법인 공시사항임",
    "넥": "본 문서는 한국거래소 코넥스시장 소관임",
    "공": "본 공시사항은 공정거래위원회 소관임",
    "연": "본 보고서는 연결부분을 포함한 것임",
    "정": "본 보고서 제출 후 정정신고가 있으니 관련 보고서를 참조하시기 바람",
    "철": "본 보고서는 철회(간주)되었으니 관련 철회신고서(철회간주안내)를 참고하시기 바람",
}


# ==================== 헬퍼 ==================== #

def _json(data: Any) -> str:
    try:
        # pandas.DataFrame 대응: to_dict('records') 보존
        if hasattr(data, "to_dict") and hasattr(data, "empty"):
            if data.empty:  # type: ignore[attr-defined]
                return json.dumps({"result": "데이터가 없습니다."}, ensure_ascii=False)
            return json.dumps(data.to_dict("records"), ensure_ascii=False, default=str)
        if data is None:
            return json.dumps({"result": "데이터가 없습니다."}, ensure_ascii=False)
        return json.dumps(data, ensure_ascii=False, default=str)
    except Exception as exc:  # pragma: no cover
        return json.dumps({"error": f"직렬화 오류: {exc}"}, ensure_ascii=False)


def _require_client() -> Optional[str]:
    if _dart is None:
        return _json({"error": "DART API가 초기화되지 않았습니다."})
    return None


def _validate_non_empty(text: str, field: str) -> Optional[str]:
    if not text or not text.strip():
        return _json({"error": f"{field}을(를) 입력해주세요."})
    return None


# 날짜 유틸
def _parse_ymd(text: Optional[str]) -> Optional[date]:
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except Exception:
        return None


def _format_ymd(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _add_months(d: date, months: int) -> date:
    # 달 추가 (월 말 보정)
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    # 해당 월의 마지막 날 계산
    first_next_month = date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
    last_day = (first_next_month - timedelta(days=1)).day
    day = min(d.day, last_day)
    return date(y, m, day)


def _split_into_3month_windows(start_text: str, end_text: str) -> List[Dict[str, str]]:
    start_d = _parse_ymd(start_text)
    end_d = _parse_ymd(end_text)
    if start_d is None or end_d is None or start_d > end_d:
        return []

    windows: List[Dict[str, str]] = []
    current_start = start_d
    while current_start <= end_d:
        # 3개월 범위의 마지막 날짜는 (start + 3개월 - 1일)
        tentative_end = _add_months(current_start, 3) - timedelta(days=1)
        current_end = tentative_end if tentative_end <= end_d else end_d
        windows.append({
            "start": _format_ymd(current_start),
            "end": _format_ymd(current_end),
        })
        # 다음 창의 시작은 직전 창의 다음 날
        next_start = current_end + timedelta(days=1)
        if next_start > end_d:
            break
        current_start = next_start
    return windows


    # no-op


# ==================== 1) 기업/공시 검색 ==================== #

def list_company_disclosures(
    company: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    disclosure_kind: Optional[str] = None,
    disclosure_kind_detail: Optional[str] = None,
    final_only: bool = True,
) -> str:
    """
    특정 기업 또는 전체 대상의 공시 목록을 조회합니다.

    LLM-first 사용 지침:
        - 사용자가 자연어로 문서유형을 말한 경우, 먼저 get_supported_codes('disclosure_kind_details')로 코드표를 조회한 후,
          해당 코드를 disclosure_kind_detail에 입력하세요. 대분류만 필요한 경우에는 'disclosure_kinds'를 조회합니다.
        - 불명확하면 1문장으로 명확화 질문을 한 뒤 재시도합니다.

    Args:
        company (str | None): 기업명 또는 종목코드. 미지정 시 전체 공시를 조회합니다.
        start_date (str | None): 시작일자. 형식: YYYY-MM-DD.
        end_date (str | None): 종료일자. 형식: YYYY-MM-DD.
        disclosure_kind (str | None): 공시 종류 코드. 반드시 DISCLOSURE_KINDS의 키 중 하나여야 함.
            - 허용 코드: A,B,C,D,E,F,G,H,I,J (예: A=정기공시)
        disclosure_kind_detail (str | None): 공시 상세유형 코드. 반드시 DISCLOSURE_KIND_DETAILS의 키 중 하나여야 함.
            - 예: A001=사업보고서, B001=주요사항보고서, E004=주식매수선택권부여에관한신고
        final_only (bool): 최종보고서만 조회할지 여부. True면 정정보고 제외.

    Returns:
        str: JSON 문자열. 성공 시 목록 데이터, 실패 시 에러 메시지.
    """
    err = _require_client()
    if err:
        return err

    try:
        kwargs: Dict[str, Any] = {}
        if start_date:
            kwargs["start"] = start_date
        if end_date:
            kwargs["end"] = end_date

        # 상세유형 우선 -> kind_detail, 없으면 kind (코드만 허용)
        if disclosure_kind_detail:
            if not all(code.strip() in DISCLOSURE_KIND_DETAILS for code in str(disclosure_kind_detail).split(",")):
                return _json({
                    "error": f"올바르지 않은 공시 상세유형 코드: {disclosure_kind_detail}",
                    "allowed_detail_codes": list(DISCLOSURE_KIND_DETAILS.keys()),
                    "hint": "먼저 get_supported_codes('disclosure_kind_details')로 코드표를 확인하세요.",
                })
            kwargs["kind_detail"] = disclosure_kind_detail
        elif disclosure_kind:
            if disclosure_kind not in DISCLOSURE_KINDS:
                return _json({
                    "error": f"올바르지 않은 공시 종류 코드: {disclosure_kind}",
                    "allowed_kinds": list(DISCLOSURE_KINDS.keys()),
                    "hint": "먼저 get_supported_codes('disclosure_kinds')로 코드표를 확인하세요.",
                })
            kwargs["kind"] = disclosure_kind

        kwargs["final"] = final_only

        # 회사 미지정 + 3개월 초과 기간인 경우: 3개월 단위 분할 조회
        start_d = _parse_ymd(start_date) if start_date else None
        end_d = _parse_ymd(end_date) if end_date else None
        if not company and start_d and end_d and _add_months(start_d, 3) <= end_d:
            windows = _split_into_3month_windows(start_date, end_date)
            all_items: List[Any] = []
            for w in windows:
                local_kwargs = dict(kwargs)
                local_kwargs["start"] = w["start"]
                local_kwargs["end"] = w["end"]
                chunk_res = _dart.list(**local_kwargs)  # type: ignore[operator]
                parsed = json.loads(_json(chunk_res))
                if isinstance(parsed, list):
                    all_items.extend(parsed)
            return _json(all_items)

        # 기본 경로: 단건 호출
        if company:
            res = _dart.list(company, **kwargs)  # type: ignore[operator]
        else:
            res = _dart.list(**kwargs)  # type: ignore[operator]
        return _json(res)
    except Exception as exc:
        return _json({"error": f"list_company_disclosures 오류: {exc}"})


def get_company_overview(company: str) -> str:
    """
    기업 개황 정보를 조회합니다.

    Args:
        company (str): 기업명 또는 종목코드. 예: '삼성전자', '005930'.

    Returns:
        str: JSON 문자열. 기업 기본정보 레코드.
    """
    err = _require_client()
    if err:
        return err
    empty = _validate_non_empty(company, "기업명 또는 종목코드")
    if empty:
        return empty
    try:
        res = _dart.company(company.strip())  # type: ignore[operator]
        return _json(res)
    except Exception as exc:
        return _json({"error": f"get_company_overview 오류: {exc}"})


def search_companies(company_name: str) -> str:
    """
    회사명(부분 일치)으로 기업을 검색합니다.

    Args:
        company_name (str): 검색어. 부분 일치 허용.

    Returns:
        str: JSON 문자열. 검색 결과 목록.
    """
    err = _require_client()
    if err:
        return err
    empty = _validate_non_empty(company_name, "회사명")
    if empty:
        return empty
    try:
        res = _dart.company_by_name(company_name.strip())  # type: ignore[operator]
        return _json(res)
    except Exception as exc:
        return _json({"error": f"search_companies 오류: {exc}"})


def resolve_corp_code(company: str) -> str:
    """
    기업명/종목코드로 DART 고유번호(corp_code)를 조회합니다.

    Args:
        company (str): 기업명 또는 종목코드.

    Returns:
        str: JSON 문자열. 예: {"corp_code": "00126380", ...} 형태.
    """
    err = _require_client()
    if err:
        return err
    empty = _validate_non_empty(company, "기업명 또는 종목코드")
    if empty:
        return empty
    try:
        res = _dart.find_corp_code(company.strip())  # type: ignore[operator]
        return _json(res)
    except Exception as exc:
        return _json({"error": f"resolve_corp_code 오류: {exc}"})


# ==================== 2) 문서 원본/첨부 ==================== #

def get_document_html(rcp_no: str, include_all: bool = False) -> str:
    """
    공시서류 원본 HTML을 조회합니다.

    Args:
        rcp_no (str): 접수번호. 예: '20220308000798'.
        include_all (bool): True면 document_all로 모든 문서 섹션을 포함.

    Returns:
        str: JSON 문자열. {"content": "..."} 또는 {"document_1": "...", ...}.
    """
    err = _require_client()
    if err:
        return err
    empty = _validate_non_empty(rcp_no, "접수번호")
    if empty:
        return empty
    try:
        if include_all:
            docs = _dart.document_all(rcp_no.strip())  # type: ignore[operator]
            payload: Dict[str, Any] = {}
            for idx, html in enumerate(docs):
                payload[f"document_{idx+1}"] = html
            return _json(payload)
        html = _dart.document(rcp_no.strip())  # type: ignore[operator]
        return _json({"content": html})
    except Exception as exc:
        return _json({"error": f"get_document_html 오류: {exc}"})


def list_attached_documents(
    rcp_no: str,
    title_match: Optional[str] = None,
    mode: str = "list",
) -> str:
    """
    첨부 문서 메타/목록/파일 정보를 조회합니다.

    Args:
        rcp_no (str): 접수번호. 형식: 14자리 숫자 문자열.
        title_match (str | None): 제목 키워드 필터. None이면 전체.
        mode (str): 'list'|'docs'|'files' 중 하나. 'list'는 attach_doc_list, 'docs'는 attach_docs, 'files'는 attach_files를 호출.

    Returns:
        str: JSON 문자열. 목록 또는 파일 메타정보.
    """
    err = _require_client()
    if err:
        return err
    empty = _validate_non_empty(rcp_no, "접수번호")
    if empty:
        return empty
    try:
        mode_norm = (mode or "list").lower()
        if mode_norm == "files" and hasattr(_dart, "attach_files"):
            res = _dart.attach_files(rcp_no.strip())  # type: ignore[operator]
            return _json(res)
        if mode_norm == "docs" and hasattr(_dart, "attach_docs"):
            if title_match:
                res = _dart.attach_docs(rcp_no.strip(), match=title_match)  # type: ignore[operator]
            else:
                res = _dart.attach_docs(rcp_no.strip())  # type: ignore[operator]
            return _json(res)
        # default: list
        if hasattr(_dart, "attach_doc_list"):
            if title_match:
                res = _dart.attach_doc_list(rcp_no.strip(), match=title_match)  # type: ignore[operator]
            else:
                res = _dart.attach_doc_list(rcp_no.strip())  # type: ignore[operator]
            return _json(res)
        return _json({"error": "해당 모드가 지원되지 않거나 OpenDartReader 버전이 호환되지 않습니다."})
    except Exception as exc:
        return _json({"error": f"list_attached_documents 오류: {exc}"})


# ==================== 3) 재무/XBRL/사업보고 ==================== #

def get_financial_statements(
    company: str,
    year: int,
    report_code: str = "11011",
    include_comprehensive: bool = False,
) -> str:
    """
    재무제표(연간/분기)를 조회합니다. 여러 기업은 콤마로 연결하여 입력 가능합니다.

    Args:
        company (str): 기업명/종목코드 또는 콤마구분 다중 입력. 예: '005930,000660'.
        year (int): 조회 연도. 1990 이상, 현재 연도 이하.
        report_code (str): 보고서 코드. 반드시 {'11011','11012','11013','11014'} 중 하나.
        include_comprehensive (bool): True면 포괄적 재무제표 API(finstate_all) 사용.

    Returns:
        str: JSON 문자열. 표준화된 레코드 목록.
    """
    err = _require_client()
    if err:
        return err
    empty = _validate_non_empty(company, "기업명/종목코드")
    if empty:
        return empty
    try:
        if year < 1990 or year > datetime.now().year:
            return _json({"error": f"올바르지 않은 연도: {year}"})
        if not include_comprehensive and report_code not in REPORT_CODES:
            return _json({
                "error": f"올바르지 않은 보고서 코드: {report_code}",
                "allowed_codes": list(REPORT_CODES.keys()),
            })
        company_norm = ",".join([c.strip() for c in str(company).split(",") if c.strip()])
        if include_comprehensive:
            res = _dart.finstate_all(company_norm, year)  # type: ignore[operator]
        else:
            res = _dart.finstate(company_norm, year, reprt_code=report_code)  # type: ignore[operator]
        return _json(res)
    except Exception as exc:
        return _json({"error": f"get_financial_statements 오류: {exc}"})


def get_xbrl_taxonomy(classification: str) -> str:
    """
    XBRL 표준계정과목체계 분류 항목을 조회합니다.

    Args:
        classification (str): XBRL 분류 코드. 반드시 {'BS1','IS1','CIS1','CF1','SCE1'} 중 하나.

    Returns:
        str: JSON 문자열. 계정과목 목록.
    """
    err = _require_client()
    if err:
        return err
    empty = _validate_non_empty(classification, "분류 코드")
    if empty:
        return empty
    try:
        if classification not in XBRL_CLASSIFICATIONS:
            return _json({
                "error": f"올바르지 않은 분류 코드: {classification}",
                "allowed_codes": list(XBRL_CLASSIFICATIONS.keys()),
            })
        res = _dart.xbrl_taxonomy(classification)  # type: ignore[operator]
        return _json(res)
    except Exception as exc:
        return _json({"error": f"get_xbrl_taxonomy 오류: {exc}"})


def get_business_report_item(company: str, item_type: str, year: int) -> str:
    """
    사업보고서의 특정 항목을 조회합니다.

    Args:
        company (str): 기업명 또는 종목코드.
        item_type (str): 항목명. 예: '배당','임원','직원','주식총수' 등 OpenDartReader가 지원하는 텍스트 키.
        year (int): 조회 연도. 1990 이상, 현재 연도 이하.

    Returns:
        str: JSON 문자열. 항목 데이터.
    """
    err = _require_client()
    if err:
        return err
    if (msg := _validate_non_empty(company, "기업명 또는 종목코드")):
        return msg
    if year < 1990 or year > datetime.now().year:
        return _json({"error": f"올바르지 않은 연도: {year}"})
    try:
        res = _dart.report(company.strip(), item_type, year)  # type: ignore[operator]
        return _json(res)
    except Exception as exc:
        return _json({"error": f"get_business_report_item 오류: {exc}"})


# ==================== 4) 지분/주요사항/증권신고 ==================== #

def get_shareholding_reports(company: str, report_type: str = "major") -> str:
    """
    지분 관련 보고를 조회합니다.

    Args:
        company (str): 기업명 또는 종목코드.
        report_type (str): 'major' 또는 'executive'. 'major'는 대량보유상황보고, 'executive'는 임원·주요주주소유보고.

    Returns:
        str: JSON 문자열. 보고 데이터.
    """
    err = _require_client()
    if err:
        return err
    if (msg := _validate_non_empty(company, "기업명 또는 종목코드")):
        return msg
    if report_type not in {"major", "executive"}:
        return _json({"error": f"올바르지 않은 report_type: {report_type}", "allowed": ["major", "executive"]})
    try:
        if report_type == "executive":
            res = _dart.major_shareholders_exec(company.strip())  # type: ignore[operator]
        else:
            res = _dart.major_shareholders(company.strip())  # type: ignore[operator]
        return _json(res)
    except Exception as exc:
        return _json({"error": f"get_shareholding_reports 오류: {exc}"})


def get_major_event_reports(
    company: str,
    event_type: str,
    start_year: Optional[str] = None,
    end_year: Optional[str] = None,
) -> str:
    """
    주요사항보고서(합병, 소송, 증자 등)를 조회합니다.

    Args:
        company (str): 기업명 또는 종목코드.
        event_type (str): 주요사항 종류. 반드시 MAJOR_EVENT_TYPES 목록 중 하나.
            - 허용 예시: '회사합병','소송','유상증자','자산양수도' 등. 전체 목록은 get_supported_codes('major_event_types')로 조회 가능.
        start_year (str | None): 시작 연도(YYYY). 선택.
        end_year (str | None): 종료 연도(YYYY). 선택.

    Returns:
        str: JSON 문자열. 보고 데이터.
    """
    err = _require_client()
    if err:
        return err
    if (msg := _validate_non_empty(company, "기업명 또는 종목코드")):
        return msg
    if event_type not in MAJOR_EVENT_TYPES:
        return _json({"error": f"올바르지 않은 주요사항 종류: {event_type}", "allowed": MAJOR_EVENT_TYPES})
    try:
        kwargs: Dict[str, Any] = {}
        if start_year:
            kwargs["start"] = start_year
        if end_year:
            kwargs["end"] = end_year
        res = _dart.event(company.strip(), event_type, **kwargs)  # type: ignore[operator]
        return _json(res)
    except Exception as exc:
        return _json({"error": f"get_major_event_reports 오류: {exc}"})


def get_securities_registration(
    company: str,
    registration_type: str,
    start_year: Optional[str] = None,
    end_year: Optional[str] = None,
) -> str:
    """
    증권신고서(합병/분할/지분증권 등)를 조회합니다.

    Args:
        company (str): 기업명 또는 종목코드.
        registration_type (str): 신고 유형. 반드시 SECURITIES_TYPES 목록 중 하나.
            - 허용 예시: '합병','분할','지분증권','채무증권','증권예탁증권','주식의포괄적교환이전'.
        start_year (str | None): 시작 연도(YYYY). 선택.
        end_year (str | None): 종료 연도(YYYY). 선택.

    Returns:
        str: JSON 문자열. 신고 데이터.
    """
    err = _require_client()
    if err:
        return err
    if (msg := _validate_non_empty(company, "기업명 또는 종목코드")):
        return msg
    if registration_type not in SECURITIES_TYPES:
        return _json({"error": f"올바르지 않은 신고 유형: {registration_type}", "allowed": SECURITIES_TYPES})
    try:
        kwargs: Dict[str, Any] = {}
        if start_year:
            kwargs["start"] = start_year
        if end_year:
            kwargs["end"] = end_year
        res = _dart.regstate(company.strip(), registration_type, **kwargs)  # type: ignore[operator]
        return _json(res)
    except Exception as exc:
        return _json({"error": f"get_securities_registration 오류: {exc}"})


# ==================== 5) 옵션 조회 ==================== #

def get_supported_codes(code_type: str) -> str:
    """
    지원되는 코드 테이블을 조회합니다.

    Args:
        code_type (str): 'disclosure_kinds'|'report_codes'|'xbrl_classifications'|'major_event_types'|'securities_types' 중 하나.

    Returns:
        str: JSON 문자열. 코드 테이블 또는 오류.
    """
    mapping: Dict[str, Any] = {
        "disclosure_kinds": DISCLOSURE_KINDS,
        "disclosure_kind_details": DISCLOSURE_KIND_DETAILS,
        "report_codes": REPORT_CODES,
        "xbrl_classifications": XBRL_CLASSIFICATIONS,
        "major_event_types": MAJOR_EVENT_TYPES,
        "securities_types": SECURITIES_TYPES,
        "corp_class": CORP_CLASS,
        "remark_codes": REMARK_CODES,
    }
    data = mapping.get(code_type)
    if data is None:
        return _json({
            "error": f"올바르지 않은 code_type: {code_type}",
            "allowed": list(mapping.keys()),
        })
    return _json({"code_type": code_type, "values": data})


__all__ = [
    "list_company_disclosures",
    "get_company_overview",
    "search_companies",
    "resolve_corp_code",
    "get_document_html",
    "list_attached_documents",
    "get_financial_statements",
    "get_xbrl_taxonomy",
    "get_business_report_item",
    "get_shareholding_reports",
    "get_major_event_reports",
    "get_securities_registration",
    "get_supported_codes",
]


def register_tools(mcp: FastMCP) -> None:
    """
    이 모듈의 모든 OpenDartReader 래퍼 함수를 MCP에 등록합니다.

    Args:
        mcp (FastMCP): MCP 서버 인스턴스. fastmcp의 `mcp.tool` 데코레이터를 사용합니다.

    등록되는 도구와 설명:
        - list_company_disclosures: 특정 기업/전체 공시 목록 검색. 기간/종류/상세유형/최종 여부 지정.
        - get_company_overview: 기업 개황 정보 조회.
        - search_companies: 회사명(부분 일치)으로 기업 검색.
        - resolve_corp_code: 기업명/종목코드로 DART 고유번호(corp_code) 조회.
        - get_document_html: 공시서류 원본 HTML 조회(단일/전체).
        - list_attached_documents: 첨부 문서 목록/문서/파일 메타 조회.
        - get_financial_statements: 재무제표 조회(연/분기, 포괄선택, 보고서 코드 검증).
        - get_xbrl_taxonomy: XBRL 분류별 계정과목(표준계정체계) 조회.
        - get_business_report_item: 사업보고서 내 특정 항목 데이터 조회.
        - get_shareholding_reports: 지분 관련 보고(대량보유/임원·주요주주) 조회.
        - get_major_event_reports: 주요사항보고서(합병/소송/증자 등) 조회.
        - get_securities_registration: 증권신고서(합병/분할/증권유형) 조회.
        - get_supported_codes: 지원 코드 테이블 조회(분류/상세/보고서/XBRL/이벤트/시장/비고).
    """
    if mcp is None:
        return

    # 도구 등록 (각 설명은 의도를 한 문장으로, 입력 제약은 함수 Docstring으로 관리)
    mcp.tool(
        name="list_company_disclosures",
        description="특정 기업 또는 전체 대상의 공시 목록을 검색합니다. 기간/종류/상세유형/최종 여부를 지정할 수 있습니다. 자연어 문서유형인 경우 반드시 get_supported_codes('disclosure_kind_details')로 코드 확인 후 'disclosure_kind_detail'에 코드를 입력하세요 (예: '주식매수선택권' → E004)."
    )(list_company_disclosures)

    mcp.tool(
        name="get_company_overview",
        description="기업 개황 정보를 조회합니다. 기업명 또는 종목코드를 입력합니다."
    )(get_company_overview)

    mcp.tool(
        name="search_companies",
        description="회사명(부분 일치)으로 기업을 검색합니다."
    )(search_companies)

    mcp.tool(
        name="resolve_corp_code",
        description="기업명/종목코드로 DART 고유번호(corp_code)를 조회합니다."
    )(resolve_corp_code)

    mcp.tool(
        name="get_document_html",
        description="공시서류 원본 HTML을 조회합니다. 단일 또는 전체 섹션을 선택할 수 있습니다."
    )(get_document_html)

    mcp.tool(
        name="list_attached_documents",
        description="첨부 문서의 목록/문서/파일 메타를 조회합니다. 제목 키워드로 필터링할 수 있습니다."
    )(list_attached_documents)

    mcp.tool(
        name="get_financial_statements",
        description="재무제표를 조회합니다. 다중 기업, 연도, 보고서 코드, 포괄 여부를 지원합니다."
    )(get_financial_statements)

    mcp.tool(
        name="get_xbrl_taxonomy",
        description="XBRL 분류(BS1/IS1/CIS1/CF1/SCE1)별 표준계정과목을 조회합니다."
    )(get_xbrl_taxonomy)

    mcp.tool(
        name="get_business_report_item",
        description="사업보고서의 특정 항목 데이터를 조회합니다. (예: 배당/임원/직원/주식총수)"
    )(get_business_report_item)

    mcp.tool(
        name="get_shareholding_reports",
        description="지분 관련 보고를 조회합니다. (대량보유상황/임원·주요주주)"
    )(get_shareholding_reports)

    mcp.tool(
        name="get_major_event_reports",
        description="주요사항보고서를 조회합니다. (합병/소송/증자 등 유형 지정)"
    )(get_major_event_reports)

    mcp.tool(
        name="get_securities_registration",
        description="증권신고서를 조회합니다. (합병/분할/지분·채무·예탁증권 등)"
    )(get_securities_registration)

    mcp.tool(
        name="get_supported_codes",
        description="지원되는 코드 테이블을 조회합니다. (공시종류/상세/보고서/XBRL/이벤트/시장/비고)"
    )(get_supported_codes)
