"""
캐싱 시스템
DART API 호출 결과를 캐싱하여 중복 호출 방지 및 성능 향상
"""

import json
import hashlib
import os
import time
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
import pickle
from pathlib import Path

from utils.logging import get_logger

logger = get_logger("cache")


class DartCache:
    """DART API 캐시 관리"""
    
    def __init__(self, cache_dir: str = "./cache/dart", ttl_hours: int = 24):
        """
        Args:
            cache_dir: 캐시 디렉토리 경로
            ttl_hours: 캐시 유효 시간 (시간 단위)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        self.memory_cache = {}  # 메모리 캐시
        
        # 캐시 통계
        self.stats = {
            "hits": 0,
            "misses": 0,
            "saves": 0
        }
        
        logger.info(f"Cache initialized: {self.cache_dir} (TTL: {ttl_hours}h)")
    
    def _generate_key(self, function_name: str, params: Dict[str, Any]) -> str:
        """
        캐시 키 생성
        
        Args:
            function_name: 함수명
            params: 파라미터 딕셔너리
            
        Returns:
            해시된 캐시 키
        """
        # 파라미터를 정렬하여 일관된 키 생성
        sorted_params = json.dumps(params, sort_keys=True, ensure_ascii=False)
        key_string = f"{function_name}:{sorted_params}"
        
        # MD5 해시로 키 생성
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """캐시 파일 경로 반환"""
        # 첫 2글자로 서브디렉토리 생성 (분산 저장)
        subdir = self.cache_dir / cache_key[:2]
        subdir.mkdir(exist_ok=True)
        return subdir / f"{cache_key}.cache"
    
    def _is_valid(self, timestamp: float) -> bool:
        """캐시 유효성 검사"""
        age = datetime.now() - datetime.fromtimestamp(timestamp)
        return age < self.ttl
    
    async def get(self, function_name: str, params: Dict[str, Any]) -> Optional[Any]:
        """
        캐시에서 데이터 조회
        
        Args:
            function_name: 함수명
            params: 파라미터
            
        Returns:
            캐시된 데이터 또는 None
        """
        cache_key = self._generate_key(function_name, params)
        
        # 1. 메모리 캐시 확인
        if cache_key in self.memory_cache:
            entry = self.memory_cache[cache_key]
            if self._is_valid(entry["timestamp"]):
                self.stats["hits"] += 1
                logger.debug(f"Memory cache hit: {function_name}")
                return entry["data"]
            else:
                del self.memory_cache[cache_key]
        
        # 2. 파일 캐시 확인
        cache_path = self._get_cache_path(cache_key)
        
        if cache_path.exists():
            try:
                with open(cache_path, "rb") as f:
                    entry = pickle.load(f)
                    
                if self._is_valid(entry["timestamp"]):
                    # 메모리 캐시에도 저장
                    self.memory_cache[cache_key] = entry
                    self.stats["hits"] += 1
                    logger.debug(f"File cache hit: {function_name}")
                    return entry["data"]
                else:
                    # 만료된 캐시 삭제
                    cache_path.unlink()
                    logger.debug(f"Expired cache removed: {function_name}")
                    
            except Exception as e:
                logger.error(f"Cache read error: {e}")
                # 손상된 캐시 파일 삭제
                cache_path.unlink(missing_ok=True)
        
        self.stats["misses"] += 1
        logger.debug(f"Cache miss: {function_name}")
        return None
    
    async def set(self, function_name: str, params: Dict[str, Any], data: Any) -> None:
        """
        데이터를 캐시에 저장
        
        Args:
            function_name: 함수명
            params: 파라미터
            data: 저장할 데이터
        """
        cache_key = self._generate_key(function_name, params)
        
        entry = {
            "timestamp": time.time(),
            "function": function_name,
            "params": params,
            "data": data
        }
        
        # 1. 메모리 캐시에 저장
        self.memory_cache[cache_key] = entry
        
        # 2. 파일 캐시에 저장
        cache_path = self._get_cache_path(cache_key)
        
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(entry, f)
            
            self.stats["saves"] += 1
            logger.debug(f"Data cached: {function_name}")
            
        except Exception as e:
            logger.error(f"Cache write error: {e}")
    
    async def clear(self, older_than_hours: Optional[int] = None) -> int:
        """
        캐시 삭제
        
        Args:
            older_than_hours: 지정된 시간보다 오래된 캐시만 삭제 (None이면 전체 삭제)
            
        Returns:
            삭제된 파일 수
        """
        count = 0
        
        # 메모리 캐시 클리어
        if older_than_hours is None:
            self.memory_cache.clear()
        else:
            cutoff = time.time() - (older_than_hours * 3600)
            keys_to_delete = [
                k for k, v in self.memory_cache.items()
                if v["timestamp"] < cutoff
            ]
            for key in keys_to_delete:
                del self.memory_cache[key]
        
        # 파일 캐시 클리어
        for cache_file in self.cache_dir.rglob("*.cache"):
            try:
                if older_than_hours is None:
                    cache_file.unlink()
                    count += 1
                else:
                    mtime = cache_file.stat().st_mtime
                    if mtime < cutoff:
                        cache_file.unlink()
                        count += 1
                        
            except Exception as e:
                logger.error(f"Failed to delete cache file {cache_file}: {e}")
        
        logger.info(f"Cleared {count} cache files")
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        # 캐시 크기 계산
        cache_size = sum(
            f.stat().st_size for f in self.cache_dir.rglob("*.cache")
        )
        
        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "saves": self.stats["saves"],
            "hit_rate": f"{hit_rate:.1f}%",
            "cache_files": len(list(self.cache_dir.rglob("*.cache"))),
            "cache_size_mb": f"{cache_size / 1024 / 1024:.1f}",
            "memory_entries": len(self.memory_cache)
        }


class CachedFunction:
    """함수 캐싱 데코레이터"""
    
    def __init__(self, cache: DartCache):
        self.cache = cache
    
    def __call__(self, func):
        """데코레이터 구현"""
        async def wrapper(*args, **kwargs):
            # 함수명과 파라미터 추출
            function_name = func.__name__
            
            # 파라미터를 딕셔너리로 변환
            params = {
                "args": args,
                "kwargs": kwargs
            }
            
            # 캐시 조회
            cached_result = await self.cache.get(function_name, params)
            if cached_result is not None:
                return cached_result
            
            # 함수 실행
            result = await func(*args, **kwargs)
            
            # 결과 캐싱 (에러가 아닌 경우만)
            if result and not (isinstance(result, str) and "error" in result):
                await self.cache.set(function_name, params, result)
            
            return result
        
        return wrapper


# 전역 캐시 인스턴스
_global_cache = None


def get_cache(cache_dir: str = None, ttl_hours: int = 24) -> DartCache:
    """전역 캐시 인스턴스 반환"""
    global _global_cache
    
    if _global_cache is None:
        cache_dir = cache_dir or os.getenv("DART_CACHE_PATH", "./cache/dart")
        _global_cache = DartCache(cache_dir, ttl_hours)
    
    return _global_cache


def cached(ttl_hours: int = 24):
    """캐싱 데코레이터 (간편 사용)"""
    cache = get_cache(ttl_hours=ttl_hours)
    return CachedFunction(cache)