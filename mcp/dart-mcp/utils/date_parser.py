"""
날짜 표현 파서
사용자의 자연어 날짜 표현을 DART API 형식(YYYYMMDD)으로 변환
"""

from datetime import datetime, timedelta
from typing import Tuple, Optional
import re


def parse_date_expression(expr: str) -> Tuple[str, str]:
    """
    날짜 표현을 DART API 형식으로 변환
    
    Args:
        expr: 사용자 쿼리 문자열
        
    Returns:
        (시작일, 종료일) 튜플 (YYYYMMDD 형식)
    """
    today = datetime.now()
    
    # 기본값: 최근 1개월
    default_start = today - timedelta(days=30)
    default_end = today
    
    # 날짜 패턴 매칭
    patterns = {
        r"최근\s*(\d+)\s*년": lambda m: (today - timedelta(days=365 * int(m.group(1))), today),
        r"최근\s*(\d+)\s*개월": lambda m: (today - timedelta(days=30 * int(m.group(1))), today),
        r"최근\s*(\d+)\s*주": lambda m: (today - timedelta(weeks=int(m.group(1))), today),
        r"최근\s*(\d+)\s*일": lambda m: (today - timedelta(days=int(m.group(1))), today),
        r"올해": lambda m: (datetime(today.year, 1, 1), today),
        r"작년": lambda m: (datetime(today.year - 1, 1, 1), datetime(today.year - 1, 12, 31)),
        r"(\d{4})\s*년": lambda m: (datetime(int(m.group(1)), 1, 1), datetime(int(m.group(1)), 12, 31)),
        r"(\d{4})\s*년\s*(\d{1,2})\s*월": lambda m: get_month_range(int(m.group(1)), int(m.group(2))),
        r"(\d{4})[.-](\d{1,2})[.-](\d{1,2})": lambda m: parse_specific_date(m.group(0)),
    }
    
    for pattern, handler in patterns.items():
        match = re.search(pattern, expr)
        if match:
            try:
                start, end = handler(match)
                return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
            except:
                continue
    
    # 특별 키워드 처리
    if "지난달" in expr or "전월" in expr:
        last_month = today.replace(day=1) - timedelta(days=1)
        start = last_month.replace(day=1)
        end = last_month
        return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    
    if "이번달" in expr or "당월" in expr:
        start = today.replace(day=1)
        return start.strftime("%Y%m%d"), today.strftime("%Y%m%d")
    
    if "어제" in expr:
        yesterday = today - timedelta(days=1)
        return yesterday.strftime("%Y%m%d"), yesterday.strftime("%Y%m%d")
    
    if "오늘" in expr:
        return today.strftime("%Y%m%d"), today.strftime("%Y%m%d")
    
    # 분기 처리
    quarter_match = re.search(r"(\d{4})\s*년\s*(\d)\s*분기", expr)
    if not quarter_match:
        quarter_match = re.search(r"(\d)\s*분기", expr)
        if quarter_match:
            year = today.year
            quarter = int(quarter_match.group(1))
        else:
            year = None
            quarter = None
    else:
        year = int(quarter_match.group(1))
        quarter = int(quarter_match.group(2))
    
    if quarter:
        start, end = get_quarter_range(year if year else today.year, quarter)
        return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    
    # 기본값 반환
    return default_start.strftime("%Y%m%d"), default_end.strftime("%Y%m%d")


def get_month_range(year: int, month: int) -> Tuple[datetime, datetime]:
    """특정 년월의 시작일과 종료일 반환"""
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year, 12, 31)
    else:
        end = datetime(year, month + 1, 1) - timedelta(days=1)
    return start, end


def get_quarter_range(year: int, quarter: int) -> Tuple[datetime, datetime]:
    """특정 분기의 시작일과 종료일 반환"""
    quarter_months = {
        1: (1, 3),
        2: (4, 6),
        3: (7, 9),
        4: (10, 12)
    }
    
    if quarter not in quarter_months:
        raise ValueError(f"Invalid quarter: {quarter}")
    
    start_month, end_month = quarter_months[quarter]
    start = datetime(year, start_month, 1)
    
    if end_month == 12:
        end = datetime(year, 12, 31)
    else:
        end = datetime(year, end_month + 1, 1) - timedelta(days=1)
    
    return start, end


def parse_specific_date(date_str: str) -> Tuple[datetime, datetime]:
    """특정 날짜 문자열을 파싱"""
    for fmt in ["%Y-%m-%d", "%Y.%m.%d", "%Y%m%d"]:
        try:
            date = datetime.strptime(date_str.replace(".", "-"), fmt)
            return date, date
        except:
            continue
    raise ValueError(f"Cannot parse date: {date_str}")


def extract_date_range_from_query(query: str) -> Optional[Tuple[str, str]]:
    """
    쿼리에서 날짜 범위를 추출하여 DART API 형식으로 반환
    
    Args:
        query: 사용자 쿼리
        
    Returns:
        (시작일, 종료일) 또는 None
    """
    # 명시적 날짜 범위 패턴
    range_pattern = r"(\d{4}[.-]\d{1,2}[.-]\d{1,2})\s*[~-]\s*(\d{4}[.-]\d{1,2}[.-]\d{1,2})"
    match = re.search(range_pattern, query)
    
    if match:
        try:
            start_str = match.group(1).replace(".", "-")
            end_str = match.group(2).replace(".", "-")
            
            start = datetime.strptime(start_str, "%Y-%m-%d")
            end = datetime.strptime(end_str, "%Y-%m-%d")
            
            return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
        except:
            pass
    
    # 일반 날짜 표현 파싱
    return parse_date_expression(query)