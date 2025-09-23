"""
설정 로더
환경변수 및 설정 파일 관리, LLM 클라이언트 초기화
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from utils.logging import get_logger

logger = get_logger("config")

# 환경변수 로드
load_dotenv()


class Config:
    """설정 관리 클래스"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: 설정 파일 경로 (선택적)
        """
        self.config_path = config_path or os.getenv("DART_CONFIG_PATH", "./config.json")
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        config = {
            # DART API
            "dart_api_key": os.getenv("DART_API_KEY", ""),
            
            # 캐시 설정
            "cache_dir": os.getenv("DART_CACHE_PATH", "./cache/dart"),
            "cache_ttl_hours": int(os.getenv("DART_CACHE_TTL", "24")),
            
            # 검색 설정
            "max_search_results": int(os.getenv("DART_MAX_SEARCH_RESULTS", "100")),
            "api_rate_limit": int(os.getenv("DART_API_RATE_LIMIT", "1000")),
            
            # 처리 설정
            "parallel_downloads": int(os.getenv("DART_PARALLEL_DOWNLOADS", "5")),
            "parse_timeout": int(os.getenv("DART_PARSE_TIMEOUT", "30000")),
            
            # LLM 설정
            "llm_provider": os.getenv("LLM_PROVIDER", "openai"),  # openai, vllm, claude
            "llm_api_key": os.getenv("OPENAI_API_KEY", "") if os.getenv("LLM_PROVIDER", "openai") == "openai" else os.getenv("LLM_API_KEY", ""),
            "llm_base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            "llm_model": os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
            "llm_temperature": float(os.getenv("LLM_TEMPERATURE", "0.3")),
            "llm_max_tokens": int(os.getenv("LLM_MAX_TOKENS") or "1000"),
            
            # 로깅 설정
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "log_dir": os.getenv("LOG_DIR", "./logs"),
            
            # 파일 저장 경로
            "download_path": os.getenv("DART_DOWNLOAD_PATH", "./downloads/dart"),
        }
        
        # 설정 파일이 있으면 병합
        if Path(self.config_path).exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    file_config = json.load(f)
                    config.update(file_config)
                    logger.info(f"Config loaded from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load config file: {e}")
        
        return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """설정값 조회"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """설정값 변경"""
        self.config[key] = value
    
    def save(self) -> None:
        """설정 파일로 저장"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info(f"Config saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def validate(self) -> bool:
        """설정 유효성 검사"""
        required = ["dart_api_key"]
        
        for key in required:
            if not self.config.get(key):
                logger.error(f"Required config missing: {key}")
                return False
        
        return True
    
    def get_llm_config(self) -> Dict[str, Any]:
        """LLM 관련 설정 반환"""
        return {
            "provider": self.config["llm_provider"],
            "api_key": self.config["llm_api_key"],
            "base_url": self.config["llm_base_url"],
            "model": self.config["llm_model"],
            "temperature": self.config["llm_temperature"],
            "max_tokens": self.config["llm_max_tokens"],
        }


def get_openai_client():
    """OpenAI 클라이언트 생성"""
    try:
        from openai import OpenAI
        
        config = Config()
        llm_config = config.get_llm_config()
        
        if llm_config["provider"] == "vllm":
            # vLLM 서버 사용
            # vLLM API 키 가져오기 (LLM_API_KEY 환경변수 사용)
            vllm_api_key = os.getenv("LLM_API_KEY", "EMPTY")
            client = OpenAI(
                api_key=vllm_api_key,  # vLLM 서버가 인증을 요구하는 경우 API 키 사용
                base_url=llm_config["base_url"]
            )
            logger.info(f"vLLM client initialized: {llm_config['base_url']} (auth: {'enabled' if vllm_api_key != 'EMPTY' else 'disabled'})")
            
        elif llm_config["provider"] == "openai":
            # OpenAI API 사용
            if not llm_config["api_key"]:
                logger.warning("OpenAI API key not configured")
                return None
                
            client = OpenAI(
                api_key=llm_config["api_key"],
                base_url=llm_config["base_url"] if llm_config["base_url"] != "https://api.openai.com/v1" else None
            )
            logger.info("OpenAI client initialized")
            
        else:
            logger.warning(f"Unsupported LLM provider: {llm_config['provider']}")
            return None
        
        return client
        
    except ImportError:
        logger.warning("OpenAI package not installed")
        return None
    except Exception as e:
        logger.error(f"Failed to create OpenAI client: {e}")
        return None


def get_current_model():
    """현재 설정된 LLM 모델명 반환"""
    config = Config()
    return config.get("llm_model", "gpt-3.5-turbo")


def get_current_model_path():
    """현재 설정된 LLM 모델 경로 반환 (vLLM용)"""
    config = Config()
    
    if config.get("llm_provider") == "vllm":
        # vLLM의 경우 모델 경로 반환
        return config.get("llm_model", "/models/default")
    else:
        # OpenAI의 경우 모델명 반환
        return config.get("llm_model", "gpt-3.5-turbo")


# 전역 설정 인스턴스
_global_config = None


def get_config() -> Config:
    """전역 설정 인스턴스 반환"""
    global _global_config
    
    if _global_config is None:
        _global_config = Config()
    
    return _global_config


def reload_config() -> Config:
    """설정 재로드"""
    global _global_config
    _global_config = Config()
    return _global_config