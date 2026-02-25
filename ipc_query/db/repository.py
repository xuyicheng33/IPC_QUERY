"""
数据访问层

封装所有数据库操作，提供清晰的数据访问接口。
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from .connection import Database
from .models import Document, Page, Part, XRef, Alias, SearchResult, PartDetail
from ..exceptions import PartNotFoundError, DatabaseError
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 查询模式
_PN_QUERY_RE = re.compile(r"^[A-Z0-9][A-Z0-9./-]*$")


def _looks_like_pn_query(q: str) -> bool:
    """判断查询是否像件号"""
    q = (q or "").strip().upper()
    if not q or q.startswith(".") or any(ch.isspace() for ch in q):
        return False
    if not any(ch.isdigit() for ch in q):
        return False
    return bool(_PN_QUERY_RE.fullmatch(q))


def _fig_item_display(fig_raw: str | None, fig_no: str | None, not_illustrated: int) -> str:
    """格式化 FIG ITEM 显示"""
    fig_raw = (fig_raw or "").strip()
    fig_no = (fig_no or "").strip()
    if fig_raw == "-" and fig_no:
        return f"- {fig_no}"
    if fig_raw and fig_no:
        return f"{fig_raw} {fig_no}"
    if fig_raw:
        return fig_raw
    if fig_no:
        return f"- {fig_no}" if not_illustrated else fig_no
    return ""


def _safe_pdf_name(raw: str) -> str:
    """安全的PDF文件名"""
    return (raw or "").replace("\\", "/").split("/")[-1]


class DocumentRepository:
    """文档数据访问"""

    def __init__(self, db: Database):
        self._db = db

    def get_all(self) -> list[Document]:
        """获取所有文档"""
        rows = self._db.execute(
            "SELECT id, pdf_name, pdf_path, miner_dir, created_at FROM documents ORDER BY pdf_name"
        )
        return [Document.from_row(dict(r)) for r in rows]

    def get_by_id(self, doc_id: int) -> Document | None:
        """根据ID获取文档"""
        row = self._db.execute_one(
            "SELECT id, pdf_name, pdf_path, miner_dir, created_at FROM documents WHERE id = ?",
            (doc_id,),
        )
        return Document.from_row(dict(row) if row else None)

    def get_by_name(self, pdf_name: str) -> Document | None:
        """根据名称获取文档"""
        row = self._db.execute_one(
            "SELECT id, pdf_name, pdf_path, miner_dir, created_at FROM documents WHERE pdf_name = ?",
            (pdf_name,),
        )
        return Document.from_row(dict(row) if row else None)


class PartRepository:
    """零件数据访问"""

    def __init__(self, db: Database, pdf_dir: Path | None = None):
        self._db = db
        self._pdf_dir = pdf_dir

    def get_by_id(self, part_id: int) -> Part | None:
        """根据ID获取零件"""
        row = self._db.execute_one(
            """
            SELECT p.*, d.pdf_name
            FROM parts p
            JOIN documents d ON d.id = p.document_id
            WHERE p.id = ?
            """,
            (part_id,),
        )
        return Part.from_row(dict(row) if row else None)

    def search_by_pn(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        include_notes: bool = False,
        enable_contains: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        按件号搜索

        Args:
            query: 查询词
            limit: 返回数量限制
            offset: 偏移量
            include_notes: 是否包含注释行
            enable_contains: 是否启用包含匹配

        Returns:
            (结果列表, 总数)
        """
        q = (query or "").strip().upper()
        if not q:
            return [], 0

        include_notes_int = 1 if include_notes else 0
        prefix = 1 if len(q) >= 4 else 0
        contains = 1 if (enable_contains and len(q) >= 3) else 0
        q_prefix = q + "%"
        q_contains = "%" + q + "%"

        hits = [
            "SELECT id AS id, 0 AS rank FROM parts WHERE part_number_canonical = :q",
            "SELECT id AS id, 1 AS rank FROM parts WHERE part_number_extracted = :q",
            "SELECT id AS id, 2 AS rank FROM parts WHERE part_number_cell = :q",
            "SELECT part_id AS id, 3 AS rank FROM aliases WHERE alias_value = :q",
        ]
        if prefix:
            hits.extend([
                "SELECT id AS id, 10 AS rank FROM parts WHERE part_number_canonical LIKE :q_prefix",
                "SELECT id AS id, 11 AS rank FROM parts WHERE part_number_extracted LIKE :q_prefix",
                "SELECT id AS id, 12 AS rank FROM parts WHERE part_number_cell LIKE :q_prefix",
                "SELECT part_id AS id, 13 AS rank FROM aliases WHERE alias_value LIKE :q_prefix",
            ])
        if contains:
            hits.extend([
                "SELECT id AS id, 20 AS rank FROM parts WHERE part_number_canonical LIKE :q_contains",
                "SELECT id AS id, 21 AS rank FROM parts WHERE part_number_extracted LIKE :q_contains",
                "SELECT id AS id, 22 AS rank FROM parts WHERE part_number_cell LIKE :q_contains",
                "SELECT part_id AS id, 23 AS rank FROM aliases WHERE alias_value LIKE :q_contains",
            ])

        hits_sql = "\n            UNION ALL\n            ".join(hits)
        with_cte = f"""
        WITH hits(id, rank) AS (
            {hits_sql}
        ),
        best AS (
            SELECT id, min(rank) AS rank FROM hits GROUP BY id
        )
        """

        count_sql = f"""
        {with_cte}
        SELECT count(1) AS n
        FROM best
        JOIN parts p ON p.id = best.id
        WHERE (:include_notes = 1 OR p.row_kind = 'part')
        """

        sql = f"""
        {with_cte}
        SELECT
          p.id,
          d.pdf_name AS source_pdf,
          p.page_num,
          p.page_end,
          p.extractor,
          p.figure_code,
          pg.figure_label,
          pg.date_text,
          p.row_kind,
          p.fig_item_raw,
          p.fig_item_no,
          p.fig_item_no_source,
          p.not_illustrated,
          p.part_number_cell,
          p.part_number_extracted,
          p.part_number_canonical,
          p.pn_corrected,
          p.pn_method,
          p.pn_best_similarity,
          p.pn_needs_review,
          p.correction_note,
          p.nom_level,
          p.nomenclature_clean,
          p.parent_part_id,
          p.effectivity,
          p.units_per_assy,
          substr(replace(coalesce(p.nomenclature_clean, p.nomenclature, ''), char(10), ' '), 1, 220) AS nomenclature_preview,
          substr(replace(coalesce(p.nomenclature, ''), char(10), ' '), 1, 220) AS nomenclature_preview_raw
        FROM best
        JOIN parts p ON p.id = best.id
        JOIN documents d ON d.id = p.document_id
        LEFT JOIN pages pg ON pg.document_id = p.document_id AND pg.page_num = p.page_num
        WHERE (:include_notes = 1 OR p.row_kind = 'part')
        ORDER BY
          best.rank,
          p.pn_needs_review DESC,
          coalesce(p.pn_best_similarity, 0.0) DESC,
          d.pdf_name,
          p.figure_code,
          p.page_num
        LIMIT :limit OFFSET :offset
        """

        params = {
            "q": q,
            "q_prefix": q_prefix,
            "q_contains": q_contains,
            "limit": limit,
            "offset": max(offset, 0),
            "include_notes": include_notes_int,
        }

        with self._db.connection() as conn:
            total_row = conn.execute(count_sql, params).fetchone()
            total = int(total_row["n"] if total_row else 0)
            rows = conn.execute(sql, params).fetchall()

        results = [self._row_to_search_result(r) for r in rows]
        return results, total

    def search_by_term(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        include_notes: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        按术语搜索

        Args:
            query: 查询词
            limit: 返回数量限制
            offset: 偏移量
            include_notes: 是否包含注释行

        Returns:
            (结果列表, 总数)
        """
        q = (query or "").strip().upper()
        if not q:
            return [], 0

        include_notes_int = 1 if include_notes else 0
        dotprefix = 1 if q.startswith(".") else 0
        term_kw = len(q) >= 3 or (len(q) >= 2 and any(ch.isdigit() for ch in q))

        if not dotprefix and not term_kw:
            return [], 0

        q_contains = "%" + q + "%"
        dot_only = bool(dotprefix) and (q.strip(".") == "")
        min_level = len(q) if dot_only else 0

        if dot_only:
            hits = [
                "SELECT id AS id, 0 AS rank FROM parts WHERE nom_level >= :min_level",
            ]
        else:
            hits = [
                "SELECT id AS id, 0 AS rank FROM parts WHERE nomenclature_clean LIKE :q_contains",
            ]

        if term_kw and not dotprefix:
            hits.append(
                "SELECT attached_to_part_id AS id, 1 AS rank FROM parts "
                "WHERE attached_to_part_id IS NOT NULL "
                "AND coalesce(nomenclature_clean, nomenclature, '') LIKE :q_contains"
            )

        hits_sql = "\n            UNION ALL\n            ".join(hits)
        with_cte = f"""
        WITH hits(id, rank) AS (
            {hits_sql}
        ),
        best AS (
            SELECT id, min(rank) AS rank FROM hits GROUP BY id
        )
        """

        count_sql = f"""
        {with_cte}
        SELECT count(1) AS n
        FROM best
        JOIN parts p ON p.id = best.id
        WHERE (:include_notes = 1 OR p.row_kind = 'part')
        """

        sql = f"""
        {with_cte}
        SELECT
          p.id,
          d.pdf_name AS source_pdf,
          p.page_num,
          p.page_end,
          p.extractor,
          p.figure_code,
          pg.figure_label,
          pg.date_text,
          p.row_kind,
          p.fig_item_raw,
          p.fig_item_no,
          p.fig_item_no_source,
          p.not_illustrated,
          p.part_number_cell,
          p.part_number_extracted,
          p.part_number_canonical,
          p.pn_corrected,
          p.pn_method,
          p.pn_best_similarity,
          p.pn_needs_review,
          p.correction_note,
          p.nom_level,
          p.nomenclature_clean,
          p.parent_part_id,
          p.effectivity,
          p.units_per_assy,
          substr(replace(coalesce(p.nomenclature_clean, p.nomenclature, ''), char(10), ' '), 1, 220) AS nomenclature_preview,
          substr(replace(coalesce(p.nomenclature, ''), char(10), ' '), 1, 220) AS nomenclature_preview_raw
        FROM best
        JOIN parts p ON p.id = best.id
        JOIN documents d ON d.id = p.document_id
        LEFT JOIN pages pg ON pg.document_id = p.document_id AND pg.page_num = p.page_num
        WHERE (:include_notes = 1 OR p.row_kind = 'part')
        ORDER BY
          best.rank,
          d.pdf_name,
          p.figure_code,
          p.page_num
        LIMIT :limit OFFSET :offset
        """

        params = {
            "q_contains": q_contains,
            "min_level": min_level,
            "limit": limit,
            "offset": max(offset, 0),
            "include_notes": include_notes_int,
        }

        with self._db.connection() as conn:
            total_row = conn.execute(count_sql, params).fetchone()
            total = int(total_row["n"] if total_row else 0)
            rows = conn.execute(sql, params).fetchall()

        results = [self._row_to_search_result(r) for r in rows]
        return results, total

    def search_all(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        include_notes: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        综合搜索（件号+术语）

        Args:
            query: 查询词
            limit: 返回数量限制
            offset: 偏移量
            include_notes: 是否包含注释行

        Returns:
            (结果列表, 总数)
        """
        q = (query or "").strip().upper()
        if not q:
            return [], 0

        include_notes_int = 1 if include_notes else 0
        pn_like = _looks_like_pn_query(q)
        term_kw = len(q) >= 3 or (len(q) >= 2 and any(ch.isdigit() for ch in q))

        prefix = 1 if len(q) >= 4 else 0
        contains = 1 if len(q) >= 3 else 0
        q_prefix = q + "%"
        q_contains = "%" + q + "%"

        dotprefix = 1 if q.startswith(".") else 0
        kw = 1 if term_kw else 0
        term_enabled = 1 if (dotprefix or kw) else 0

        dot_only = bool(dotprefix) and (q.strip(".") == "")
        term_dot_only = 1 if dot_only else 0
        min_level = len(q) if dot_only else 0

        # 排名策略
        pn_rank_offset = 0 if pn_like else 1000
        term_rank_offset = 1000 if pn_like else 0

        hits = [
            # PN匹配
            "SELECT id AS id, (:pn_rank_offset + 0) AS rank FROM parts WHERE part_number_canonical = :q",
            "SELECT id AS id, (:pn_rank_offset + 1) AS rank FROM parts WHERE part_number_extracted = :q",
            "SELECT id AS id, (:pn_rank_offset + 2) AS rank FROM parts WHERE part_number_cell = :q",
            "SELECT part_id AS id, (:pn_rank_offset + 3) AS rank FROM aliases WHERE alias_value = :q",
            "SELECT id AS id, (:pn_rank_offset + 10) AS rank FROM parts WHERE :prefix = 1 AND part_number_canonical LIKE :q_prefix",
            "SELECT id AS id, (:pn_rank_offset + 11) AS rank FROM parts WHERE :prefix = 1 AND part_number_extracted LIKE :q_prefix",
            "SELECT id AS id, (:pn_rank_offset + 12) AS rank FROM parts WHERE :prefix = 1 AND part_number_cell LIKE :q_prefix",
            "SELECT part_id AS id, (:pn_rank_offset + 13) AS rank FROM aliases WHERE :prefix = 1 AND alias_value LIKE :q_prefix",
            "SELECT id AS id, (:pn_rank_offset + 20) AS rank FROM parts WHERE :contains = 1 AND part_number_canonical LIKE :q_contains",
            "SELECT id AS id, (:pn_rank_offset + 21) AS rank FROM parts WHERE :contains = 1 AND part_number_extracted LIKE :q_contains",
            "SELECT id AS id, (:pn_rank_offset + 22) AS rank FROM parts WHERE :contains = 1 AND part_number_cell LIKE :q_contains",
            "SELECT part_id AS id, (:pn_rank_offset + 23) AS rank FROM aliases WHERE :contains = 1 AND alias_value LIKE :q_contains",
            # 术语匹配
            "SELECT id AS id, (:term_rank_offset + 0) AS rank FROM parts WHERE :term_enabled = 1 AND :term_dot_only = 1 AND nom_level >= :min_level",
            "SELECT id AS id, (:term_rank_offset + 0) AS rank FROM parts WHERE :term_enabled = 1 AND :term_dot_only = 0 AND nomenclature_clean LIKE :q_contains",
            "SELECT attached_to_part_id AS id, (:term_rank_offset + 1) AS rank FROM parts "
            "WHERE :term_enabled = 1 AND :term_dot_only = 0 AND :kw = 1 AND :dotprefix = 0 "
            "AND attached_to_part_id IS NOT NULL AND coalesce(nomenclature_clean, nomenclature, '') LIKE :q_contains",
        ]

        hits_sql = "\n            UNION ALL\n            ".join(hits)
        with_cte = f"""
        WITH hits(id, rank) AS (
            {hits_sql}
        ),
        best AS (
            SELECT id, min(rank) AS rank FROM hits GROUP BY id
        )
        """

        count_sql = f"""
        {with_cte}
        SELECT count(1) AS n
        FROM best
        JOIN parts p ON p.id = best.id
        WHERE (:include_notes = 1 OR p.row_kind = 'part')
        """

        order_by = (
            "best.rank, p.pn_needs_review DESC, coalesce(p.pn_best_similarity, 0.0) DESC, d.pdf_name, p.figure_code, p.page_num"
            if pn_like
            else "best.rank, d.pdf_name, p.figure_code, p.page_num"
        )

        sql = f"""
        {with_cte}
        SELECT
          p.id,
          d.pdf_name AS source_pdf,
          p.page_num,
          p.page_end,
          p.extractor,
          p.figure_code,
          pg.figure_label,
          pg.date_text,
          p.row_kind,
          p.fig_item_raw,
          p.fig_item_no,
          p.fig_item_no_source,
          p.not_illustrated,
          p.part_number_cell,
          p.part_number_extracted,
          p.part_number_canonical,
          p.pn_corrected,
          p.pn_method,
          p.pn_best_similarity,
          p.pn_needs_review,
          p.correction_note,
          p.nom_level,
          p.nomenclature_clean,
          p.parent_part_id,
          p.effectivity,
          p.units_per_assy,
          substr(replace(coalesce(p.nomenclature_clean, p.nomenclature, ''), char(10), ' '), 1, 220) AS nomenclature_preview,
          substr(replace(coalesce(p.nomenclature, ''), char(10), ' '), 1, 220) AS nomenclature_preview_raw
        FROM best
        JOIN parts p ON p.id = best.id
        JOIN documents d ON d.id = p.document_id
        LEFT JOIN pages pg ON pg.document_id = p.document_id AND pg.page_num = p.page_num
        WHERE (:include_notes = 1 OR p.row_kind = 'part')
        ORDER BY {order_by}
        LIMIT :limit OFFSET :offset
        """

        params = {
            "q": q,
            "q_prefix": q_prefix,
            "q_contains": q_contains,
            "prefix": prefix,
            "contains": contains,
            "term_enabled": term_enabled,
            "term_dot_only": term_dot_only,
            "min_level": min_level,
            "kw": kw,
            "dotprefix": dotprefix,
            "pn_rank_offset": pn_rank_offset,
            "term_rank_offset": term_rank_offset,
            "limit": limit,
            "offset": max(offset, 0),
            "include_notes": include_notes_int,
        }

        with self._db.connection() as conn:
            total_row = conn.execute(count_sql, params).fetchone()
            total = int(total_row["n"] if total_row else 0)
            rows = conn.execute(sql, params).fetchall()

        results = [self._row_to_search_result(r) for r in rows]
        return results, total

    def get_detail(self, part_id: int) -> PartDetail | None:
        """
        获取零件详情（含层级信息）

        Args:
            part_id: 零件ID

        Returns:
            零件详情或None
        """
        with self._db.connection() as conn:
            row = conn.execute(
                """
                SELECT
                  p.id,
                  d.pdf_name AS source_pdf,
                  p.document_id,
                  p.page_num,
                  p.page_end,
                  p.extractor,
                  p.meta_data_raw,
                  p.figure_code,
                  pg.figure_label,
                  pg.date_text,
                  p.row_kind,
                  p.fig_item_raw,
                  p.fig_item_no,
                  p.fig_item_no_source,
                  p.not_illustrated,
                  p.part_number_cell,
                  p.part_number_extracted,
                  p.part_number_canonical,
                  p.pn_corrected,
                  p.pn_method,
                  p.pn_best_similarity,
                  p.pn_needs_review,
                  p.correction_note,
                  p.nom_level,
                  p.nomenclature_clean,
                  p.parent_part_id,
                  p.attached_to_part_id,
                  p.nomenclature,
                  p.effectivity,
                  p.units_per_assy
                FROM parts p
                JOIN documents d ON d.id = p.document_id
                LEFT JOIN pages pg ON pg.document_id = p.document_id AND pg.page_num = p.page_num
                WHERE p.id = ?
                """,
                (part_id,),
            ).fetchone()

            if not row:
                return None

            part = Part.from_row(dict(row))

            # 获取层级信息
            hierarchy = self._get_hierarchy(conn, part_id)

            # 获取交叉引用
            xrefs_rows = conn.execute(
                "SELECT kind, target FROM xrefs WHERE part_id = ? ORDER BY kind, target",
                (part_id,),
            ).fetchall()
            xrefs = [XRef(kind=r["kind"], target=r["target"]) for r in xrefs_rows]

            return PartDetail(
                part=part,
                parents=[Part.from_row(p) for p in hierarchy["ancestors"]],
                siblings=[Part.from_row(s) for s in hierarchy["siblings"]],
                children=[Part.from_row(c) for c in hierarchy["children"]],
                xrefs=xrefs,
            )

    def get_document_path(self, pdf_name: str) -> Path | None:
        """获取PDF文件路径"""
        pdf_name = _safe_pdf_name(pdf_name)

        # 首先尝试 pdf_dir
        if self._pdf_dir:
            candidate = self._pdf_dir / pdf_name
            if candidate.exists():
                return candidate

        # 从数据库获取路径
        row = self._db.execute_one(
            "SELECT pdf_path FROM documents WHERE pdf_name = ?",
            (pdf_name,),
        )
        if not row:
            return None

        raw_path = str(row["pdf_path"] or "")
        p = Path(raw_path)
        if p.exists():
            return p

        # 尝试相对路径
        if self._pdf_dir:
            normalized = raw_path.replace("\\", "/").lstrip("/")
            if normalized and ":" not in normalized:
                joined = self._pdf_dir / normalized
                if joined.exists():
                    return joined

        return p

    def _get_hierarchy(self, conn: sqlite3.Connection, part_id: int) -> dict[str, Any]:
        """获取层级信息"""
        node = self._fetch_node(conn, part_id)
        if not node:
            return {"ancestors": [], "siblings": [], "children": []}

        # 获取祖先链
        ancestors = []
        seen = {part_id}
        parent_id = node.get("parent_part_id")
        depth = 0
        while parent_id and depth < 12 and parent_id not in seen:
            parent = self._fetch_node(conn, int(parent_id))
            if not parent:
                break
            ancestors.append(parent)
            seen.add(int(parent_id))
            parent_id = parent.get("parent_part_id")
            depth += 1
        ancestors.reverse()

        # 获取同级
        siblings = []
        if node.get("parent_part_id"):
            rows = conn.execute(
                """
                SELECT p.*, d.pdf_name
                FROM parts p
                JOIN documents d ON d.id = p.document_id
                WHERE p.parent_part_id = ? AND p.nom_level = ? AND p.id != ?
                ORDER BY p.id
                LIMIT 20
                """,
                (node["parent_part_id"], node.get("nom_level", 0), node["id"]),
            ).fetchall()
            siblings = [dict(r) for r in rows]

        # 获取子级
        rows = conn.execute(
            """
            SELECT p.*, d.pdf_name
            FROM parts p
            JOIN documents d ON d.id = p.document_id
            WHERE p.parent_part_id = ?
            ORDER BY p.id
            LIMIT 40
            """,
            (node["id"],),
        ).fetchall()
        children = [dict(r) for r in rows]

        return {
            "ancestors": ancestors,
            "siblings": siblings,
            "children": children,
        }

    def _fetch_node(self, conn: sqlite3.Connection, part_id: int) -> dict | None:
        """获取节点信息"""
        row = conn.execute(
            """
            SELECT p.*, d.pdf_name
            FROM parts p
            JOIN documents d ON d.id = p.document_id
            WHERE p.id = ?
            """,
            (part_id,),
        ).fetchone()
        return dict(row) if row else None

    def _row_to_search_result(self, r: sqlite3.Row) -> dict[str, Any]:
        """将数据库行转换为搜索结果"""
        return {
            "id": r["id"],
            "source_pdf": r["source_pdf"],
            "page_num": r["page_num"],
            "page_end": r["page_end"],
            "figure_code": r["figure_code"],
            "fig_item": _fig_item_display(
                r["fig_item_raw"],
                r["fig_item_no"],
                int(r["not_illustrated"] or 0)
            ),
            "not_illustrated": int(r["not_illustrated"] or 0),
            "part_number_cell": r["part_number_cell"],
            "part_number_canonical": r["part_number_canonical"],
            "pn_corrected": int(r["pn_corrected"] or 0),
            "nom_level": int(r["nom_level"] or 0),
            "nomenclature_preview": r["nomenclature_preview"],
            "effectivity": r["effectivity"],
            "units_per_assy": r["units_per_assy"],
        }
