#!/usr/bin/env python3
"""
DART MCP Server
한국 금융감독원 DART (전자공시시스템) API를 위한 MCP 서버
"""

import signal
import sys
import time

from fastmcp import FastMCP

from tools.dart_deep_search_tools import register_deep_search_tools
from utils.logging import get_logger

# Logger 초기화
logger = get_logger("dart-mcp.main")

# 서버 상태 추적
class ServerState:
    def __init__(self):
        self.initialized = False
        self.total_tools = 0
        self.total_resources = 0
        self.registered_modules = []
        self.startup_time = None
        self.shutdown_requested = False

server_state = ServerState()

# FastMCP 서버 초기화
mcp = FastMCP(
    name="dart",
    instructions="""
DART MCP 서버는 한국 금융감독원 DART(전자공시시스템)의 api를 활용한 심층 검색 서버입니다.
일반적인 자연어 쿼리에 대해서는 dart_deep_search 도구를 사용하여 포괄적인 검색을 수행합니다.
이 도구는 기업명, 날짜, 문서 유형 등을 자동으로 추출하여 검색합니다.
또한, 특정 기업이나 이벤트 중심의 검색도 지원합니다.

🔍 주요 기능:
• dart_deep_search: 복잡한 자연어 쿼리를 통한 포괄적 공시 검색

"""
)

def setup_signal_handlers():
    """시그널 핸들러 설정 (Unix 시스템용)"""
    def signal_handler(signum, frame):
        server_state.shutdown_requested = True
        logger.info(f"🔔 Received signal {signum}, initiating graceful shutdown...")
        sys.exit(0)

    if sys.platform != 'win32':
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

def initialize_server():
    """서버 초기화 및 모듈 등록"""
    server_state.startup_time = time.time()

    logger.info("🚀 DART MCP Server starting up...")

    try:
        # 시그널 핸들러 설정
        setup_signal_handlers()

        # DART 심층 검색 도구 등록
        logger.info("📦 Registering DART Deep Search tools...")
        register_deep_search_tools(mcp)
        server_state.total_tools += 1  # dart_deep_search
        server_state.registered_modules.append("dart_deep_search_tools")

        # 초기화 완료
        server_state.initialized = True
        startup_duration = time.time() - server_state.startup_time

        logger.info(f"✅ Server initialization completed in {startup_duration:.2f}s")
        logger.info(f"📊 Total tools registered: {server_state.total_tools}")
        logger.info(f"📚 Registered modules: {', '.join(server_state.registered_modules)}")

    except Exception as e:
        logger.error(f"❌ Critical failure during server initialization: {e}")
        raise

def shutdown_server():
    """서버 종료 처리"""
    if server_state.startup_time:
        shutdown_duration = time.time() - server_state.startup_time
        logger.info(f"🛑 DART MCP Server shutting down after {shutdown_duration:.2f}s uptime")

    logger.info("👋 DART MCP Server process ended")


if __name__ == "__main__":
    try:
        # 서버 초기화
        initialize_server()

        # MCP 서버 시작
        mcp.run(transport="stdio")

    except KeyboardInterrupt:
        logger.info("🛑 Server shutdown requested by user (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"💥 Server crashed with unhandled exception: {e}")
        raise
    finally:
        shutdown_server()
