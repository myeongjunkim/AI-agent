#!/usr/bin/env python3
"""
환경 설정 검증 스크립트
.env 파일과 API 연동 설정을 확인합니다.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 색상 코드
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_status(status: str, message: str):
    """상태 메시지 출력"""
    if status == "OK":
        print(f"{GREEN}✓{RESET} {message}")
    elif status == "WARNING":
        print(f"{YELLOW}⚠{RESET} {message}")
    elif status == "ERROR":
        print(f"{RED}✗{RESET} {message}")
    else:
        print(f"  {message}")

def check_env_file():
    """환경 파일 확인"""
    print(f"\n{BOLD}=== 환경 파일 확인 ==={RESET}")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print_status("OK", ".env 파일이 존재합니다.")
        return True
    else:
        print_status("ERROR", ".env 파일이 없습니다.")
        if env_example.exists():
            print_status("", "  .env.example을 복사하여 생성하세요:")
            print_status("", f"  {BOLD}cp .env.example .env{RESET}")
        return False

def check_dart_api():
    """DART API 설정 확인"""
    print(f"\n{BOLD}=== DART API 설정 ==={RESET}")
    
    load_dotenv()
    dart_api_key = os.getenv("DART_API_KEY", "")
    
    if not dart_api_key:
        print_status("ERROR", "DART_API_KEY가 설정되지 않았습니다.")
        print_status("", "  https://opendart.fss.or.kr/ 에서 API 키를 발급받으세요.")
        return False
    
    if dart_api_key == "your-dart-api-key-here":
        print_status("WARNING", "DART_API_KEY가 예제 값으로 설정되어 있습니다.")
        print_status("", "  실제 API 키로 변경하세요.")
        return False
    
    # API 키 형식 확인 (40자리 영숫자)
    if len(dart_api_key) == 40 and dart_api_key.isalnum():
        print_status("OK", f"DART API 키가 설정되었습니다. (****{dart_api_key[-4:]})")
        
        # 실제 API 테스트
        try:
            import OpenDartReader
            dart = OpenDartReader(dart_api_key)
            # 간단한 테스트 - 회사 정보 조회
            test_result = dart.company("005930")  # 삼성전자
            if test_result is not None:
                print_status("OK", "DART API 연결 테스트 성공")
                return True
            else:
                print_status("WARNING", "DART API 키는 유효하나 응답이 없습니다.")
                return True
        except ImportError:
            print_status("WARNING", "OpenDartReader 패키지가 설치되지 않았습니다.")
            print_status("", "  pip install opendartreader")
            return False
        except Exception as e:
            print_status("ERROR", f"DART API 테스트 실패: {e}")
            return False
    else:
        print_status("ERROR", "DART API 키 형식이 올바르지 않습니다.")
        return False

def check_llm_api():
    """LLM API 설정 확인"""
    print(f"\n{BOLD}=== LLM API 설정 ==={RESET}")
    
    load_dotenv()
    llm_provider = os.getenv("LLM_PROVIDER", "none")
    
    print_status("", f"LLM Provider: {llm_provider}")
    
    if llm_provider == "none":
        print_status("WARNING", "LLM이 설정되지 않았습니다.")
        print_status("", "  고급 기능(쿼리 확장, 충분성 검사, 답변 생성)이 제한됩니다.")
        return True
    
    elif llm_provider == "openai":
        openai_key = os.getenv("OPENAI_API_KEY", "")
        
        if not openai_key:
            print_status("ERROR", "OPENAI_API_KEY가 설정되지 않았습니다.")
            return False
        
        if openai_key == "your-openai-api-key-here":
            print_status("WARNING", "OPENAI_API_KEY가 예제 값으로 설정되어 있습니다.")
            return False
        
        # OpenAI API 키 형식 확인
        if openai_key.startswith("sk-") and len(openai_key) > 20:
            print_status("OK", f"OpenAI API 키가 설정되었습니다. (****{openai_key[-4:]})")
            
            # 실제 API 테스트
            try:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                # 간단한 테스트
                response = client.models.list()
                print_status("OK", "OpenAI API 연결 테스트 성공")
                
                # 모델 확인
                model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
                print_status("", f"  사용 모델: {model}")
                return True
                
            except ImportError:
                print_status("WARNING", "openai 패키지가 설치되지 않았습니다.")
                print_status("", "  pip install openai")
                return False
            except Exception as e:
                print_status("ERROR", f"OpenAI API 테스트 실패: {e}")
                return False
        else:
            print_status("ERROR", "OpenAI API 키 형식이 올바르지 않습니다.")
            return False
    
    elif llm_provider == "vllm":
        base_url = os.getenv("LLM_BASE_URL", "")
        if base_url:
            print_status("OK", f"vLLM 서버 URL: {base_url}")
            
            # vLLM 서버 연결 테스트
            try:
                import httpx
                response = httpx.get(f"{base_url}/health", timeout=5)
                if response.status_code == 200:
                    print_status("OK", "vLLM 서버 연결 성공")
                    return True
                else:
                    print_status("WARNING", f"vLLM 서버 응답 코드: {response.status_code}")
                    return True
            except Exception as e:
                print_status("WARNING", f"vLLM 서버 연결 실패: {e}")
                return True
        else:
            print_status("WARNING", "LLM_BASE_URL이 설정되지 않았습니다.")
            return False
    
    else:
        print_status("WARNING", f"알 수 없는 LLM Provider: {llm_provider}")
        return False

def check_cache_settings():
    """캐시 설정 확인"""
    print(f"\n{BOLD}=== 캐시 설정 ==={RESET}")
    
    load_dotenv()
    cache_path = os.getenv("DART_CACHE_PATH", "./cache/dart")
    cache_ttl = os.getenv("DART_CACHE_TTL", "24")
    
    print_status("", f"캐시 디렉토리: {cache_path}")
    print_status("", f"캐시 TTL: {cache_ttl}시간")
    
    # 캐시 디렉토리 확인
    cache_dir = Path(cache_path)
    if cache_dir.exists():
        # 캐시 파일 수 확인
        cache_files = list(cache_dir.rglob("*.cache"))
        print_status("OK", f"캐시 디렉토리 존재 ({len(cache_files)}개 캐시 파일)")
    else:
        print_status("", "캐시 디렉토리가 아직 생성되지 않았습니다.")
    
    return True

def check_rate_limit_settings():
    """Rate Limit 설정 확인"""
    print(f"\n{BOLD}=== Rate Limit 설정 ==={RESET}")
    
    load_dotenv()
    rate_limit = os.getenv("DART_API_RATE_LIMIT", "1000")
    max_results = os.getenv("DART_MAX_SEARCH_RESULTS", "100")
    
    print_status("", f"일일 API 제한: {rate_limit}회")
    print_status("", f"최대 검색 결과: {max_results}개")
    
    return True

def check_dependencies():
    """필수 패키지 확인"""
    print(f"\n{BOLD}=== 필수 패키지 확인 ==={RESET}")
    
    required_packages = {
        "OpenDartReader": "opendartreader",
        "httpx": "httpx",
        "bs4": "beautifulsoup4",
        "dotenv": "python-dotenv"
    }
    
    optional_packages = {
        "openai": "openai",
        "pdfplumber": "pdfplumber"
    }
    
    all_ok = True
    
    # 필수 패키지
    for module, package in required_packages.items():
        try:
            __import__(module)
            print_status("OK", f"{package} 설치됨")
        except ImportError:
            print_status("ERROR", f"{package} 미설치 - pip install {package}")
            all_ok = False
    
    # 선택적 패키지
    for module, package in optional_packages.items():
        try:
            __import__(module)
            print_status("OK", f"{package} 설치됨 (선택적)")
        except ImportError:
            print_status("WARNING", f"{package} 미설치 (선택적) - pip install {package}")
    
    return all_ok

def main():
    """메인 함수"""
    print(f"{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}DART MCP 환경 설정 검증{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")
    
    results = []
    
    # 환경 파일 확인
    if check_env_file():
        # 각 설정 확인
        results.append(("DART API", check_dart_api()))
        results.append(("LLM API", check_llm_api()))
        results.append(("캐시", check_cache_settings()))
        results.append(("Rate Limit", check_rate_limit_settings()))
    else:
        results.append(("환경 파일", False))
    
    # 패키지 확인
    results.append(("필수 패키지", check_dependencies()))
    
    # 결과 요약
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}검증 결과 요약{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")
    
    all_ok = True
    for name, status in results:
        if status:
            print_status("OK", name)
        else:
            print_status("ERROR", name)
            all_ok = False
    
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    if all_ok:
        print(f"{GREEN}{BOLD}✅ 모든 설정이 정상입니다!{RESET}")
        print(f"\n이제 다음 명령으로 DART MCP를 실행할 수 있습니다:")
        print(f"  {BOLD}python main.py{RESET}")
    else:
        print(f"{RED}{BOLD}❌ 일부 설정에 문제가 있습니다.{RESET}")
        print(f"\n위의 오류 메시지를 확인하고 수정해주세요.")
        
        if not Path(".env").exists():
            print(f"\n먼저 .env 파일을 생성하세요:")
            print(f"  {BOLD}cp .env.example .env{RESET}")
            print(f"  {BOLD}vi .env  # 또는 원하는 편집기로 수정{RESET}")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())