"""
Web Server (Legacy)

DEPRECATED: This module is deprecated and will be removed in a future version.
Please use the new modular architecture instead:

    # Start server using new architecture
    python -m ipc_query

Or programmatically:

    from ipc_query.api.server import run_server
    run_server(config)

The new architecture provides:
- Better separation of concerns (API/Services/DB layers)
- Improved caching with TTL support
- Structured logging and metrics
- Comprehensive error handling

See ipc_query.api module for details.
"""

from __future__ import annotations

import warnings

# Emit deprecation warning when this module is imported
warnings.warn(
    "web_server.py is deprecated. Use 'python -m ipc_query' or ipc_query.api module instead.",
    DeprecationWarning,
    stacklevel=2
)

import argparse
import json
import mimetypes
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import fitz  # PyMuPDF


def _json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _warmup_search(db_path: Path, *, q: str = "113A4200-2") -> None:
    """
    Best-effort warm-up to reduce the "first query is slow" cold-start effect.

    This intentionally does not fail the server start.
    """

    t0 = time.time()
    try:
        with _open_db(db_path) as conn:
            # Touch a few pages + indexes via the same query path as the UI (PN match).
            _search(conn, q=q, offset=0, limit=1, include_notes=False, match="pn")
    except Exception as e:
        print(f"[WARN] warmup skipped: {e}")
        return
    elapsed_ms = int((time.time() - t0) * 1000)
    print(f"[OK] warmup: q={q!r} {elapsed_ms}ms")


def _safe_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except Exception:
        return default


@dataclass(frozen=True)
class AppConfig:
    db_path: Path
    static_dir: Path
    cache_dir: Path
    pdf_dir: Path | None
    render_semaphore: threading.BoundedSemaphore
    render_acquire_timeout_s: float


def _open_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA case_sensitive_like=ON;").fetchone()
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("PRAGMA query_only=ON;").fetchone()
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("PRAGMA temp_store=MEMORY;").fetchone()
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("PRAGMA busy_timeout=5000;").fetchone()
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("PRAGMA cache_size=-20000;").fetchone()
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("PRAGMA mmap_size=268435456;").fetchone()
    except sqlite3.OperationalError:
        pass
    return conn


def _fetch_documents(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, pdf_name, pdf_path, miner_dir, created_at FROM documents ORDER BY pdf_name"
    ).fetchall()
    return [dict(r) for r in rows]


def _safe_pdf_name(raw: str) -> str:
    # Defense-in-depth: avoid path traversal and keep caching predictable.
    # We only allow a single filename segment.
    return (raw or "").replace("\\", "/").split("/")[-1]


def _get_document_path(conn: sqlite3.Connection, pdf_name: str, *, pdf_dir: Path | None) -> Path | None:
    pdf_name = _safe_pdf_name(pdf_name)

    pdf_root = pdf_dir.resolve() if pdf_dir else None
    if pdf_dir:
        candidate = (pdf_dir / pdf_name).resolve()
        if (candidate == pdf_root or pdf_root in candidate.parents) and candidate.exists():
            return candidate

    row = conn.execute("SELECT pdf_path FROM documents WHERE pdf_name = ?", (pdf_name,)).fetchone()
    if not row:
        return None
    raw_path = str(row["pdf_path"] or "")
    p = Path(raw_path)
    if p.exists():
        return p

    if pdf_dir:
        normalized = raw_path.replace("\\", "/").lstrip("/")
        # Prefer DB-relative paths when possible (e.g. "IPC/7NG/xx.pdf") so multiple subdirs work.
        if normalized and ":" not in normalized:
            joined = (pdf_dir / normalized).resolve()
            if (joined == pdf_root or pdf_root in joined.parents) and joined.exists():
                return joined
            if normalized.upper().startswith("IPC/"):
                joined2 = (pdf_dir / normalized[4:]).resolve()
                if (joined2 == pdf_root or pdf_root in joined2.parents) and joined2.exists():
                    return joined2

        fallback = (pdf_dir / _safe_pdf_name(raw_path)).resolve()
        if (fallback == pdf_root or pdf_root in fallback.parents) and fallback.exists():
            return fallback

    return p


def _fig_item_display(fig_raw: str | None, fig_no: str | None, not_illustrated: int) -> str:
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


_PN_QUERY_RE = re.compile(r"^[A-Z0-9][A-Z0-9./-]*$")


def _looks_like_pn_query(q: str) -> bool:
    """
    Heuristic: treat the query as a PN when it resembles typical IPC part numbers.

    This lets us skip expensive term matching for PN-like queries under match=all,
    improving latency on large databases.
    """

    q = (q or "").strip().upper()
    if not q or q.startswith(".") or any(ch.isspace() for ch in q):
        return False
    if not any(ch.isdigit() for ch in q):
        return False
    return bool(_PN_QUERY_RE.fullmatch(q))


def _ensure_db_optimized(db_path: Path) -> None:
    """
    One-time DB optimization for interactive queries:
    - add missing indexes that the server relies on
    - run ANALYZE once so SQLite has stats for query planning

    Safe to call repeatedly; it is a no-op after the first run.
    """

    conn = sqlite3.connect(str(db_path), timeout=60)
    try:
        conn.execute("PRAGMA foreign_keys=ON;").fetchone()
        conn.execute("PRAGMA busy_timeout=60000;").fetchone()
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_parts_pn_cell ON parts(part_number_cell);
            CREATE INDEX IF NOT EXISTS idx_parts_doc_page ON parts(document_id, page_num);
            CREATE INDEX IF NOT EXISTS idx_pages_doc_page ON pages(document_id, page_num);
            CREATE INDEX IF NOT EXISTS idx_parts_nom_clean ON parts(nomenclature_clean);
            CREATE INDEX IF NOT EXISTS idx_parts_nom_level ON parts(nom_level);
            CREATE INDEX IF NOT EXISTS idx_xrefs_part ON xrefs(part_id);
            CREATE INDEX IF NOT EXISTS idx_alias_part ON aliases(part_id);
            """
        )

        need_analyze = (
            conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_stat1'").fetchone()
            is None
        )
        if not need_analyze:
            has_xrefs = conn.execute("SELECT 1 FROM xrefs LIMIT 1").fetchone() is not None
            has_aliases = conn.execute("SELECT 1 FROM aliases LIMIT 1").fetchone() is not None
            required_stats = [
                ("idx_parts_pn_cell", True),
                ("idx_parts_doc_page", True),
                ("idx_pages_doc_page", True),
                ("idx_parts_nom_clean", True),
                ("idx_parts_nom_level", True),
                ("idx_xrefs_part", has_xrefs),
                ("idx_alias_part", has_aliases),
            ]
            for idx_name, required in required_stats:
                if not required:
                    continue
                if conn.execute("SELECT 1 FROM sqlite_stat1 WHERE idx = ?", (idx_name,)).fetchone() is None:
                    need_analyze = True
                    break
        if need_analyze:
            conn.execute("ANALYZE;").fetchone()
    finally:
        conn.close()


def _search(
    conn: sqlite3.Connection,
    q: str,
    *,
    offset: int,
    limit: int,
    include_notes: bool,
    match: str,
) -> tuple[list[dict[str, Any]], int]:
    q = (q or "").strip()
    if not q:
        return ([], 0)

    q = q.upper()
    include_notes_int = 1 if include_notes else 0
    match = (match or "all").strip().lower()
    if match not in {"all", "pn", "term"}:
        match = "all"

    pn_like = _looks_like_pn_query(q)
    term_kw = len(q) >= 3 or (len(q) >= 2 and any(ch.isdigit() for ch in q))

    def _search_pn_rows(*, enable_contains: bool) -> tuple[list[sqlite3.Row], int]:
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
            hits.extend(
                [
                    "SELECT id AS id, 10 AS rank FROM parts WHERE part_number_canonical LIKE :q_prefix",
                    "SELECT id AS id, 11 AS rank FROM parts WHERE part_number_extracted LIKE :q_prefix",
                    "SELECT id AS id, 12 AS rank FROM parts WHERE part_number_cell LIKE :q_prefix",
                    "SELECT part_id AS id, 13 AS rank FROM aliases WHERE alias_value LIKE :q_prefix",
                ]
            )
        if contains:
            hits.extend(
                [
                    "SELECT id AS id, 20 AS rank FROM parts WHERE part_number_canonical LIKE :q_contains",
                    "SELECT id AS id, 21 AS rank FROM parts WHERE part_number_extracted LIKE :q_contains",
                    "SELECT id AS id, 22 AS rank FROM parts WHERE part_number_cell LIKE :q_contains",
                    "SELECT part_id AS id, 23 AS rank FROM aliases WHERE alias_value LIKE :q_contains",
                ]
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

        total_row = conn.execute(count_sql, params).fetchone()
        total = int(total_row["n"] if total_row else 0)
        rows = conn.execute(sql, params).fetchall()
        return rows, total

    def _search_term_rows() -> tuple[list[sqlite3.Row], int]:
        dotprefix = 1 if q.startswith(".") else 0
        kw = 1 if term_kw else 0
        if not dotprefix and not kw:
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
        if kw and not dotprefix:
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

        total_row = conn.execute(count_sql, params).fetchone()
        total = int(total_row["n"] if total_row else 0)
        rows = conn.execute(sql, params).fetchall()
        return rows, total

    def _search_all_rows() -> tuple[list[sqlite3.Row], int]:
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

        # Ranking strategy:
        # - PN-like queries: prioritize PN matches; still include term matches later.
        # - Term-like queries: prioritize term matches; still include PN matches later.
        pn_rank_offset = 0 if pn_like else 1000
        term_rank_offset = 1000 if pn_like else 0

        hits = [
            # PN hits (cheap + indexed)
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
            # Term hits (potentially expensive; gated)
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
            """
          best.rank,
          p.pn_needs_review DESC,
          coalesce(p.pn_best_similarity, 0.0) DESC,
          d.pdf_name,
          p.figure_code,
          p.page_num
            """
            if pn_like
            else """
          best.rank,
          d.pdf_name,
          p.figure_code,
          p.page_num
            """
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

        total_row = conn.execute(count_sql, params).fetchone()
        total = int(total_row["n"] if total_row else 0)
        rows = conn.execute(sql, params).fetchall()
        return rows, total

    rows: list[sqlite3.Row]
    total: int
    if match == "pn":
        rows, total = _search_pn_rows(enable_contains=False)
        if total == 0 and len(q) >= 3:
            rows, total = _search_pn_rows(enable_contains=True)
    elif match == "term":
        rows, total = _search_term_rows()
    else:
        rows, total = _search_all_rows()

    out: list[dict[str, Any]] = []
    for r in rows:
        item_display = _fig_item_display(r["fig_item_raw"], r["fig_item_no"], int(r["not_illustrated"] or 0))
        out.append(
            {
                "id": r["id"],
                "source_pdf": r["source_pdf"],
                "page_num": r["page_num"],
                "page_end": r["page_end"],
                "extractor": r["extractor"],
                "figure_code": r["figure_code"],
                "figure_label": r["figure_label"],
                "date_text": r["date_text"],
                "row_kind": r["row_kind"],
                "fig_item": item_display,
                "fig_item_no_source": r["fig_item_no_source"],
                "not_illustrated": int(r["not_illustrated"] or 0),
                "part_number_cell": r["part_number_cell"],
                "part_number_extracted": r["part_number_extracted"],
                "part_number_canonical": r["part_number_canonical"],
                "pn_corrected": int(r["pn_corrected"] or 0),
                "pn_method": r["pn_method"],
                "pn_best_similarity": r["pn_best_similarity"],
                "pn_needs_review": int(r["pn_needs_review"] or 0),
                "correction_note": r["correction_note"],
                "nom_level": int(r["nom_level"] or 0),
                "parent_part_id": r["parent_part_id"],
                "effectivity": r["effectivity"],
                "units_per_assy": r["units_per_assy"],
                "nomenclature_preview": r["nomenclature_preview"],
                "nomenclature_preview_raw": r["nomenclature_preview_raw"],
            }
        )
    return (out, total)


def _node_summary(row: sqlite3.Row) -> dict[str, Any]:
    item_display = _fig_item_display(row["fig_item_raw"], row["fig_item_no"], int(row["not_illustrated"] or 0))
    part_number = row["part_number_canonical"] or row["part_number_extracted"] or row["part_number_cell"] or ""
    nomenclature = row["nomenclature_clean"] or row["nomenclature"] or ""
    return {
        "id": row["id"],
        "row_kind": row["row_kind"],
        "source_pdf": row["source_pdf"],
        "page_num": row["page_num"],
        "figure_code": row["figure_code"],
        "fig_item": item_display,
        "part_number": part_number,
        "nom_level": int(row["nom_level"] or 0),
        "nomenclature": nomenclature,
        "parent_part_id": row["parent_part_id"],
    }


def _fetch_node(conn: sqlite3.Connection, part_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT
          p.id,
          d.pdf_name AS source_pdf,
          p.page_num,
          p.figure_code,
          p.row_kind,
          p.fig_item_raw,
          p.fig_item_no,
          p.not_illustrated,
          p.part_number_cell,
          p.part_number_extracted,
          p.part_number_canonical,
          p.nom_level,
          p.nomenclature_clean,
          p.nomenclature,
          p.parent_part_id
        FROM parts p
        JOIN documents d ON d.id = p.document_id
        WHERE p.id = ?
        """,
        (part_id,),
    ).fetchone()


def _get_hierarchy(conn: sqlite3.Connection, part_id: int) -> dict[str, Any]:
    node = _fetch_node(conn, part_id)
    if not node:
        return {"ancestors": [], "siblings": [], "children": [], "root": None}

    ancestors: list[dict[str, Any]] = []
    seen = {part_id}
    parent_id = node["parent_part_id"]
    depth = 0
    while parent_id and depth < 12 and parent_id not in seen:
        parent = _fetch_node(conn, int(parent_id))
        if not parent:
            break
        ancestors.append(_node_summary(parent))
        seen.add(int(parent_id))
        parent_id = parent["parent_part_id"]
        depth += 1
    ancestors.reverse()

    root: dict[str, Any] | None = None
    if ancestors:
        root = ancestors[0]
    else:
        root = _node_summary(node)

    siblings: list[dict[str, Any]] = []
    if node["parent_part_id"]:
        rows = conn.execute(
            """
            SELECT
              p.id,
              d.pdf_name AS source_pdf,
              p.page_num,
              p.figure_code,
              p.row_kind,
              p.fig_item_raw,
              p.fig_item_no,
              p.not_illustrated,
              p.part_number_cell,
              p.part_number_extracted,
              p.part_number_canonical,
              p.nom_level,
              p.nomenclature_clean,
              p.nomenclature,
              p.parent_part_id
            FROM parts p
            JOIN documents d ON d.id = p.document_id
            WHERE p.parent_part_id = ? AND p.nom_level = ? AND p.id != ?
            ORDER BY p.id
            LIMIT 20
            """,
            (node["parent_part_id"], node["nom_level"], node["id"]),
        ).fetchall()
        siblings = [_node_summary(r) for r in rows]

    rows = conn.execute(
        """
        SELECT
          p.id,
          d.pdf_name AS source_pdf,
          p.page_num,
          p.figure_code,
          p.row_kind,
          p.fig_item_raw,
          p.fig_item_no,
          p.not_illustrated,
          p.part_number_cell,
          p.part_number_extracted,
          p.part_number_canonical,
          p.nom_level,
          p.nomenclature_clean,
          p.nomenclature,
          p.parent_part_id
        FROM parts p
        JOIN documents d ON d.id = p.document_id
        WHERE p.parent_part_id = ?
        ORDER BY p.id
        LIMIT 40
        """,
        (node["id"],),
    ).fetchall()
    children = [_node_summary(r) for r in rows]

    return {
        "ancestors": ancestors,
        "siblings": siblings,
        "children": children,
        "root": root,
    }


def _get_part_detail(conn: sqlite3.Connection, part_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT
          p.id,
          d.pdf_name AS source_pdf,
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

    attached_rows = conn.execute(
        """
        SELECT id, nomenclature_clean, nomenclature
        FROM parts
        WHERE attached_to_part_id = ?
        ORDER BY id
        """,
        (part_id,),
    ).fetchall()
    attached_notes: list[dict[str, Any]] = []
    attached_lines: list[str] = []
    for r in attached_rows:
        txt = (r["nomenclature_clean"] or r["nomenclature"] or "").strip()
        if not txt:
            continue
        attached_notes.append({"id": r["id"], "text": txt})
        attached_lines.append(txt)

    xrefs = conn.execute(
        "SELECT kind, target FROM xrefs WHERE part_id = ? ORDER BY kind, target",
        (part_id,),
    ).fetchall()
    aliases = conn.execute(
        "SELECT alias_type, alias_value FROM aliases WHERE part_id = ? ORDER BY alias_type, alias_value",
        (part_id,),
    ).fetchall()

    item_display = _fig_item_display(row["fig_item_raw"], row["fig_item_no"], int(row["not_illustrated"] or 0))

    base_desc = (row["nomenclature_clean"] or row["nomenclature"] or "").strip()
    desc_lines = [ln for ln in [base_desc, *attached_lines] if ln]
    nomenclature_full = "\n".join(desc_lines)

    return {
        "part": {
            **dict(row),
            "fig_item": item_display,
            "attached_notes": attached_notes,
            "nomenclature_full": nomenclature_full,
        },
        "xrefs": [dict(r) for r in xrefs],
        "aliases": [dict(r) for r in aliases],
        "hierarchy": _get_hierarchy(conn, part_id),
    }


class Handler(BaseHTTPRequestHandler):
    config: AppConfig

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, obj: Any) -> None:
        self._send(status, _json_bytes(obj), "application/json; charset=utf-8")

    def _send_file(self, path: Path, content_type: str | None = None) -> None:
        if not path.exists() or not path.is_file():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        ct = content_type or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        size = int(path.stat().st_size)

        disp_name = path.name.replace('"', "")
        content_disposition = None
        if ct == "application/pdf":
            content_disposition = f'inline; filename="{disp_name}"'

        # Support byte-range requests for better PDF viewing performance and lower memory usage.
        range_header = (self.headers.get("Range") or "").strip()
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header) if range_header else None
        if m:
            start_raw, end_raw = m.group(1), m.group(2)
            try:
                if start_raw == "" and end_raw == "":
                    raise ValueError("empty range")
                if start_raw == "":
                    # suffix bytes: bytes=-N
                    length = int(end_raw)
                    if length <= 0:
                        raise ValueError("bad suffix length")
                    start = max(size - length, 0)
                    end = size - 1
                else:
                    start = int(start_raw)
                    end = int(end_raw) if end_raw != "" else size - 1
                    if start < 0 or start >= size:
                        raise ValueError("start out of range")
                    end = min(max(end, start), size - 1)
            except Exception:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return

            length = end - start + 1
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            if content_disposition:
                self.send_header("Content-Disposition", content_disposition)
            if ct.startswith("image/"):
                self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            else:
                self.send_header("Cache-Control", "no-store")
            self.end_headers()

            try:
                with path.open("rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(64 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except BrokenPipeError:
                return
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(size))
        self.send_header("Accept-Ranges", "bytes")
        if content_disposition:
            self.send_header("Content-Disposition", content_disposition)
        if ct.startswith("image/"):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            with path.open("rb") as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except BrokenPipeError:
            return

    def _serve_static(self, request_path: str) -> None:
        if request_path in ("", "/"):
            self._send_file(self.config.static_dir / "index.html", "text/html; charset=utf-8")
            return
        rel = request_path.lstrip("/")
        target = (self.config.static_dir / rel).resolve()
        static_root = self.config.static_dir.resolve()
        if static_root not in target.parents and target != static_root:
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
            return
        self._send_file(target)

    def _handle_api_search(self, qs: dict[str, list[str]]) -> None:
        q = (qs.get("q") or [""])[0]
        include_notes = ((qs.get("include_notes") or ["0"])[0] == "1")
        match = (qs.get("match") or ["all"])[0]

        page_size = _safe_int((qs.get("page_size") or [None])[0], 0)
        limit = _safe_int((qs.get("limit") or [None])[0], 60)
        if page_size <= 0:
            page_size = limit
        page_size = min(max(page_size, 1), 200)

        page = min(max(_safe_int((qs.get("page") or [None])[0], 1), 1), 999999)
        offset = (page - 1) * page_size
        t0 = time.time()
        with _open_db(self.config.db_path) as conn:
            results, total = _search(
                conn,
                q=q,
                offset=offset,
                limit=page_size,
                include_notes=include_notes,
                match=match,
            )
        elapsed_ms = int((time.time() - t0) * 1000)
        self._send_json(
            HTTPStatus.OK,
            {
                "query": q,
                "count": len(results),
                "total": total,
                "page": page,
                "page_size": page_size,
                "match": match,
                "elapsed_ms": elapsed_ms,
                "results": results,
            },
        )

    def _handle_api_part(self, part_id: int) -> None:
        with _open_db(self.config.db_path) as conn:
            detail = _get_part_detail(conn, part_id)
        if not detail:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        self._send_json(HTTPStatus.OK, detail)

    def _handle_api_docs(self) -> None:
        with _open_db(self.config.db_path) as conn:
            docs = _fetch_documents(conn)
        self._send_json(HTTPStatus.OK, docs)

    def _handle_api_health(self) -> None:
        database: dict[str, Any]
        try:
            with _open_db(self.config.db_path) as conn:
                conn.execute("SELECT 1")
                tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                table_names = [str(t["name"]) for t in tables]
                parts_count = int(conn.execute("SELECT COUNT(*) AS cnt FROM parts").fetchone()["cnt"])
                docs_count = int(conn.execute("SELECT COUNT(*) AS cnt FROM documents").fetchone()["cnt"])
                database = {
                    "status": "healthy",
                    "tables": table_names,
                    "parts_count": parts_count,
                    "documents_count": docs_count,
                }
        except Exception as e:
            database = {
                "status": "unhealthy",
                "error": str(e),
            }

        self._send_json(
            HTTPStatus.OK,
            {
                "status": "healthy",
                "version": "2.0.0",
                "database": database,
            },
        )

    def _handle_pdf(self, pdf_name: str) -> None:
        with _open_db(self.config.db_path) as conn:
            path = _get_document_path(conn, pdf_name, pdf_dir=self.config.pdf_dir)
        if not path:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "pdf_not_found"})
            return
        if not path.exists():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "pdf_missing_on_disk"})
            return
        self._send_file(path, "application/pdf")

    def _handle_render(self, pdf_name: str, page_num: int, scale: float) -> None:
        if page_num < 1:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_page"})
            return
        scale = max(1.0, min(scale, 4.0))
        pdf_name = _safe_pdf_name(pdf_name)
        cache_name = f"{pdf_name}__p{page_num}__s{scale:.2f}.png".replace(os.sep, "_")
        cache_path = self.config.cache_dir / cache_name
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)

        if cache_path.exists():
            self._send_file(cache_path, "image/png")
            return

        acquired = self.config.render_semaphore.acquire(timeout=max(0.0, self.config.render_acquire_timeout_s))
        if not acquired:
            self._send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "render_busy"})
            return

        try:
            try:
                with _open_db(self.config.db_path) as conn:
                    pdf_path = _get_document_path(conn, pdf_name, pdf_dir=self.config.pdf_dir)
                if not pdf_path:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "pdf_not_found"})
                    return
                if not pdf_path.exists():
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "pdf_missing_on_disk"})
                    return

                doc = fitz.open(str(pdf_path))
                try:
                    if page_num > doc.page_count:
                        self._send_json(HTTPStatus.NOT_FOUND, {"error": "page_out_of_range"})
                        return
                    page = doc[page_num - 1]
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
                    pix.save(str(cache_path))
                finally:
                    doc.close()
            except Exception as e:
                if cache_path.exists():
                    try:
                        cache_path.unlink()
                    except Exception:
                        pass
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "render_failed", "detail": str(e)})
                return
        finally:
            try:
                self.config.render_semaphore.release()
            except Exception:
                pass

        self._send_file(cache_path, "image/png")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        qs = parse_qs(parsed.query)

        if path == "/api/search":
            self._handle_api_search(qs)
            return
        if path == "/api/health":
            self._handle_api_health()
            return
        if path == "/api/docs":
            self._handle_api_docs()
            return
        if path.startswith("/api/part/"):
            try:
                part_id = int(path.split("/", 3)[3])
            except Exception:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_id"})
                return
            self._handle_api_part(part_id)
            return
        if path.startswith("/pdf/"):
            pdf_name = path.split("/", 2)[2]
            self._handle_pdf(pdf_name)
            return
        if path.startswith("/render/"):
            parts = path.split("/", 3)
            if len(parts) != 4:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "bad_render_path"})
                return
            pdf_name = parts[2]
            page_part = parts[3]
            if not page_part.endswith(".png"):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "bad_render_suffix"})
                return
            try:
                page_num = int(page_part[:-4])
            except Exception:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_page"})
                return
            scale = float((qs.get("scale") or ["2"])[0])
            self._handle_render(pdf_name, page_num, scale)
            return

        self._serve_static(path)

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: N802
        # Keep logs concise for demo
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=str, default="tmp/ipc_coords_demo.sqlite", help="SQLite 路径（新库）")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8791)
    parser.add_argument("--static-dir", type=str, default="demo_coords/web", help="静态页面目录")
    parser.add_argument("--pdf-dir", type=str, default="", help="PDF 根目录（用于定位 PDF；支持 DB 中相对 pdf_path）")
    parser.add_argument("--cache-dir", type=str, default="tmp/page_cache_coords", help="渲染缓存目录")
    parser.add_argument("--render-concurrency", type=int, default=1, help="/render 最大并发（低配建议 1）")
    parser.add_argument("--render-timeout", type=float, default=2.0, help="等待 /render 资源的秒数（超时返回 429）")
    parser.add_argument("--no-warmup", action="store_true", help="禁用启动时预热（默认开启）")
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir) if str(args.pdf_dir or "").strip() else None
    if pdf_dir and not pdf_dir.exists():
        print(f"[ERR] pdf dir not found: {pdf_dir}")
        return 2

    render_concurrency = max(1, int(args.render_concurrency))
    render_timeout_s = max(0.0, float(args.render_timeout))

    config = AppConfig(
        db_path=Path(args.db),
        static_dir=Path(args.static_dir),
        cache_dir=Path(args.cache_dir),
        pdf_dir=pdf_dir,
        render_semaphore=threading.BoundedSemaphore(render_concurrency),
        render_acquire_timeout_s=render_timeout_s,
    )
    if not config.db_path.exists():
        print(f"[ERR] DB not found: {config.db_path}")
        return 2
    if not config.static_dir.exists():
        print(f"[ERR] static dir not found: {config.static_dir}")
        return 2

    try:
        _ensure_db_optimized(config.db_path)
    except Exception as e:
        print(f"[WARN] DB optimize skipped: {e}")

    if not bool(args.no_warmup):
        _warmup_search(config.db_path)

    Handler.config = config  # type: ignore[attr-defined]

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[OK] IPC demo server: http://{args.host}:{args.port}")
    print("     - Search API: /api/search?q=113A4200-1")
    print("     - Health API: /api/health")
    print("     - Docs API:   /api/docs")
    print("     - PDF:        /pdf/24-21___083.pdf#page=3")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[OK] server stopped")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
