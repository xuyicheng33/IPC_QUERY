"""
搜索服务单元测试

测试 SearchService 的核心功能。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ipc_query.services.search import SearchService, create_search_service
from ipc_query.exceptions import SearchError


class TestSearchService:
    """SearchService 测试"""

    @pytest.fixture
    def mock_part_repo(self) -> MagicMock:
        """创建模拟零件仓库"""
        repo = MagicMock()
        repo.search_by_pn.return_value = ([], 0)
        repo.search_by_term.return_value = ([], 0)
        repo.search_all.return_value = ([], 0)
        repo.get_detail.return_value = None
        return repo

    @pytest.fixture
    def search_service(self, mock_part_repo: MagicMock, mock_config: MagicMock) -> SearchService:
        """创建搜索服务实例"""
        # 创建新的缓存实例以避免状态污染
        from ipc_query.services.cache import CacheService
        service = SearchService(mock_part_repo, mock_config)
        service._cache = CacheService(max_size=100, ttl_seconds=60)
        return service

    def test_search_empty_query(self, search_service: SearchService) -> None:
        """空查询返回空结果"""
        result = search_service.search("")
        assert result["results"] == []
        assert result["total"] == 0

    def test_search_whitespace_query(self, search_service: SearchService) -> None:
        """纯空格查询返回空结果"""
        result = search_service.search("   ")
        assert result["results"] == []
        assert result["total"] == 0

    def test_search_none_query(self, search_service: SearchService) -> None:
        """None 查询返回空结果"""
        result = search_service.search(None)  # type: ignore
        assert result["results"] == []
        assert result["total"] == 0

    def test_search_by_pn(self, search_service: SearchService, mock_part_repo: MagicMock) -> None:
        """件号搜索调用正确的仓库方法"""
        mock_part_repo.search_by_pn.return_value = (
            [{"id": 1, "part_number_canonical": "113A4200-1"}],
            1
        )

        result = search_service.search("113A4200-1", match="pn")

        mock_part_repo.search_by_pn.assert_called_once()
        assert result["total"] == 1
        assert len(result["results"]) == 1

    def test_search_by_term(self, search_service: SearchService, mock_part_repo: MagicMock) -> None:
        """术语搜索调用正确的仓库方法"""
        mock_part_repo.search_by_term.return_value = (
            [{"id": 1, "nomenclature_clean": "BRACKET"}],
            1
        )

        result = search_service.search("BRACKET", match="term")

        mock_part_repo.search_by_term.assert_called_once()
        assert result["total"] == 1

    def test_search_all(self, search_service: SearchService, mock_part_repo: MagicMock) -> None:
        """综合搜索调用正确的仓库方法"""
        mock_part_repo.search_all.return_value = (
            [{"id": 1, "part_number_canonical": "113A4200-1"}],
            1
        )

        result = search_service.search("113A4200", match="all")

        mock_part_repo.search_all.assert_called_once()
        assert result["total"] == 1

    def test_search_invalid_match_defaults_to_all(
        self, search_service: SearchService, mock_part_repo: MagicMock
    ) -> None:
        """无效的匹配模式默认使用 all"""
        mock_part_repo.search_all.return_value = ([], 0)

        result = search_service.search("test", match="invalid")

        mock_part_repo.search_all.assert_called_once()

    def test_search_caching(self, search_service: SearchService, mock_part_repo: MagicMock) -> None:
        """相同查询命中缓存"""
        mock_part_repo.search_by_pn.return_value = (
            [{"id": 1, "part_number_canonical": "113A4200-1"}],
            1
        )

        # 第一次查询
        result1 = search_service.search("113A4200-1", match="pn")
        # 第二次查询（应该命中缓存）
        result2 = search_service.search("113A4200-1", match="pn")

        # 仓库只被调用一次
        assert mock_part_repo.search_by_pn.call_count == 1
        assert result1 == result2

    def test_search_pagination(self, search_service: SearchService, mock_part_repo: MagicMock) -> None:
        """分页参数正确传递"""
        mock_part_repo.search_all.return_value = ([], 0)

        search_service.search("test", match="all", page=2, page_size=50)

        call_args = mock_part_repo.search_all.call_args
        assert call_args.kwargs["limit"] == 50
        assert call_args.kwargs["offset"] == 50  # (page-1) * page_size

    def test_search_respects_max_page_size(
        self, search_service: SearchService, mock_part_repo: MagicMock, mock_config: MagicMock
    ) -> None:
        """页大小不超过最大值"""
        mock_config.max_page_size = 50
        mock_part_repo.search_all.return_value = ([], 0)

        search_service.search("test", page_size=1000)

        call_args = mock_part_repo.search_all.call_args
        assert call_args.kwargs["limit"] == 50  # 被限制为 max_page_size

    def test_search_fallback_to_contains(
        self, search_service: SearchService, mock_part_repo: MagicMock
    ) -> None:
        """件号搜索无结果时回退到包含匹配"""
        # 精确匹配返回 0 结果
        # 包含匹配返回结果
        mock_part_repo.search_by_pn.side_effect = [
            ([], 0),  # 第一次调用（精确匹配）
            ([{"id": 1}], 1),  # 第二次调用（包含匹配）
        ]

        result = search_service.search("ABC", match="pn")

        assert mock_part_repo.search_by_pn.call_count == 2
        assert result["total"] == 1

    def test_search_no_fallback_for_short_query(
        self, search_service: SearchService, mock_part_repo: MagicMock
    ) -> None:
        """短查询不触发包含匹配回退"""
        mock_part_repo.search_by_pn.return_value = ([], 0)

        search_service.search("AB", match="pn")  # 只有2个字符

        # 只调用一次（精确匹配），不触发包含匹配
        assert mock_part_repo.search_by_pn.call_count == 1

    def test_search_raises_search_error_on_exception(
        self, search_service: SearchService, mock_part_repo: MagicMock
    ) -> None:
        """搜索异常抛出 SearchError"""
        mock_part_repo.search_all.side_effect = Exception("Database error")

        with pytest.raises(SearchError) as exc_info:
            search_service.search("test")

        assert "Search failed" in str(exc_info.value)

    def test_search_includes_notes_flag(
        self, search_service: SearchService, mock_part_repo: MagicMock
    ) -> None:
        """include_notes 参数正确传递"""
        mock_part_repo.search_all.return_value = ([], 0)

        search_service.search("test", include_notes=True)

        call_args = mock_part_repo.search_all.call_args
        assert call_args.kwargs["include_notes"] is True

    def test_search_result_has_more(
        self, search_service: SearchService, mock_part_repo: MagicMock
    ) -> None:
        """结果包含 has_more 字段"""
        mock_part_repo.search_all.return_value = (
            [{"id": 1}],
            100  # 总数大于当前页
        )

        result = search_service.search("test", page=1, page_size=10)

        assert result["has_more"] is True

    def test_search_result_no_more(
        self, search_service: SearchService, mock_part_repo: MagicMock
    ) -> None:
        """结果 has_more 为 False 当没有更多结果"""
        mock_part_repo.search_all.return_value = (
            [{"id": 1}],
            5  # 总数小于下一页起始位置
        )

        result = search_service.search("test", page=1, page_size=10)

        assert result["has_more"] is False


class TestGetPartDetail:
    """获取零件详情测试"""

    @pytest.fixture
    def mock_part_repo(self) -> MagicMock:
        repo = MagicMock()
        repo.get_detail.return_value = None
        return repo

    @pytest.fixture
    def search_service(self, mock_part_repo: MagicMock, mock_config: MagicMock) -> SearchService:
        from ipc_query.services.cache import CacheService
        service = SearchService(mock_part_repo, mock_config)
        service._cache = CacheService(max_size=100, ttl_seconds=60)
        return service

    def test_get_part_detail_not_found(
        self, search_service: SearchService, mock_part_repo: MagicMock
    ) -> None:
        """零件不存在返回 None"""
        mock_part_repo.get_detail.return_value = None

        result = search_service.get_part_detail(999)

        assert result is None

    def test_get_part_detail_found(
        self, search_service: SearchService, mock_part_repo: MagicMock
    ) -> None:
        """找到零件返回详情"""
        mock_detail = MagicMock()
        mock_detail.to_dict.return_value = {"id": 1, "part_number_canonical": "113A4200-1"}
        mock_part_repo.get_detail.return_value = mock_detail

        result = search_service.get_part_detail(1)

        assert result is not None
        assert result["id"] == 1

    def test_get_part_detail_caching(
        self, search_service: SearchService, mock_part_repo: MagicMock
    ) -> None:
        """详情查询命中缓存"""
        mock_detail = MagicMock()
        mock_detail.to_dict.return_value = {"id": 1}
        mock_part_repo.get_detail.return_value = mock_detail

        # 第一次查询
        search_service.get_part_detail(1)
        # 第二次查询（应该命中缓存）
        search_service.get_part_detail(1)

        # 仓库只被调用一次
        assert mock_part_repo.get_detail.call_count == 1


class TestWarmup:
    """预热测试"""

    @pytest.fixture
    def mock_part_repo(self) -> MagicMock:
        repo = MagicMock()
        repo.search_by_pn.return_value = ([], 0)
        return repo

    @pytest.fixture
    def search_service(self, mock_part_repo: MagicMock, mock_config: MagicMock) -> SearchService:
        from ipc_query.services.cache import CacheService
        service = SearchService(mock_part_repo, mock_config)
        service._cache = CacheService(max_size=100, ttl_seconds=60)
        return service

    def test_warmup_success(self, search_service: SearchService, mock_part_repo: MagicMock) -> None:
        """预热成功执行搜索"""
        mock_part_repo.search_by_pn.return_value = ([], 0)

        search_service.warmup()

        # 预热会调用搜索，由于有 fallback 逻辑可能调用多次
        assert mock_part_repo.search_by_pn.call_count >= 1

    def test_warmup_failure_does_not_raise(
        self, search_service: SearchService, mock_part_repo: MagicMock
    ) -> None:
        """预热失败不抛出异常"""
        mock_part_repo.search_by_pn.side_effect = Exception("Connection error")

        # 不应该抛出异常
        search_service.warmup()

    def test_warmup_custom_query(
        self, search_service: SearchService, mock_part_repo: MagicMock
    ) -> None:
        """预热使用自定义查询"""
        search_service.warmup("CUSTOM-QUERY")

        # 参数通过 kwargs 传递
        call_args = mock_part_repo.search_by_pn.call_args
        assert call_args.kwargs["query"] == "CUSTOM-QUERY"


class TestCreateSearchService:
    """工厂函数测试"""

    def test_create_search_service(self, mock_config: MagicMock) -> None:
        """工厂函数创建正确的实例"""
        from ipc_query.db.repository import PartRepository
        from ipc_query.db.connection import Database

        mock_db = MagicMock(spec=Database)
        repo = PartRepository(mock_db)

        service = create_search_service(repo, mock_config)

        assert isinstance(service, SearchService)
        assert service._repo is repo
        assert service._config is mock_config
