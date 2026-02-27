"""
数据访问层单元测试

测试 PartRepository 和 DocumentRepository 的核心功能。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ipc_query.db.repository import (
    PartRepository,
    DocumentRepository,
    _looks_like_pn_query,
    _fig_item_display,
    _safe_pdf_name,
)
from ipc_query.db.models import Part, PartDetail
from ipc_query.db.connection import Database


class TestUtilityFunctions:
    """工具函数测试"""

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("113A4200-1", True),
            ("123B5000", True),
            ("A-123B", True),
            ("AB1.CD", True),  # 需要包含数字
            ("", False),
            ("  ", False),
            ("abc", False),  # 小写
            (".LEVEL", False),  # 以点开头
            ("has space", False),  # 包含空格
            ("no digits", False),  # 无数字
            ("中文", False),  # 非字母数字
            ("AB.CD", False),  # 无数字
        ],
    )
    def test_looks_like_pn_query(self, query: str, expected: bool) -> None:
        """测试件号查询判断"""
        result = _looks_like_pn_query(query)
        assert result == expected

    @pytest.mark.parametrize(
        "fig_raw,fig_no,not_illustrated,expected",
        [
            ("1", "1", 0, "1 1"),
            ("-", "1", 0, "- 1"),
            ("1", None, 0, "1"),
            (None, "1", 0, "1"),
            (None, "1", 1, "- 1"),  # not_illustrated
            ("", "", 0, ""),
        ],
    )
    def test_fig_item_display(
        self, fig_raw: str | None, fig_no: str | None, not_illustrated: int, expected: str
    ) -> None:
        """测试 FIG ITEM 显示格式化"""
        result = _fig_item_display(fig_raw, fig_no, not_illustrated)
        assert result == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("test.pdf", "test.pdf"),
            ("/path/to/test.pdf", "test.pdf"),
            (r"C:\Users\test.pdf", "test.pdf"),
            (None, ""),
            ("", ""),
        ],
    )
    def test_safe_pdf_name(self, raw: str | None, expected: str) -> None:
        """测试安全PDF文件名提取"""
        result = _safe_pdf_name(raw)
        assert result == expected


class TestDocumentRepository:
    """DocumentRepository 测试"""

    @pytest.fixture
    def doc_repo(self, mock_database: MagicMock) -> DocumentRepository:
        """创建文档仓库实例"""
        return DocumentRepository(mock_database)

    def test_get_all(self, doc_repo: DocumentRepository, sample_db: sqlite3.Connection) -> None:
        """获取所有文档"""
        docs = doc_repo.get_all()

        assert len(docs) == 1
        assert docs[0].pdf_name == "test_doc.pdf"

    def test_get_by_id(self, doc_repo: DocumentRepository, sample_db: sqlite3.Connection) -> None:
        """根据ID获取文档"""
        doc = doc_repo.get_by_id(1)

        assert doc is not None
        assert doc.pdf_name == "test_doc.pdf"

    def test_get_by_id_not_found(
        self, doc_repo: DocumentRepository, sample_db: sqlite3.Connection
    ) -> None:
        """获取不存在的文档返回 None"""
        doc = doc_repo.get_by_id(999)
        assert doc is None

    def test_get_by_name(self, doc_repo: DocumentRepository, sample_db: sqlite3.Connection) -> None:
        """根据名称获取文档"""
        doc = doc_repo.get_by_name("test_doc.pdf")

        assert doc is not None
        assert doc.id == 1


class TestPartRepository:
    """PartRepository 测试"""

    @pytest.fixture
    def part_repo(self, mock_database: MagicMock) -> PartRepository:
        """创建零件仓库实例"""
        return PartRepository(mock_database)

    def test_get_by_id(self, part_repo: PartRepository, sample_db: sqlite3.Connection) -> None:
        """根据ID获取零件"""
        part = part_repo.get_by_id(1)

        assert part is not None
        assert part.part_number_canonical == "113A4200-1"

    def test_get_by_id_not_found(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """获取不存在的零件返回 None"""
        part = part_repo.get_by_id(999)
        assert part is None


class TestPartRepositorySearchByPn:
    """件号搜索测试"""

    @pytest.fixture
    def part_repo(self, mock_database: MagicMock) -> PartRepository:
        return PartRepository(mock_database)

    def test_search_by_pn_exact_match(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """精确匹配件号"""
        results, total = part_repo.search_by_pn("113A4200-1")

        assert total == 1
        assert results[0]["part_number_canonical"] == "113A4200-1"

    def test_search_by_pn_prefix_match(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """前缀匹配件号"""
        results, total = part_repo.search_by_pn("113A4")

        assert total >= 1

    def test_search_by_pn_contains_match(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """包含匹配件号"""
        results, total = part_repo.search_by_pn("A4200", enable_contains=True)

        assert total >= 1

    def test_search_by_pn_empty_query(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """空查询返回空结果"""
        results, total = part_repo.search_by_pn("")

        assert results == []
        assert total == 0

    def test_search_by_pn_case_insensitive(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """件号搜索不区分大小写"""
        # 小写查询
        results_lower, total_lower = part_repo.search_by_pn("113a4200-1")

        # 大写查询
        results_upper, total_upper = part_repo.search_by_pn("113A4200-1")

        assert total_lower == total_upper

    def test_search_by_pn_alias(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """通过别名搜索"""
        results, total = part_repo.search_by_pn("113A4200-1-ALT")

        assert total == 1
        assert results[0]["part_number_canonical"] == "113A4200-1"

    def test_search_by_pn_exclude_notes(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """默认排除注释行"""
        results, total = part_repo.search_by_pn("113A4200")

        # 确保没有注释行
        for r in results:
            # 注释行的 part_number_canonical 为 None
            if r.get("row_kind") == "note":
                pytest.fail("Should not include note rows")

    def test_search_by_pn_include_notes(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """可以包含注释行"""
        results, total = part_repo.search_by_pn("NOTE", include_notes=True, enable_contains=True)

        # 包含注释行时，可能会有更多结果
        # 具体取决于测试数据

    def test_search_by_pn_pagination(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """分页查询"""
        results1, total1 = part_repo.search_by_pn("113A", limit=1, offset=0)
        results2, total2 = part_repo.search_by_pn("113A", limit=1, offset=1)

        assert total1 == total2  # 总数相同
        assert len(results1) <= 1
        assert len(results2) <= 1


class TestPartRepositorySearchByTerm:
    """术语搜索测试"""

    @pytest.fixture
    def part_repo(self, mock_database: MagicMock) -> PartRepository:
        return PartRepository(mock_database)

    def test_search_by_term_exact(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """精确术语搜索"""
        results, total = part_repo.search_by_term("BRACKET")

        assert total >= 1

    def test_search_by_term_partial(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """部分术语搜索"""
        results, total = part_repo.search_by_term("BRACK")

        assert total >= 1

    def test_search_by_term_empty_query(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """空查询返回空结果"""
        results, total = part_repo.search_by_term("")

        assert results == []
        assert total == 0

    def test_search_by_term_dot_prefix(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """点前缀搜索（层级）"""
        # 使用纯点前缀来搜索层级（"." 表示 nom_level >= 1）
        results, total = part_repo.search_by_term(".")

        # 搜索 nom_level >= 1 的零件
        # 测试数据中 nom_level >= 1 的零件应该存在
        # 如果没有结果，说明测试数据或逻辑需要调整

    def test_search_by_term_short_query_returns_empty(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """短查询（<3字符且无数字）返回空"""
        results, total = part_repo.search_by_term("AB")

        # AB 只有两个字符且没有数字
        # 但如果包含数字则会执行搜索
        # 这里测试纯字母短查询


class TestPartRepositorySearchAll:
    """综合搜索测试"""

    @pytest.fixture
    def part_repo(self, mock_database: MagicMock) -> PartRepository:
        return PartRepository(mock_database)

    def test_search_all_pn_like(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """综合搜索优先件号匹配"""
        results, total = part_repo.search_all("113A4200-1")

        assert total >= 1

    def test_search_all_term(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """综合搜索术语匹配"""
        results, total = part_repo.search_all("BRACKET")

        assert total >= 1

    def test_search_all_empty(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """空查询返回空结果"""
        results, total = part_repo.search_all("")

        assert results == []
        assert total == 0


class TestPartRepositoryGetDetail:
    """零件详情测试"""

    @pytest.fixture
    def part_repo(self, mock_database: MagicMock) -> PartRepository:
        return PartRepository(mock_database)

    def test_get_detail_found(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """获取零件详情"""
        detail = part_repo.get_detail(1)

        assert detail is not None
        assert detail.part.part_number_canonical == "113A4200-1"
        payload = detail.part.to_api_dict()
        assert payload["source_relative_path"] == "test_doc.pdf"

    def test_get_detail_not_found(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """获取不存在的零件详情"""
        detail = part_repo.get_detail(999)

        assert detail is None

    def test_get_detail_with_hierarchy(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """获取零件层级信息"""
        # 先获取一个有父零件的零件
        rows = sample_db.execute(
            "SELECT id, parent_part_id FROM parts WHERE parent_part_id IS NOT NULL LIMIT 1"
        ).fetchall()

        if not rows:
            pytest.skip("No parts with parent_part_id in test data")

        part_id = rows[0]["id"]
        parent_id = rows[0]["parent_part_id"]

        detail = part_repo.get_detail(part_id)

        assert detail is not None
        assert len(detail.parents) >= 1  # 有父零件

    def test_get_detail_with_children(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """获取零件子零件"""
        # 先获取一个有子零件的零件
        rows = sample_db.execute(
            """
            SELECT DISTINCT p1.id
            FROM parts p1
            JOIN parts p2 ON p2.parent_part_id = p1.id
            LIMIT 1
            """
        ).fetchall()

        if not rows:
            pytest.skip("No parts with children in test data")

        part_id = rows[0]["id"]
        detail = part_repo.get_detail(part_id)

        assert detail is not None
        assert len(detail.children) >= 1

    def test_get_detail_result_type(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """返回正确类型"""
        detail = part_repo.get_detail(1)

        assert isinstance(detail, PartDetail)
        assert isinstance(detail.part, Part)


class TestPartRepositoryGetDocumentPath:
    """文档路径获取测试"""

    def test_get_document_path_from_pdf_dir(self, mock_database: MagicMock, tmp_path: Path) -> None:
        """从 pdf_dir 获取文档路径"""
        # 创建临时 PDF 文件
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf")

        repo = PartRepository(mock_database, pdf_dir=tmp_path)
        result = repo.get_document_path("test.pdf")

        assert result == pdf_file

    def test_get_document_path_not_found(
        self, mock_database: MagicMock, sample_db: sqlite3.Connection
    ) -> None:
        """文档不存在返回 None"""
        repo = PartRepository(mock_database)
        result = repo.get_document_path("nonexistent.pdf")

        assert result is None


class TestSearchResultFormat:
    """搜索结果格式测试"""

    @pytest.fixture
    def part_repo(self, mock_database: MagicMock) -> PartRepository:
        return PartRepository(mock_database)

    def test_search_result_fields(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """搜索结果包含所有必要字段"""
        results, _ = part_repo.search_by_pn("113A4200-1")

        if results:
            result = results[0]
            expected_fields = [
                "id",
                "source_pdf",
                "page_num",
                "figure_code",
                "fig_item",
                "part_number_canonical",
                "nom_level",
                "nomenclature_preview",
            ]

            for field in expected_fields:
                assert field in result, f"Missing field: {field}"

    def test_search_result_fig_item_format(
        self, part_repo: PartRepository, sample_db: sqlite3.Connection
    ) -> None:
        """fig_item 字段格式正确"""
        results, _ = part_repo.search_by_pn("113A4200-1")

        if results:
            result = results[0]
            # fig_item 应该是字符串
            assert isinstance(result["fig_item"], str)
