"""
缓存服务单元测试

测试 CacheService 和 MultiCache 的核心功能。
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import patch

import pytest

from ipc_query.services.cache import CacheService, CacheEntry, MultiCache, get_cache


class TestCacheEntry:
    """CacheEntry 测试"""

    def test_is_expired_false_when_ttl_zero(self) -> None:
        """TTL 为 0 时永不过期"""
        entry = CacheEntry(value="test", created_at=time.time(), ttl=0)
        assert entry.is_expired() is False

    def test_is_expired_false_when_not_expired(self) -> None:
        """未过期时返回 False"""
        entry = CacheEntry(value="test", created_at=time.time(), ttl=100)
        assert entry.is_expired() is False

    def test_is_expired_true_when_expired(self) -> None:
        """过期时返回 True"""
        entry = CacheEntry(
            value="test",
            created_at=time.time() - 200,  # 200秒前创建
            ttl=100  # 100秒过期
        )
        assert entry.is_expired() is True


class TestCacheService:
    """CacheService 测试"""

    def test_set_and_get(self, cache_service: CacheService) -> None:
        """测试基本的 set/get 操作"""
        cache_service.set("key1", "value1")
        result = cache_service.get("key1")
        assert result == "value1"

    def test_get_missing_key(self, cache_service: CacheService) -> None:
        """获取不存在的键返回 None"""
        result = cache_service.get("nonexistent")
        assert result is None

    def test_set_overwrites_existing(self, cache_service: CacheService) -> None:
        """设置已存在的键会覆盖"""
        cache_service.set("key1", "value1")
        cache_service.set("key1", "value2")
        result = cache_service.get("key1")
        assert result == "value2"

    def test_delete_existing(self, cache_service: CacheService) -> None:
        """删除存在的键"""
        cache_service.set("key1", "value1")
        deleted = cache_service.delete("key1")
        assert deleted is True
        assert cache_service.get("key1") is None

    def test_delete_nonexistent(self, cache_service: CacheService) -> None:
        """删除不存在的键返回 False"""
        deleted = cache_service.delete("nonexistent")
        assert deleted is False

    def test_clear(self, cache_service: CacheService) -> None:
        """清空缓存"""
        cache_service.set("key1", "value1")
        cache_service.set("key2", "value2")
        cache_service.clear()
        assert cache_service.get("key1") is None
        assert cache_service.get("key2") is None

    def test_lru_eviction(self) -> None:
        """测试 LRU 淘汰"""
        cache = CacheService(max_size=3, ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # 应该淘汰 "a"

        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_lru_access_updates_order(self) -> None:
        """测试访问更新 LRU 顺序"""
        cache = CacheService(max_size=3, ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")  # 访问 "a"，使其变为最新
        cache.set("d", 4)  # 应该淘汰 "b"

        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_ttl_expiration(self) -> None:
        """测试 TTL 过期"""
        cache = CacheService(max_size=100, ttl_seconds=1)
        cache.set("key1", "value1", ttl=1)
        assert cache.get("key1") == "value1"

        # 模拟时间流逝
        with patch("time.time", return_value=time.time() + 2):
            result = cache.get("key1")
            assert result is None

    def test_invalidate_pattern(self, cache_service: CacheService) -> None:
        """测试按前缀删除"""
        cache_service.set("search:query1", "result1")
        cache_service.set("search:query2", "result2")
        cache_service.set("detail:123", "detail_data")

        deleted = cache_service.invalidate_pattern("search:")

        assert deleted == 2
        assert cache_service.get("search:query1") is None
        assert cache_service.get("search:query2") is None
        assert cache_service.get("detail:123") == "detail_data"

    def test_get_stats(self, cache_service: CacheService) -> None:
        """测试统计信息"""
        cache_service.set("key1", "value1")
        cache_service.get("key1")  # hit
        cache_service.get("key1")  # hit
        cache_service.get("nonexistent")  # miss

        stats = cache_service.get_stats()

        assert stats["size"] == 1
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2 / 3

    def test_cached_decorator(self, cache_service: CacheService) -> None:
        """测试缓存装饰器"""
        call_count = 0

        @cache_service.cached("test", key_func=lambda x: f"key:{x}")
        def expensive_func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # 第一次调用
        result1 = expensive_func(5)
        assert result1 == 10
        assert call_count == 1

        # 第二次调用（应该命中缓存）
        result2 = expensive_func(5)
        assert result2 == 10
        assert call_count == 1  # 没有增加

        # 不同参数
        result3 = expensive_func(10)
        assert result3 == 20
        assert call_count == 2

    def test_cached_decorator_default_key(self, cache_service: CacheService) -> None:
        """测试装饰器默认键生成"""
        call_count = 0

        @cache_service.cached("test")
        def func(a: int, b: str) -> str:
            nonlocal call_count
            call_count += 1
            return f"{a}:{b}"

        result1 = func(1, "x")
        assert result1 == "1:x"
        assert call_count == 1

        # 相同参数命中缓存
        result2 = func(1, "x")
        assert result2 == "1:x"
        assert call_count == 1


class TestMultiCache:
    """MultiCache 测试"""

    def test_get_cache_creates_new(self, multi_cache: MultiCache) -> None:
        """获取不存在的缓存会创建新实例"""
        cache = multi_cache.get_cache("test_cache", max_size=50, ttl=30)
        assert cache is not None
        assert cache._max_size == 50
        assert cache._default_ttl == 30

    def test_get_cache_returns_same_instance(self, multi_cache: MultiCache) -> None:
        """相同名称返回相同实例"""
        cache1 = multi_cache.get_cache("test_cache")
        cache2 = multi_cache.get_cache("test_cache")
        assert cache1 is cache2

    def test_get_all_stats(self, multi_cache: MultiCache) -> None:
        """测试获取所有缓存统计"""
        cache1 = multi_cache.get_cache("cache1")
        cache2 = multi_cache.get_cache("cache2")
        cache1.set("key1", "value1")
        cache2.set("key2", "value2")

        all_stats = multi_cache.get_all_stats()

        assert "cache1" in all_stats
        assert "cache2" in all_stats
        assert all_stats["cache1"]["size"] == 1
        assert all_stats["cache2"]["size"] == 1

    def test_clear_all(self, multi_cache: MultiCache) -> None:
        """测试清空所有缓存"""
        cache1 = multi_cache.get_cache("cache1")
        cache2 = multi_cache.get_cache("cache2")
        cache1.set("key1", "value1")
        cache2.set("key2", "value2")

        multi_cache.clear_all()

        assert cache1.get("key1") is None
        assert cache2.get("key2") is None

    def test_get_aggregate_stats(self, multi_cache: MultiCache) -> None:
        """测试聚合统计"""
        cache1 = multi_cache.get_cache("cache1")
        cache2 = multi_cache.get_cache("cache2")
        cache1.set("key1", "value1")
        cache1.get("key1")  # hit
        cache1.get("nonexistent")  # miss
        cache2.set("key2", "value2")
        cache2.get("key2")  # hit

        stats = multi_cache.get_aggregate_stats()

        assert stats["total_caches"] == 2
        assert stats["total_size"] == 2
        assert stats["total_hits"] == 2
        assert stats["total_misses"] == 1


class TestGetCache:
    """get_cache 便捷函数测试"""

    def test_get_cache_returns_cache_service(self) -> None:
        """get_cache 返回 CacheService 实例"""
        cache = get_cache("test_convenience")
        assert isinstance(cache, CacheService)


class TestCacheServiceThreadSafety:
    """缓存服务线程安全测试"""

    def test_concurrent_set_get(self) -> None:
        """测试并发读写"""
        import threading

        cache = CacheService(max_size=1000, ttl_seconds=60)
        errors: list[Exception] = []
        results: dict[str, Any] = {}

        def writer(start: int) -> None:
            try:
                for i in range(start, start + 100):
                    cache.set(f"key_{i}", i)
            except Exception as e:
                errors.append(e)

        def reader(prefix: str) -> None:
            try:
                for i in range(100):
                    cache.get(f"{prefix}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(0,)),
            threading.Thread(target=writer, args=(100,)),
            threading.Thread(target=reader, args=("key",)),
            threading.Thread(target=reader, args=("nonexistent",)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
