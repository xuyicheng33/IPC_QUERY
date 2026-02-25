"""
搜索服务模块

提供零件搜索功能，集成缓存优化。
"""

from __future__ import annotations

import time
from typing import Any

from ..config import Config
from ..db.repository import PartRepository
from ..exceptions import SearchError, ValidationError
from ..utils.logger import get_logger
from ..utils.metrics import metrics
from .cache import get_cache

logger = get_logger(__name__)


class SearchService:
    """
    搜索服务

    提供零件搜索功能，支持件号搜索、术语搜索和综合搜索。
    集成缓存优化，提升查询性能。
    """

    def __init__(
        self,
        part_repo: PartRepository,
        config: Config,
    ):
        self._repo = part_repo
        self._config = config
        self._cache = get_cache("search_results")

    def search(
        self,
        query: str,
        match: str = "all",
        page: int = 1,
        page_size: int | None = None,
        include_notes: bool = False,
    ) -> dict[str, Any]:
        """
        搜索零件

        Args:
            query: 查询词
            match: 匹配模式 (pn/term/all)
            page: 页码
            page_size: 每页数量
            include_notes: 是否包含注释行

        Returns:
            搜索结果字典
        """
        # 参数验证
        query = (query or "").strip()
        if not query:
            return {
                "results": [],
                "total": 0,
                "page": page,
                "page_size": page_size or self._config.default_page_size,
            }

        # 参数处理
        page_size = min(
            page_size or self._config.default_page_size,
            self._config.max_page_size,
        )
        offset = (page - 1) * page_size
        match = (match or "all").lower()
        if match not in ("pn", "term", "all"):
            match = "all"

        # 检查缓存
        cache_key = f"{query}:{match}:{page}:{page_size}:{include_notes}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            metrics.record_search(0, cache_hit=True)
            logger.debug(
                "Search cache hit",
                extra_fields={"query": query, "match": match},
            )
            return cached

        # 执行搜索
        start_time = time.perf_counter()
        try:
            results, total = self._do_search(
                query=query,
                match=match,
                offset=offset,
                limit=page_size,
                include_notes=include_notes,
            )
        except Exception as e:
            logger.error(
                "Search failed",
                extra_fields={"query": query, "error": str(e)},
            )
            raise SearchError(f"Search failed: {e}") from e

        duration_ms = (time.perf_counter() - start_time) * 1000
        metrics.record_search(duration_ms, cache_hit=False)

        # 构建结果
        result = {
            "results": results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": total > page * page_size,
        }

        # 存入缓存
        self._cache.set(cache_key, result, ttl=60)

        logger.info(
            "Search completed",
            extra_fields={
                "query": query,
                "match": match,
                "total": total,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return result

    def _do_search(
        self,
        query: str,
        match: str,
        offset: int,
        limit: int,
        include_notes: bool,
    ) -> tuple[list[dict[str, Any]], int]:
        """执行搜索"""
        if match == "pn":
            # 件号搜索
            results, total = self._repo.search_by_pn(
                query=query,
                limit=limit,
                offset=offset,
                include_notes=include_notes,
                enable_contains=False,
            )
            # 如果没有结果，尝试包含匹配
            if total == 0 and len(query) >= 3:
                results, total = self._repo.search_by_pn(
                    query=query,
                    limit=limit,
                    offset=offset,
                    include_notes=include_notes,
                    enable_contains=True,
                )
        elif match == "term":
            # 术语搜索
            results, total = self._repo.search_by_term(
                query=query,
                limit=limit,
                offset=offset,
                include_notes=include_notes,
            )
        else:
            # 综合搜索
            results, total = self._repo.search_all(
                query=query,
                limit=limit,
                offset=offset,
                include_notes=include_notes,
            )

        return results, total

    def get_part_detail(self, part_id: int) -> dict[str, Any] | None:
        """
        获取零件详情

        Args:
            part_id: 零件ID

        Returns:
            零件详情或None
        """
        # 检查缓存
        cache_key = f"detail:{part_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # 查询数据库
        start_time = time.perf_counter()
        detail = self._repo.get_detail(part_id)

        if detail is None:
            return None

        duration_ms = (time.perf_counter() - start_time) * 1000

        # 转换为字典
        result = detail.to_dict()

        # 存入缓存
        self._cache.set(cache_key, result, ttl=300)

        logger.debug(
            "Part detail fetched",
            extra_fields={
                "part_id": part_id,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return result

    def warmup(self, query: str = "113A4200-2") -> None:
        """
        预热缓存

        执行一次搜索以预热数据库连接和缓存。

        Args:
            query: 预热查询词
        """
        try:
            self.search(query, match="pn", page=1, page_size=1)
            logger.info("Search warmup completed")
        except Exception as e:
            logger.warning(
                "Search warmup failed",
                extra_fields={"error": str(e)},
            )


def create_search_service(
    part_repo: PartRepository,
    config: Config,
) -> SearchService:
    """创建搜索服务实例"""
    return SearchService(part_repo, config)
