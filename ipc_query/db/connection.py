"""
数据库连接管理

提供数据库连接的创建、配置和管理功能。
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, cast

from ..constants import DB_BUSY_TIMEOUT_MS, DB_CACHE_SIZE, DB_MMAP_SIZE
from ..exceptions import DatabaseConnectionError, DatabaseError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class Database:
    """
    数据库管理类

    管理SQLite数据库连接，提供连接池和配置优化。
    """

    def __init__(self, db_path: Path, readonly: bool = True):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径
            readonly: 是否以只读模式打开
        """
        self.db_path = db_path
        self.readonly = readonly
        self._local = threading.local()
        self._lock = threading.Lock()
        self._connections: dict[int, sqlite3.Connection] = {}

        if not db_path.exists():
            if readonly:
                raise DatabaseConnectionError(f"Database not found: {db_path}")
            db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Database initialized",
            extra_fields={
                "db_path": str(db_path),
                "readonly": readonly,
            },
        )

    def _create_connection(self) -> sqlite3.Connection:
        """创建新的数据库连接"""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row

        # 配置PRAGMA
        self._configure_pragma(conn)
        with self._lock:
            self._connections[id(conn)] = conn

        return conn

    def _configure_pragma(self, conn: sqlite3.Connection) -> None:
        """配置数据库PRAGMA参数"""
        pragmas = [
            ("case_sensitive_like", "ON"),
            ("busy_timeout", str(DB_BUSY_TIMEOUT_MS)),
            ("cache_size", str(DB_CACHE_SIZE)),
            ("mmap_size", str(DB_MMAP_SIZE)),
            ("temp_store", "MEMORY"),
        ]

        if self.readonly:
            pragmas.append(("query_only", "ON"))
        else:
            pragmas.append(("foreign_keys", "ON"))

        for pragma, value in pragmas:
            try:
                conn.execute(f"PRAGMA {pragma}={value};")
            except sqlite3.OperationalError:
                pass  # 忽略不支持的PRAGMA

    def get_connection(self) -> sqlite3.Connection:
        """
        获取数据库连接（线程本地）

        Returns:
            数据库连接对象
        """
        conn = cast(sqlite3.Connection | None, getattr(self._local, "conn", None))
        if conn is None:
            conn = self._create_connection()
            self._local.conn = conn
        return conn

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        获取数据库连接的上下文管理器

        Yields:
            数据库连接对象
        """
        conn = self.get_connection()
        try:
            yield conn
        except sqlite3.Error as e:
            logger.error(
                "Database error",
                extra_fields={"error": str(e)},
            )
            raise DatabaseError(f"Database error: {e}") from e

    def close(self) -> None:
        """关闭当前线程的连接"""
        conn = cast(sqlite3.Connection | None, getattr(self._local, "conn", None))
        if conn is None:
            return
        with self._lock:
            self._connections.pop(id(conn), None)
        try:
            conn.close()
        finally:
            self._local.conn = None
        logger.info("Database connection closed")

    def close_all(self) -> None:
        """关闭所有连接（主要用于测试）"""
        with self._lock:
            conns = list(self._connections.values())
            self._connections.clear()
        for conn in conns:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        self._local.conn = None

    def optimize(self) -> None:
        """
        优化数据库

        - 创建缺失的索引
        - 执行ANALYZE更新统计信息
        """
        if self.readonly:
            logger.info("Skip database optimize in readonly mode")
            return

        with self.connection() as conn:
            # 检查并创建FTS5索引（如果不存在）
            try:
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='parts_fts'
                """)
                fts_exists = cursor.fetchone() is not None
            except Exception:
                fts_exists = False

            if not fts_exists:
                logger.info("Creating FTS5 index...")
                self._create_fts_index(conn)

            # 更新统计信息
            conn.execute("ANALYZE")
            logger.info("Database optimized")

    def _create_fts_index(self, conn: sqlite3.Connection) -> None:
        """创建全文搜索索引"""
        conn.executescript("""
            -- 创建FTS5虚拟表
            CREATE VIRTUAL TABLE IF NOT EXISTS parts_fts USING fts5(
                part_number_canonical,
                nomenclature,
                nomenclature_clean,
                content='parts',
                content_rowid='id'
            );

            -- 创建触发器：插入
            CREATE TRIGGER IF NOT EXISTS parts_fts_ai AFTER INSERT ON parts BEGIN
                INSERT INTO parts_fts(rowid, part_number_canonical, nomenclature, nomenclature_clean)
                VALUES (new.id, new.part_number_canonical, new.nomenclature, new.nomenclature_clean);
            END;

            -- 创建触发器：删除
            CREATE TRIGGER IF NOT EXISTS parts_fts_ad AFTER DELETE ON parts BEGIN
                INSERT INTO parts_fts(parts_fts, rowid, part_number_canonical, nomenclature, nomenclature_clean)
                VALUES ('delete', old.id, old.part_number_canonical, old.nomenclature, old.nomenclature_clean);
            END;

            -- 创建触发器：更新
            CREATE TRIGGER IF NOT EXISTS parts_fts_au AFTER UPDATE ON parts BEGIN
                INSERT INTO parts_fts(parts_fts, rowid, part_number_canonical, nomenclature, nomenclature_clean)
                VALUES ('delete', old.id, old.part_number_canonical, old.nomenclature, old.nomenclature_clean);
                INSERT INTO parts_fts(rowid, part_number_canonical, nomenclature, nomenclature_clean)
                VALUES (new.id, new.part_number_canonical, new.nomenclature, new.nomenclature_clean);
            END;

            -- 填充现有数据
            INSERT INTO parts_fts(rowid, part_number_canonical, nomenclature, nomenclature_clean)
            SELECT id, part_number_canonical, nomenclature, nomenclature_clean FROM parts;
        """)
        conn.commit()

    def check_health(self) -> dict[str, Any]:
        """
        检查数据库健康状态

        Returns:
            健康状态字典
        """
        try:
            with self.connection() as conn:
                # 检查连接
                conn.execute("SELECT 1")

                # 获取表信息
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
                table_names = [t["name"] for t in tables]

                # 获取零件数量
                parts_count = conn.execute("SELECT COUNT(*) as cnt FROM parts").fetchone()["cnt"]

                # 获取文档数量
                docs_count = conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()["cnt"]

                return {
                    "status": "healthy",
                    "tables": table_names,
                    "parts_count": parts_count,
                    "documents_count": docs_count,
                }
        except Exception as e:
            logger.warning(
                "Database health check failed",
                extra_fields={"error": str(e)},
            )
            return {
                "status": "unhealthy",
                "error": "database_error",
            }

    def execute(
        self,
        query: str,
        params: tuple | None = None,
    ) -> list[sqlite3.Row]:
        """
        执行查询并返回结果

        Args:
            query: SQL查询语句
            params: 查询参数

        Returns:
            查询结果列表
        """
        with self.connection() as conn:
            if params:
                cursor = conn.execute(query, params)
            else:
                cursor = conn.execute(query)
            return cursor.fetchall()

    def execute_one(
        self,
        query: str,
        params: tuple | None = None,
    ) -> sqlite3.Row | None:
        """
        执行查询并返回单条结果

        Args:
            query: SQL查询语句
            params: 查询参数

        Returns:
            单条查询结果或None
        """
        results = self.execute(query, params)
        return results[0] if results else None


def create_database(
    db_path: Path,
    readonly: bool = True,
) -> Database:
    """
    创建数据库实例的工厂函数

    Args:
        db_path: 数据库文件路径
        readonly: 是否以只读模式打开

    Returns:
        Database实例
    """
    return Database(db_path, readonly=readonly)
