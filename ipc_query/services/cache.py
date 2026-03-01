"""
缓存服务模块

提供内存缓存功能，支持 LRU 淘汰和 TTL 过期。
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar, cast

from ..constants import CACHE_STRATEGIES
from ..utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
P = ParamSpec("P")


@dataclass
class CacheEntry:
    """缓存条目"""

    value: Any
    created_at: float
    ttl: int  # 秒

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl <= 0:
            return False
        return time.time() - self.created_at > self.ttl


class CacheService:
    """
    缓存服务

    提供线程安全的 LRU 缓存，支持 TTL 过期。

    Example:
        cache = CacheService(max_size=1000, ttl_seconds=300)

        # 设置缓存
        cache.set("search:query1", results)

        # 获取缓存
        results = cache.get("search:query1")

        # 使用装饰器缓存函数结果
        @cache.cached("search", key_func=lambda q: f"search:{q}")
        def search(query: str):
            return do_search(query)
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        """
        初始化缓存服务

        Args:
            max_size: 最大缓存条目数
            ttl_seconds: 默认过期时间（秒）
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = ttl_seconds
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

        logger.info(
            "Cache service initialized",
            extra_fields={
                "max_size": max_size,
                "default_ttl": ttl_seconds,
            },
        )

    def get(self, key: str) -> Any | None:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值或 None
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            # 检查过期
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                logger.debug("Cache expired", extra_fields={"key": key})
                return None

            # 移动到末尾（LRU）
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None 使用默认值
        """
        with self._lock:
            # 如果已存在，先删除
            if key in self._cache:
                del self._cache[key]

            # 检查容量
            while len(self._cache) >= self._max_size:
                # 删除最旧的条目
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug(
                    "Cache evicted (LRU)",
                    extra_fields={"evicted_key": oldest_key},
                )

            # 添加新条目
            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl if ttl is not None else self._default_ttl,
            )

    def delete(self, key: str) -> bool:
        """
        删除缓存条目

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")

    def invalidate_pattern(self, pattern: str) -> int:
        """
        按模式删除缓存

        Args:
            pattern: 键前缀模式

        Returns:
            删除的条目数
        """
        with self._lock:
            keys_to_delete = [
                k for k in self._cache.keys()
                if k.startswith(pattern)
            ]
            for key in keys_to_delete:
                del self._cache[key]

            if keys_to_delete:
                logger.debug(
                    "Cache invalidated by pattern",
                    extra_fields={
                        "pattern": pattern,
                        "count": len(keys_to_delete),
                    },
                )

            return len(keys_to_delete)

    def get_stats(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0

            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "total_requests": total_requests,
            }

    def cached(
        self,
        cache_name: str,
        key_func: Callable[P, str] | None = None,
        ttl: int | None = None,
    ) -> Callable[[Callable[P, T]], Callable[P, T]]:
        """
        缓存装饰器

        Args:
            cache_name: 缓存名称（用于日志）
            key_func: 生成缓存键的函数，默认使用参数
            ttl: 过期时间

        Returns:
            装饰器函数

        Example:
            @cache.cached("search", key_func=lambda q: f"search:{q}")
            def search(query: str):
                return do_search(query)
        """
        def decorator(func: Callable[P, T]) -> Callable[P, T]:
            @wraps(func)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                # 生成缓存键
                if key_func:
                    cache_key = f"{cache_name}:{key_func(*args, **kwargs)}"
                else:
                    cache_key = f"{cache_name}:{args}:{kwargs}"

                # 尝试从缓存获取
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    logger.debug(
                        "Cache hit",
                        extra_fields={"cache": cache_name, "key": cache_key},
                    )
                    return cast(T, cached_value)

                # 执行函数
                result = func(*args, **kwargs)

                # 存入缓存
                self.set(cache_key, result, ttl=ttl)
                logger.debug(
                    "Cache miss, stored",
                    extra_fields={"cache": cache_name, "key": cache_key},
                )

                return result

            return wrapper
        return decorator


class MultiCache:
    """
    多缓存管理器

    管理多个独立的缓存实例，每个实例可以有不同的配置。
    """

    def __init__(self) -> None:
        self._caches: dict[str, CacheService] = {}
        self._lock = threading.Lock()

    def get_cache(
        self,
        name: str,
        max_size: int | None = None,
        ttl: int | None = None,
    ) -> CacheService:
        """
        获取或创建缓存实例

        Args:
            name: 缓存名称
            max_size: 最大大小
            ttl: 过期时间

        Returns:
            CacheService 实例
        """
        with self._lock:
            if name not in self._caches:
                # 使用预定义策略或默认值
                strategy = CACHE_STRATEGIES.get(name, {})
                cache = CacheService(
                    max_size=max_size or strategy.get("max_size", 500),
                    ttl_seconds=ttl or strategy.get("ttl", 300),
                )
                self._caches[name] = cache
                logger.info(
                    "Created cache instance",
                    extra_fields={
                        "name": name,
                        "max_size": cache._max_size,
                        "ttl": cache._default_ttl,
                    },
                )

            return self._caches[name]

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """获取所有缓存的统计信息"""
        return {
            name: cache.get_stats()
            for name, cache in self._caches.items()
        }

    def clear_all(self) -> None:
        """清空所有缓存"""
        for cache in self._caches.values():
            cache.clear()

    def get_aggregate_stats(self) -> dict[str, Any]:
        """获取聚合统计信息"""
        total_hits = 0
        total_misses = 0
        total_size = 0

        for cache in self._caches.values():
            stats = cache.get_stats()
            total_hits += stats["hits"]
            total_misses += stats["misses"]
            total_size += stats["size"]

        total_requests = total_hits + total_misses
        return {
            "total_caches": len(self._caches),
            "total_size": total_size,
            "total_hits": total_hits,
            "total_misses": total_misses,
            "hit_rate": total_hits / total_requests if total_requests > 0 else 0,
        }


# 全局多缓存实例
multi_cache = MultiCache()


def get_cache(
    name: str,
    max_size: int | None = None,
    ttl: int | None = None,
) -> CacheService:
    """
    获取缓存实例的便捷函数

    Args:
        name: 缓存名称
        max_size: 最大缓存条目
        ttl: 默认 TTL（秒）

    Returns:
        CacheService 实例
    """
    return multi_cache.get_cache(name, max_size=max_size, ttl=ttl)
