"""
LLM 클라이언트 설정 유틸리티
메인 LLM과 추출용 LLM을 구분하여 관리
"""

import os
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv
from openai import OpenAI

# 조건부 import
try:
    import langextract as lx
    LANGEXTRACT_AVAILABLE = True
except ImportError:
    LANGEXTRACT_AVAILABLE = False


class LLMClientConfig:
    """LLM 클라이언트 설정 관리"""
    
    def __init__(self, use_extraction_llm: bool = True):
        """
        Args:
            use_extraction_llm: True면 추출용 LLM 설정, False면 메인 LLM 설정
        """
        # 환경변수 로드
        load_dotenv('.env')
        
        self.use_extraction_llm = use_extraction_llm
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """환경변수에서 설정 로드"""
        config = {}
        
        if self.use_extraction_llm:
            # 추출용 LLM 설정 로드
            config = self._load_extraction_config()
        else:
            # 메인 LLM 설정 로드
            config = self._load_main_config()
        
        return config
    
    def _load_extraction_config(self) -> Dict[str, Any]:
        """추출용 LLM 설정 로드 (쿼리 파싱, 정보 추출)"""
        config = {}
        
        # 우선순위: vLLM > LangExtract > Main LLM > Ollama
        
        if os.getenv('EXTRACTION_USE_VLLM', 'false').lower() == 'true':
            # vLLM 서버 사용
            config['mode'] = 'vllm'
            config['base_url'] = os.getenv('EXTRACTION_VLLM_BASE_URL', 'http://localhost:8000/v1')
            config['api_key'] = os.getenv('EXTRACTION_VLLM_API_KEY', 'dummy-key')
            config['model_name'] = os.getenv('EXTRACTION_VLLM_MODEL_NAME', 'meta-llama/Llama-3.1-8B-Instruct')
            print(f"📡 추출용 vLLM 서버: {config['base_url']}")
            
        elif os.getenv('EXTRACTION_USE_LANGEXTRACT', 'false').lower() == 'true':
            # LangExtract (Gemini) 사용
            config['mode'] = 'langextract'
            config['api_key'] = os.getenv('LANGEXTRACT_API_KEY')
            config['model_name'] = os.getenv('LANGEXTRACT_MODEL', 'gemini-2.0-flash-exp')
            
            if LANGEXTRACT_AVAILABLE and config['api_key']:
                print(f"✅ LangExtract 모드: {config['model_name']}")
            else:
                if not LANGEXTRACT_AVAILABLE:
                    print("⚠️ LangExtract가 설치되지 않았습니다.")
                if not config['api_key']:
                    print("⚠️ LANGEXTRACT_API_KEY가 설정되지 않았습니다.")
                # 메인 LLM으로 폴백
                return self._load_main_config()
                
        elif os.getenv('EXTRACTION_USE_MAIN_LLM', 'false').lower() == 'true':
            # 메인 LLM 설정 재사용
            return self._load_main_config()
            
        elif os.getenv('EXTRACTION_USE_OLLAMA', 'false').lower() == 'true':
            # Ollama 사용
            config['mode'] = 'ollama'
            config['base_url'] = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
            config['model_name'] = os.getenv('OLLAMA_MODEL', 'llama3.1:8b')
            print(f"🦙 Ollama 모드: {config['model_name']}")
            
        else:
            # 기본값: 메인 LLM 사용
            print("ℹ️ 추출용 LLM 미설정, 메인 LLM 사용")
            return self._load_main_config()
        
        return config
    
    def _load_main_config(self) -> Dict[str, Any]:
        """메인 LLM 설정 로드 (문서 분석, 요약 등)"""
        config = {}
        provider = os.getenv('LLM_PROVIDER', 'none')
        
        if provider == 'openai':
            config['mode'] = 'openai'
            config['api_key'] = os.getenv('OPENAI_API_KEY')
            config['model_name'] = os.getenv('LLM_MODEL', 'gpt-3.5-turbo')
            config['temperature'] = float(os.getenv('LLM_TEMPERATURE', '0.3'))
            config['max_tokens'] = int(os.getenv('LLM_MAX_TOKENS', '1000'))
            
            if config['api_key']:
                print(f"🤖 OpenAI 모드: {config['model_name']}")
            else:
                print("⚠️ OPENAI_API_KEY가 설정되지 않았습니다.")
                
        elif provider == 'vllm':
            config['mode'] = 'vllm'
            config['base_url'] = os.getenv('LLM_BASE_URL', 'http://localhost:8000/v1')
            config['api_key'] = os.getenv('LLM_API_KEY', 'dummy-key')
            config['model_name'] = os.getenv('LLM_MODEL', 'meta-llama/Llama-3.1-8B-Instruct')
            config['temperature'] = float(os.getenv('LLM_TEMPERATURE', '0.3'))
            config['max_tokens'] = int(os.getenv('LLM_MAX_TOKENS', '1000'))
            print(f"📡 메인 vLLM 서버: {config['base_url']}")
            
        else:
            config['mode'] = 'none'
            print("ℹ️ LLM이 설정되지 않았습니다.")
        
        return config
    
    def get_openai_client(self) -> Optional[OpenAI]:
        """OpenAI 호환 클라이언트 반환"""
        mode = self.config.get('mode')
        
        if mode == 'openai':
            return OpenAI(api_key=self.config.get('api_key'))
        elif mode == 'vllm':
            return OpenAI(
                base_url=self.config.get('base_url'),
                api_key=self.config.get('api_key')
            )
        elif mode == 'ollama':
            # Ollama도 OpenAI 호환 API 제공
            return OpenAI(
                base_url=f"{self.config.get('base_url')}/v1",
                api_key='ollama'  # Ollama는 API 키 불필요
            )
        return None
    
    def get_langextract_config(self) -> Tuple[str, Optional[str]]:
        """LangExtract 설정 반환 (model_id, api_key)"""
        if self.config.get('mode') == 'langextract':
            return self.config.get('model_name'), self.config.get('api_key')
        return None, None
    
    def is_vllm_mode(self) -> bool:
        """vLLM 모드 여부"""
        return self.config.get('mode') == 'vllm'
    
    def is_langextract_available(self) -> bool:
        """LangExtract 사용 가능 여부"""
        return (
            LANGEXTRACT_AVAILABLE and 
            self.config.get('mode') == 'langextract' and 
            self.config.get('api_key') is not None
        )
    
    def get_model_name(self) -> str:
        """현재 모델명 반환"""
        return self.config.get('model_name', 'unknown')
    
    def get_mode(self) -> str:
        """현재 모드 반환"""
        return self.config.get('mode', 'unknown')
    
    def get_temperature(self) -> float:
        """온도 설정 반환"""
        return self.config.get('temperature', 0.3)
    
    def get_max_tokens(self) -> int:
        """최대 토큰 수 반환"""
        return self.config.get('max_tokens', 500)


# 싱글톤 인스턴스
_main_config = None
_extraction_config = None

def get_main_llm_config() -> LLMClientConfig:
    """메인 LLM 설정 반환"""
    global _main_config
    if _main_config is None:
        _main_config = LLMClientConfig(use_extraction_llm=False)
    return _main_config

def get_extraction_llm_config() -> LLMClientConfig:
    """추출용 LLM 설정 반환"""
    global _extraction_config
    if _extraction_config is None:
        _extraction_config = LLMClientConfig(use_extraction_llm=True)
    return _extraction_config

# 기본값: 추출용 LLM
def get_llm_config() -> LLMClientConfig:
    """기본 LLM 설정 (추출용) 반환"""
    return get_extraction_llm_config()


def create_chat_completion(
    messages: list,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    config: Optional[LLMClientConfig] = None,
    use_main_llm: bool = False
) -> Optional[str]:
    """
    통합 채팅 완성 함수
    
    Args:
        messages: OpenAI 형식 메시지 리스트
        model: 모델명 (None일 경우 설정에서 가져옴)
        temperature: 생성 온도
        max_tokens: 최대 토큰 수
        config: LLM 설정 (None일 경우 기본 설정 사용)
        use_main_llm: True면 메인 LLM 사용, False면 추출용 LLM 사용
        
    Returns:
        생성된 텍스트 또는 None
    """
    if config is None:
        config = get_main_llm_config() if use_main_llm else get_extraction_llm_config()
    
    client = config.get_openai_client()
    if client:
        try:
            response = client.chat.completions.create(
                model=model or config.get_model_name(),
                messages=messages,
                temperature=temperature or config.get_temperature(),
                max_tokens=max_tokens or config.get_max_tokens()
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM 호출 실패: {e}")
            return None
    
    return None


# LangExtract 헬퍼 함수들
def create_langextract_example(
    text: str,
    extractions: list
) -> Any:
    """LangExtract 예제 데이터 생성"""
    if not LANGEXTRACT_AVAILABLE:
        return None
    
    extraction_objects = []
    for ext in extractions:
        extraction_objects.append(
            lx.data.Extraction(
                extraction_class=ext.get('class'),
                extraction_text=ext.get('text'),
                attributes=ext.get('attributes', {})
            )
        )
    
    return lx.data.ExampleData(
        text=text,
        extractions=extraction_objects
    )