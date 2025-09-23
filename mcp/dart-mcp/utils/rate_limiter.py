"""
Rate Limiter for API calls
DART API 호출 제한 관리
"""

import asyncio
import time
from typing import Optional, Dict, Any
from collections import deque
from datetime import datetime, timedelta

from utils.logging import get_logger
from functools import wraps

logger = get_logger("rate_limiter")


class RateLimiter:
    """API 호출 속도 제한기"""
    
    def __init__(
        self,
        max_calls: int = 100,
        time_window: int = 60,
        burst_limit: Optional[int] = None
    ):
        """
        Args:
            max_calls: 시간 윈도우 내 최대 호출 수
            time_window: 시간 윈도우 (초)
            burst_limit: 순간 최대 호출 수 (선택적)
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.burst_limit = burst_limit or max_calls
        
        # 호출 기록 (타임스탬프 큐)
        self.call_times = deque()
        
        # 대기 중인 요청 수
        self.pending_requests = 0
        
        # 통계
        self.stats = {
            "total_calls": 0,
            "throttled_calls": 0,
            "total_wait_time": 0.0,
            "last_reset": datetime.now()
        }
        
        # 세마포어 (동시 실행 제한)
        self.semaphore = asyncio.Semaphore(min(10, burst_limit or 10))
        
        # 락 (스레드 안전성)
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> float:
        """
        호출 권한 획득 (필요시 대기)
        
        Returns:
            대기 시간 (초)
        """
        async with self.lock:
            now = time.time()
            wait_time = 0.0
            
            # 오래된 호출 기록 정리
            self._cleanup_old_calls(now)
            
            # 현재 윈도우 내 호출 수 확인
            current_calls = len(self.call_times)
            
            # 제한 초과시 대기
            if current_calls >= self.max_calls:
                # 가장 오래된 호출이 윈도우를 벗어날 때까지 대기
                oldest_call = self.call_times[0]
                wait_time = max(0, self.time_window - (now - oldest_call))
                
                if wait_time > 0:
                    self.stats["throttled_calls"] += 1
                    self.stats["total_wait_time"] += wait_time
                    self.pending_requests += 1
                    
                    logger.info(f"Rate limit reached. Waiting {wait_time:.2f}s "
                              f"(pending: {self.pending_requests})")
                    
                    # 대기
                    await asyncio.sleep(wait_time)
                    self.pending_requests -= 1
                    
                    # 대기 후 다시 정리
                    now = time.time()
                    self._cleanup_old_calls(now)
            
            # 호출 기록 추가
            self.call_times.append(now)
            self.stats["total_calls"] += 1
            
            return wait_time
    
    def _cleanup_old_calls(self, now: float):
        """오래된 호출 기록 정리"""
        cutoff = now - self.time_window
        
        while self.call_times and self.call_times[0] < cutoff:
            self.call_times.popleft()
    
    async def __aenter__(self):
        """컨텍스트 매니저 진입"""
        await self.acquire()
        await self.semaphore.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        self.semaphore.release()
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 정보 반환"""
        now = datetime.now()
        uptime = (now - self.stats["last_reset"]).total_seconds()
        
        return {
            "total_calls": self.stats["total_calls"],
            "throttled_calls": self.stats["throttled_calls"],
            "throttle_rate": (
                self.stats["throttled_calls"] / max(1, self.stats["total_calls"])
            ),
            "avg_wait_time": (
                self.stats["total_wait_time"] / max(1, self.stats["throttled_calls"])
                if self.stats["throttled_calls"] > 0 else 0
            ),
            "pending_requests": self.pending_requests,
            "current_window_calls": len(self.call_times),
            "calls_per_minute": (
                self.stats["total_calls"] / max(1, uptime / 60)
            ),
            "uptime_seconds": uptime
        }
    
    def reset_stats(self):
        """통계 초기화"""
        self.stats = {
            "total_calls": 0,
            "throttled_calls": 0,
            "total_wait_time": 0.0,
            "last_reset": datetime.now()
        }
        logger.info("Rate limiter stats reset")


class MultiServiceRateLimiter:
    """여러 서비스용 Rate Limiter 관리"""
    
    def __init__(self):
        """초기화"""
        self.limiters = {}
        self.default_configs = {
            "dart_api": {
                "max_calls": 100,
                "time_window": 60,
                "burst_limit": 20
            },
            "openai": {
                "max_calls": 60,
                "time_window": 60,
                "burst_limit": 10
            },
            "default": {
                "max_calls": 30,
                "time_window": 60,
                "burst_limit": 5
            }
        }
    
    def get_limiter(self, service: str) -> RateLimiter:
        """
        서비스별 Rate Limiter 획득
        
        Args:
            service: 서비스 이름
            
        Returns:
            Rate Limiter 인스턴스
        """
        if service not in self.limiters:
            config = self.default_configs.get(
                service,
                self.default_configs["default"]
            )
            self.limiters[service] = RateLimiter(**config)
            logger.info(f"Created rate limiter for {service}: {config}")
        
        return self.limiters[service]
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """모든 서비스의 통계 반환"""
        return {
            service: limiter.get_stats()
            for service, limiter in self.limiters.items()
        }
    
    def reset_all_stats(self):
        """모든 통계 초기화"""
        for limiter in self.limiters.values():
            limiter.reset_stats()


# 전역 Rate Limiter 인스턴스
_global_limiter = MultiServiceRateLimiter()


def get_rate_limiter(service: str = "default") -> RateLimiter:
    """
    Rate Limiter 인스턴스 획득
    
    Args:
        service: 서비스 이름
        
    Returns:
        Rate Limiter 인스턴스
    """
    return _global_limiter.get_limiter(service)


async def rate_limited_call(
    func,
    *args,
    service: str = "default",
    **kwargs
):
    """
    Rate Limit이 적용된 함수 호출
    
    Args:
        func: 호출할 함수
        service: 서비스 이름
        *args, **kwargs: 함수 인자
        
    Returns:
        함수 반환값
    """
    limiter = get_rate_limiter(service)
    
    async with limiter:
        # 함수가 비동기인지 확인
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)


class RateLimitDecorator:
    """Rate Limit 데코레이터"""
    
    def __init__(self, service: str = "default"):
        """
        Args:
            service: 서비스 이름
        """
        self.service = service
    
    def __call__(self, func):
        """데코레이터 적용"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await rate_limited_call(
                func, *args, service=self.service, **kwargs
            )
        return wrapper


# 데코레이터 shortcuts
dart_rate_limit = RateLimitDecorator("dart_api")
llm_rate_limit = RateLimitDecorator("openai")