# AI-agent

MCP 기반 AI Agent Server

## 프로젝트 구조

- `server/`: FastAPI 기반 에이전트 서버
  - `.env`로 모델/키 설정, `mcp.json`으로 MCP 서버 등록
  - 엔드포인트: `POST /api/v1/chat/`
- `mcp/`: MCP 서버들
  - `websearch-mcp/`: RSS/웹 검색 예시 (uv + fastmcp)
  - `example-mcp/`: 최소 예시 MCP
- `langfuse/`: Langfuse (OSS) 모노레포 서브트리. 로컬 셀프호스트 및 개발 유틸 제공

---

## 1) Server 실행 방법

### 1-1. 필수 요구사항

- Python 3.13+
- `uv` 패키지 관리자 (권장)

### 1-2. 환경변수(.env)

`/server/.env` 파일을 생성:

```
OPENAI_API_KEY=your-openai-key
MODEL_NAME=gpt-4o-mini
BASE_URL=

LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

설정은 `server/app/_core/config.py`의 `Settings`에서 로드됩니다.

### 1-3. MCP 설정(mcp.json)

`/server/mcp.json` 파일로 MCP 서버를 등록합니다. 예시:

```
{
  "websearch-mcp": {
    "transport": "stdio",
    "command": "uv",
    "args": ["run", "fastmcp", "run", "app/main.py"],
    "cwd": "../mcp/websearch-mcp",
    "env": {
      "OPENAI_API_KEY": "...",
      "OPENAI_BASE_URL": "http://localhost:11434/v1", # 선택
      "GOOGLE_SEARCH_API_KEY": "...",
      "GOOGLE_CX_ID": "..."
    }
  }
}
```

주의: 실제 키를 노출하지 않도록 `.env` 를 사용해 주입하는 것을 권장합니다.

### 1-4. 의존성 설치 및 서버 실행

```
cd server
uv sync
uv run fastapi dev
```

엔드포인트: `POST http://localhost:8000/api/v1/chat/`

---

## 2) MCP 추가 방법 (환경변수 관리 포함)

1. MCP 폴더 추가: `mcp/<your-mcp>/app/main.py`에 `FastMCP` 서버 구현 및 `mcp.run(transport="stdio")` 호출
2. 실행 스크립트: `uv run fastmcp run app/main.py`로 구동 가능하도록 구성
3. `server/mcp.json`에 신규 MCP 블록 추가
   - mcp.example.json 참고
   - `cwd`는 MCP 디렉토리
   - 민감값은 `env`에 직접 넣지 말고, mcp.json 에서 주입

---

## 3) Langfuse 실행 방법

- 로컬 셀프호스트(Docker Compose):

```
cd langfuse
docker compose up
# 준비가 되면 웹은 http://localhost:3000 에서 접근 가능
```

---

## 참고 링크/파일

- 서버 진입점: `server/app/main.py`, 라우터: `server/app/api/v1/chat.py`
- Langfuse 통합: `server/app/client/agent.py` (Langfuse SDK/Callback 사용)
- MCP 예시: `mcp/websearch-mcp/app/main.py`, `mcp/example-mcp/app/main.py`
