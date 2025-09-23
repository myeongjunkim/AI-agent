"""
기업명 검증 도구 (간소화 버전)
thefuzz를 활용한 퍼지 매칭
"""

from typing import List, Dict, Any, Optional
from thefuzz import fuzz, process


class CompanyValidator:
    """기업명 검증 및 후보 추천 (간소화)"""
    
    def __init__(self, dart_reader=None):
        """
        Args:
            dart_reader: OpenDartReader 인스턴스
        """
        self.dart_reader = dart_reader
        self._company_list = []  # 기업명 리스트
        self._company_map = {}  # 기업명 -> (corp_code, stock_code) 매핑
        self._initialize_corp_data()
    
    def _initialize_corp_data(self):
        """기업 데이터 초기화"""
        if self.dart_reader and hasattr(self.dart_reader, 'corp_codes'):
            corp_df = self.dart_reader.corp_codes
            
            for _, row in corp_df.iterrows():
                corp_name = row['corp_name']
                corp_code = row['corp_code']
                stock_code = row.get('stock_code', '')
                
                self._company_list.append(corp_name)
                self._company_map[corp_name] = {
                    'corp_code': corp_code,
                    'stock_code': stock_code
                }
    
    def find_company(self, query: str, threshold: int = 70) -> Dict[str, Any]:
        """
        기업명 검색 및 검증
        
        Args:
            query: 검색할 기업명
            threshold: 최소 유사도 임계값 (0-100)
            
        Returns:
            {
                "status": "exact" | "fuzzy" | "multiple" | "not_found",
                "company": str or None,  # 매칭된 기업명
                "corp_code": str or None,
                "score": int,  # 유사도 점수 (0-100)
                "candidates": List[Dict],  # 후보 리스트
                "needs_confirmation": bool
            }
        """
        if not query or not self._company_list:
            return {
                "status": "not_found",
                "company": None,
                "corp_code": None,
                "score": 0,
                "candidates": [],
                "needs_confirmation": False
            }
        
        # 정확한 매칭 먼저 확인
        if query in self._company_map:
            return {
                "status": "exact",
                "company": query,
                "corp_code": self._company_map[query]['corp_code'],
                "score": 100,
                "candidates": [{"name": query, "score": 100}],
                "needs_confirmation": False
            }
        
        # 퍼지 매칭으로 상위 5개 후보 찾기
        matches = process.extract(query, self._company_list, scorer=fuzz.ratio, limit=5)
        
        if not matches:
            return {
                "status": "not_found",
                "company": None,
                "corp_code": None,
                "score": 0,
                "candidates": [],
                "needs_confirmation": False
            }
        
        # 후보 리스트 생성
        candidates = []
        for match_name, score in matches:
            if score >= threshold:
                candidates.append({
                    "name": match_name,
                    "corp_code": self._company_map[match_name]['corp_code'],
                    "score": score
                })
        
        if not candidates:
            return {
                "status": "not_found",
                "company": None,
                "corp_code": None,
                "score": matches[0][1] if matches else 0,
                "candidates": [],
                "needs_confirmation": False
            }
        
        # 최고 점수 확인
        best_match = candidates[0]
        
        # 상태 결정
        if best_match['score'] >= 95:
            # 매우 높은 유사도 - 자동 매칭
            return {
                "status": "fuzzy",
                "company": best_match['name'],
                "corp_code": best_match['corp_code'],
                "score": best_match['score'],
                "candidates": candidates,
                "needs_confirmation": False
            }
        elif best_match['score'] >= 85:
            # 높은 유사도 - 확인 권장
            # 두 번째 후보와의 점수 차이 확인
            if len(candidates) > 1 and (best_match['score'] - candidates[1]['score']) < 10:
                # 비슷한 점수의 후보가 여러 개
                return {
                    "status": "multiple",
                    "company": None,
                    "corp_code": None,
                    "score": best_match['score'],
                    "candidates": candidates,
                    "needs_confirmation": True
                }
            else:
                # 명확한 최고 후보
                return {
                    "status": "fuzzy",
                    "company": best_match['name'],
                    "corp_code": best_match['corp_code'],
                    "score": best_match['score'],
                    "candidates": candidates,
                    "needs_confirmation": True
                }
        else:
            # 낮은 유사도 - 확인 필수
            return {
                "status": "multiple",
                "company": None,
                "corp_code": None,
                "score": best_match['score'],
                "candidates": candidates,
                "needs_confirmation": True
            }
    
    def find_companies_batch(self, queries: List[str], threshold: int = 70) -> List[Dict[str, Any]]:
        """
        여러 기업명 일괄 검색
        
        Args:
            queries: 기업명 리스트
            threshold: 최소 유사도 임계값
            
        Returns:
            검색 결과 리스트
        """
        results = []
        for query in queries:
            result = self.find_company(query, threshold)
            result['original_query'] = query
            results.append(result)
        return results
    
    def get_company_by_stock_code(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        종목코드로 기업 찾기
        
        Args:
            stock_code: 6자리 종목코드
            
        Returns:
            기업 정보 또는 None
        """
        for company_name, info in self._company_map.items():
            if info['stock_code'] == stock_code:
                return {
                    "company": company_name,
                    "corp_code": info['corp_code'],
                    "stock_code": stock_code
                }
        return None