from fastapi import APIRouter
from datetime import datetime
from app.api.schema import SearchRequest, SearchResponse

router = APIRouter(prefix="/v1/search", tags=["search"])


@router.post("/dart", response_model=SearchResponse)
async def dart_search(request: SearchRequest) -> SearchResponse:

    # mcp 비지니스 로직 실행
    
    response = SearchResponse(
        query=request.query,
        status="success",
        expanded_query={},
        statistics={},
        documents=[],
        timestamp=datetime.now().isoformat()
    )
    return response



@router.post("/web", response_model=SearchResponse)
async def web_search(request: SearchRequest) -> SearchResponse:

    # mcp 비지니스 로직 실행
    
    response = SearchResponse(
        query=request.query,
        status="success",
        expanded_query={},
        statistics={},
        documents=[],
        timestamp=datetime.now().isoformat()
    )
    return response