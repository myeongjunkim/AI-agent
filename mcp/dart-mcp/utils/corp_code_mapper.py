"""
기업명/종목코드 매퍼
기업명과 종목코드, DART 기업코드 간 변환을 담당
"""

import re
from typing import Optional, List, Dict, Any
import json


class CorpCodeMapper:
    """기업 코드 매핑 관리"""
    
    def __init__(self, dart_reader=None):
        """
        Args:
            dart_reader: OpenDartReader 인스턴스
        """
        self.dart_reader = dart_reader
        self._cache = {}
        
    async def get_corp_code(self, company: str) -> Optional[str]:
        """
        기업명 또는 종목코드로 DART 기업코드(corp_code) 조회
        
        Args:
            company: 기업명 또는 종목코드
            
        Returns:
            DART 기업코드 또는 None
        """
        if not company:
            return None
            
        # 캐시 확인
        if company in self._cache:
            return self._cache[company]
        
        if not self.dart_reader:
            return None
            
        try:
            # OpenDartReader의 find_corp_code 메서드 사용
            # 이 메서드는 corp_code를 문자열로 직접 반환
            result = self.dart_reader.find_corp_code(company)
            
            if result is not None and isinstance(result, str):
                self._cache[company] = result
                return result
                        
        except Exception as e:
            # 오류 발생시 None 반환
            pass
            
        return None
    
    async def get_company_info(self, company: str) -> Optional[Dict[str, Any]]:
        """
        기업 정보 조회
        
        Args:
            company: 기업명 또는 종목코드
            
        Returns:
            기업 정보 딕셔너리
        """
        if not self.dart_reader:
            return None
            
        try:
            result = self.dart_reader.company(company)
            
            if result is not None and hasattr(result, 'to_dict'):
                return result.to_dict('records')[0] if not result.empty else None
                
        except Exception:
            pass
            
        return None
    
    def extract_companies_from_query(self, query: str) -> List[str]:
        """
        쿼리에서 기업명/종목코드 추출
        
        Args:
            query: 사용자 쿼리
            
        Returns:
            기업명/종목코드 리스트
        """
        companies = []
        
        # 종목코드 패턴 (6자리 숫자)
        stock_codes = re.findall(r'\b\d{6}\b', query)
        companies.extend(stock_codes)
        
        # 주요 기업명 패턴
        # 알려진 대기업들 (확장 가능)
        known_companies = [
            "삼성전자", "SK하이닉스", "LG전자", "현대차", "현대자동차", "기아",
            "네이버", "카카오", "쿠팡", "배달의민족", "우아한형제들",
            "포스코", "POSCO", "현대제철", "롯데케미칼",
            "삼성물산", "삼성생명", "삼성화재", "삼성증권", "삼성카드",
            "LG화학", "LG디스플레이", "LG이노텍", "LG유플러스",
            "SK텔레콤", "SKT", "SK이노베이션", "SK에너지",
            "한국전력", "한전", "KT", "케이티",
            "현대건설", "대우건설", "GS건설",
            "신한은행", "국민은행", "우리은행", "하나은행", "기업은행",
            "삼성바이오로직스", "셀트리온", "한미약품",
            "대한항공", "아시아나항공", "제주항공",
            "CJ제일제당", "CJ ENM", "CJ대한통운",
            "아모레퍼시픽", "LG생활건강",
            "현대모비스", "한국타이어", "현대위아",
            "두산", "두산중공업", "두산인프라코어",
            "한화", "한화솔루션", "한화에어로스페이스",
            "엔씨소프트", "넥슨", "넷마블", "크래프톤", "펄어비스",
            "현대중공업", "삼성중공업", "대우조선해양",
            "SK바이오팜", "SK바이오사이언스",
            "카카오뱅크", "카카오페이", "토스", "비바리퍼블리카"
        ]
        
        # 쿼리를 소문자로 변환하여 비교
        query_lower = query.lower()
        
        # 정확한 매칭 먼저
        for company in known_companies:
            if company.lower() in query_lower:
                companies.append(company)
        
        # 부분 매칭 추가 (쿼리의 일부가 회사명에 포함되는 경우)
        # 예: "SK하이닉" -> "SK하이닉스"
        if not companies:  # 정확한 매칭이 없을 때만
            words = query.split()
            for word in words:
                if len(word) >= 2:  # 2글자 이상인 단어만
                    for company in known_companies:
                        if word.lower() in company.lower() and len(word) >= len(company) * 0.6:
                            # 단어가 회사명의 60% 이상을 차지하면 매칭
                            if company not in companies:
                                companies.append(company)
        
        # 기업명 패턴 (한글 2자 이상 + 선택적으로 영문/숫자)
        # "OO전자", "OO화학" 등의 패턴
        company_patterns = [
            r'[가-힣]+(?:전자|화학|제약|바이오|엔터|건설|중공업|자동차|은행|증권|생명|화재|카드)',
            r'[가-힣]+(?:케미칼|케미컬|에너지|모빌리티|솔루션)',
            r'[가-힣]+(?:홀딩스|그룹|지주)',
        ]
        
        for pattern in company_patterns:
            matches = re.findall(pattern, query)
            companies.extend(matches)
        
        # 중복 제거 및 반환
        return list(set(companies))
    
    async def validate_company(self, company: str) -> bool:
        """
        기업명/종목코드가 유효한지 확인
        
        Args:
            company: 기업명 또는 종목코드
            
        Returns:
            유효 여부
        """
        corp_code = await self.get_corp_code(company)
        return corp_code is not None
    
    def is_stock_code(self, text: str) -> bool:
        """
        문자열이 종목코드 형식인지 확인
        
        Args:
            text: 검사할 문자열
            
        Returns:
            종목코드 형식 여부
        """
        return bool(re.match(r'^\d{6}$', text))
    
    async def search_companies(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        키워드로 기업 검색
        
        Args:
            keyword: 검색 키워드
            limit: 최대 결과 수
            
        Returns:
            기업 정보 리스트
        """
        if not self.dart_reader:
            return []
            
        try:
            result = self.dart_reader.company_by_name(keyword)
            
            if result is not None and hasattr(result, 'to_dict'):
                companies = result.to_dict('records')
                return companies[:limit]
                
        except Exception:
            pass
            
        return []