"""
DART 심층 검색 MCP 도구
복잡한 DART 검색 쿼리를 처리하는 MCP 도구
"""

from mcp.server.fastmcp import FastMCP
from workflow.dart_orchestrator import dart_research_pipeline
from tools import dart_api_tools
from utils.logging import get_logger

# Logger 초기화
logger = get_logger("dart_deep_search")


def register_deep_search_tools(mcp: FastMCP):
    """
    DART 심층 검색 도구를 MCP 서버에 등록
    
    Args:
        mcp: FastMCP 서버 인스턴스
    """
    
    @mcp.tool(
        name="dart_deep_search",
        description="""DART 심층 검색 - 사용자의 복잡한 질의를 분석하여 포괄적인 공시 검색 및 답변 생성
        
        이 도구는 다음과 같은 작업을 수행합니다:
        1. 쿼리 분석 및 확장 (날짜, 기업명, 문서유형 자동 추출)
        2. 병렬 검색으로 여러 기업/문서유형 동시 검색
        3. 검색 결과 관련성 평가 및 정렬
        4. 종합적인 답변 생성
        
        사용 예시:
        - "최근 1년간 삼성전자의 자사주 관련 공시"
        - "올해 주요 기업들의 합병 관련 공시"
        - "최근 3개월 내 유상증자 공시"
        """
    )
    async def dart_deep_search(query: str) -> str:
        """
        DART 심층 검색 실행
        
        Args:
            query: 사용자의 자연어 질의
            
        Returns:
            JSON 형식의 검색 결과 및 답변
        """
        logger.info(f"Deep search requested: {query}")
        
        try:
            # 오케스트레이터 실행
            result = await dart_research_pipeline(query, dart_api_tools)
            logger.info("Deep search completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Deep search error: {str(e)}")
            import json
            return json.dumps({
                "status": "error",
                "query": query,
                "error": str(e),
                "message": "심층 검색 중 오류가 발생했습니다."
            }, ensure_ascii=False)
    
    # 아래 함수들은 MCP 도구로 등록하지 않고 내부 헬퍼 함수로만 사용
    # @mcp.tool 데코레이터를 제거하여 등록하지 않음
    
    logger.info("DART deep search tools registered successfully")