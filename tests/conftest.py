"""
pytest 配置和共享 fixtures

提供测试所需的通用 fixtures 和配置。
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

# 添加项目根目录到路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """创建临时数据库文件路径"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    # 清理
    if path.exists():
        path.unlink()


@pytest.fixture
def sample_db(temp_db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """
    创建包含示例数据的测试数据库

    Returns:
        sqlite3.Connection: 数据库连接
    """
    conn = sqlite3.connect(str(temp_db_path))
    conn.row_factory = sqlite3.Row

    # 创建表结构
    conn.executescript("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pdf_name TEXT NOT NULL,
            pdf_path TEXT,
            miner_dir TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            page_num INTEGER NOT NULL,
            figure_label TEXT,
            date_text TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );

        CREATE TABLE parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            page_num INTEGER NOT NULL,
            page_end INTEGER,
            extractor TEXT,
            meta_data_raw TEXT,
            figure_code TEXT,
            row_kind TEXT DEFAULT 'part',
            fig_item_raw TEXT,
            fig_item_no TEXT,
            fig_item_no_source TEXT,
            not_illustrated INTEGER DEFAULT 0,
            part_number_cell TEXT,
            part_number_extracted TEXT,
            part_number_canonical TEXT,
            pn_corrected INTEGER DEFAULT 0,
            pn_method TEXT,
            pn_best_similarity REAL,
            pn_needs_review INTEGER DEFAULT 0,
            correction_note TEXT,
            nom_level INTEGER DEFAULT 0,
            nomenclature TEXT,
            nomenclature_clean TEXT,
            parent_part_id INTEGER,
            attached_to_part_id INTEGER,
            effectivity TEXT,
            units_per_assy TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(id),
            FOREIGN KEY (parent_part_id) REFERENCES parts(id)
        );

        CREATE TABLE aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id INTEGER NOT NULL,
            alias_value TEXT NOT NULL,
            FOREIGN KEY (part_id) REFERENCES parts(id)
        );

        CREATE TABLE xrefs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            target TEXT NOT NULL,
            FOREIGN KEY (part_id) REFERENCES parts(id)
        );

        CREATE INDEX idx_parts_pn_canonical ON parts(part_number_canonical);
        CREATE INDEX idx_parts_pn_extracted ON parts(part_number_extracted);
        CREATE INDEX idx_parts_pn_cell ON parts(part_number_cell);
        CREATE INDEX idx_parts_nom_clean ON parts(nomenclature_clean);
        CREATE INDEX idx_parts_parent ON parts(parent_part_id);
        CREATE INDEX idx_aliases_value ON aliases(alias_value);
    """)

    # 插入测试数据
    conn.execute(
        "INSERT INTO documents (id, pdf_name, pdf_path) VALUES (1, 'test_doc.pdf', '/path/to/test_doc.pdf')"
    )
    conn.execute(
        "INSERT INTO pages (document_id, page_num, figure_label, date_text) VALUES (1, 1, 'FIG 1', '2024-01-01')"
    )

    # 插入零件数据 - 使用明确的列名
    # 零件 1: ID=1, 无父级
    conn.execute(
        """
        INSERT INTO parts (
            document_id, page_num, figure_code, row_kind,
            fig_item_raw, fig_item_no, not_illustrated,
            part_number_cell, part_number_extracted, part_number_canonical,
            nom_level, nomenclature, nomenclature_clean, parent_part_id
        ) VALUES (1, 1, 'A', 'part', '1', '1', 0, '113A4200-1', '113A4200-1', '113A4200-1', 1, 'BRACKET', 'BRACKET', NULL)
        """
    )
    # 零件 2: ID=2, 无父级
    conn.execute(
        """
        INSERT INTO parts (
            document_id, page_num, figure_code, row_kind,
            fig_item_raw, fig_item_no, not_illustrated,
            part_number_cell, part_number_extracted, part_number_canonical,
            nom_level, nomenclature, nomenclature_clean, parent_part_id
        ) VALUES (1, 1, 'A', 'part', '2', '2', 0, '113A4200-2', '113A4200-2', '113A4200-2', 2, 'ASSY', 'ASSY', NULL)
        """
    )
    # 零件 3: ID=3, parent_part_id=2
    conn.execute(
        """
        INSERT INTO parts (
            document_id, page_num, figure_code, row_kind,
            fig_item_raw, fig_item_no, not_illustrated,
            part_number_cell, part_number_extracted, part_number_canonical,
            nom_level, nomenclature, nomenclature_clean, parent_part_id
        ) VALUES (1, 1, 'A', 'part', '3', '3', 0, '113A4200-3', '113A4200-3', '113A4200-3', 2, 'COVER', 'COVER', 2)
        """
    )
    # 零件 4: ID=4
    conn.execute(
        """
        INSERT INTO parts (
            document_id, page_num, figure_code, row_kind,
            fig_item_raw, fig_item_no, not_illustrated,
            part_number_cell, part_number_extracted, part_number_canonical,
            nom_level, nomenclature, nomenclature_clean, parent_part_id
        ) VALUES (1, 1, 'B', 'part', '4', '4', 0, '123B5000-1', '123B5000-1', '123B5000-1', 1, 'PLATE', 'PLATE', NULL)
        """
    )
    # 零件 5: ID=5
    conn.execute(
        """
        INSERT INTO parts (
            document_id, page_num, figure_code, row_kind,
            fig_item_raw, fig_item_no, not_illustrated,
            part_number_cell, part_number_extracted, part_number_canonical,
            nom_level, nomenclature, nomenclature_clean, parent_part_id
        ) VALUES (1, 1, 'B', 'part', '5', '5', 0, '123B5000-2', '123B5000-2', '123B5000-2', 1, 'SCREW', 'SCREW', NULL)
        """
    )
    # 注释行: ID=6
    conn.execute(
        """
        INSERT INTO parts (
            document_id, page_num, figure_code, row_kind,
            fig_item_raw, fig_item_no, not_illustrated,
            nom_level, nomenclature, nomenclature_clean
        ) VALUES (1, 1, 'B', 'note', '6', '6', 0, 0, 'NOTE: For reference', 'NOTE: For reference')
        """
    )

    # 插入别名
    conn.execute(
        "INSERT INTO aliases (part_id, alias_value) VALUES (1, '113A4200-1-ALT')"
    )

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def mock_config() -> MagicMock:
    """创建模拟配置对象"""
    config = MagicMock()
    config.default_page_size = 20
    config.max_page_size = 100
    config.db_path = Path(":memory:")
    config.pdf_dir = None
    config.log_level = "DEBUG"
    config.log_format = "text"
    return config


@pytest.fixture
def mock_database(sample_db: sqlite3.Connection) -> MagicMock:
    """创建模拟数据库对象"""
    from ipc_query.db.connection import Database

    db = MagicMock(spec=Database)
    db._path = ":memory:"
    db._connection = sample_db

    def execute(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return sample_db.execute(sql, params).fetchall()

    def execute_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return sample_db.execute(sql, params).fetchone()

    db.execute = execute
    db.execute_one = execute_one

    def connection():
        class ConnCtx:
            def __enter__(self):
                return sample_db
            def __exit__(self, *args):
                pass
        return ConnCtx()

    db.connection = connection
    return db


@pytest.fixture
def cache_service():
    """创建缓存服务实例"""
    from ipc_query.services.cache import CacheService
    cache = CacheService(max_size=100, ttl_seconds=60)
    yield cache
    cache.clear()


@pytest.fixture
def multi_cache():
    """创建多缓存管理器实例"""
    from ipc_query.services.cache import MultiCache
    mc = MultiCache()
    yield mc
    mc.clear_all()
