"""
Database Builder Script

Build SQLite database from IPC PDF files.
This script extracts part information from PDF files and stores it in a SQLite database.

Usage:
    python build_db.py --pdf-dir IPC/7NG --db ipc.db
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import difflib
import json
import re
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

import fitz  # PyMuPDF

# 导入共享常量
from ipc_query.constants import (
    MONTHS,
    DATE_RE,
    RF_TEXT_RE,
    FIGURE_CODE_RE,
    PAGE_TOKEN_RE,
    FIG_LINE_RE,
    FIGURE_LINE_RE,
    ITEM_PN_SPLIT_RE,
    NOM_LEADING_DOTS_RE,
    PART_RE,
    CJK_RE,
)


def _force_utf8_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    try:
        if callable(reconfigure):
            reconfigure(encoding="utf-8")
    except Exception:
        pass


_force_utf8_stdout()


# 保留本地使用的CJK检测函数
def _has_cjk(s: str) -> bool:
    """检查字符串是否包含CJK字符"""
    return bool(CJK_RE.search(s or ""))


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _norm_loose(s: str) -> str:
    s = (s or "").upper()
    s = s.replace("–", "-").replace("—", "-")
    s = _norm_ws(s)
    s = re.sub(r"(?<=\d)O(?=\d)", "0", s)
    s = re.sub(r"(?<=[A-Z])0(?=[A-Z])", "O", s)
    return s


def _norm_loose_cell(s: str) -> str:
    """
    A more conservative normalization for values coming from the PART NUMBER column itself.

    We still fix the common O/0 confusion in numeric contexts (e.g. 10O1 -> 1001), but we do NOT
    map 0->O between letters here, because some IPC part numbers legitimately contain '0' as the
    only digit (e.g. C0ML, DEM0KIT).
    """

    s = (s or "").upper()
    s = s.replace("–", "-").replace("—", "-")
    s = _norm_ws(s)
    s = re.sub(r"(?<=\d)O(?=\d)", "0", s)
    return s


def _looks_like_part_number(s: str) -> bool:
    t = _norm_loose(s)
    if not t:
        return False
    if re.fullmatch(r"\d+", t):
        return False
    if FIGURE_CODE_RE.fullmatch(t):
        return False
    if not any(ch.isdigit() for ch in t):
        return False
    if not PART_RE.fullmatch(t):
        return False
    return True


def _looks_like_part_number_cell(s: str) -> bool:
    """
    PART NUMBER column values are much more reliable than free-text tokens from the whole page.

    Some IPC tables contain valid part numbers that are digits-only (e.g. "33700002", "103").
    We allow those here to avoid dropping real rows, while keeping the free-text token heuristic
    strict to prevent candidate explosions during canonicalization.
    """

    t = _norm_loose_cell(s)
    if not t:
        return False
    if FIGURE_CODE_RE.fullmatch(t):
        return False
    if not PART_RE.fullmatch(t):
        return False
    if re.fullmatch(r"\d+", t):
        return len(t) >= 3
    if not any(ch.isdigit() for ch in t):
        return False
    return True


def _extract_candidate_tokens_from_pdf_page(page: fitz.Page) -> list[str]:
    text = page.get_text("text") or ""
    tokens = set()
    upper = text.upper()
    for tok in re.findall(r"[A-Z0-9][A-Z0-9./-]{3,}", upper):
        if _looks_like_part_number(tok):
            tokens.add(tok)
    # Short codes like "M4", "V37", "T434" sometimes appear as valid PART NUMBERs.
    for tok in re.findall(r"\b[A-Z]{1,3}\d{1,4}[A-Z]?\b", upper):
        if _looks_like_part_number(tok):
            tokens.add(tok)
    return sorted(tokens)


@dataclasses.dataclass(frozen=True)
class Canonicalization:
    canonical: str
    corrected: bool
    method: str
    best_similarity: float | None = None
    needs_review: bool = False
    note: str | None = None


def _candidate_index_from_page(page: fitz.Page) -> tuple[list[str], set[str], dict[str, str]]:
    candidates = _extract_candidate_tokens_from_pdf_page(page)
    candidates_set = set(candidates)
    candidates_by_loose: dict[str, str] = {}
    for c in candidates:
        candidates_by_loose.setdefault(_norm_loose(c), c)
    return candidates, candidates_set, candidates_by_loose


def _canonicalize_part_number_indexed(
    candidates: list[str],
    candidates_set: set[str],
    candidates_by_loose: dict[str, str],
    raw: str,
) -> Canonicalization:
    raw = (raw or "").strip()
    if not raw:
        return Canonicalization(canonical="", corrected=False, method="empty", needs_review=False)
    raw_upper = raw.upper()
    if raw_upper in candidates_set:
        return Canonicalization(canonical=raw_upper, corrected=False, method="exact", needs_review=False)

    raw_loose = _norm_loose(raw_upper)
    mapped = candidates_by_loose.get(raw_loose)
    if mapped:
        return Canonicalization(canonical=mapped, corrected=False, method="loose", needs_review=False)

    best = None
    best_ratio = 0.0
    for c in candidates:
        ratio = difflib.SequenceMatcher(None, _norm_loose(c), raw_loose).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best = c

    if best and best_ratio >= 0.92:
        return Canonicalization(
            canonical=best,
            corrected=True,
            method="fuzzy",
            best_similarity=best_ratio,
            needs_review=False,
            note=f"{raw_upper} -> {best} (sim {best_ratio:.3f})",
        )
    if best and best_ratio >= 0.90:
        return Canonicalization(
            canonical=best,
            corrected=True,
            method="fuzzy_low",
            best_similarity=best_ratio,
            needs_review=True,
            note=f"{raw_upper} -> {best} (sim {best_ratio:.3f}, low confidence)",
        )
    return Canonicalization(canonical=raw_upper, corrected=False, method="unverified", needs_review=True)


def _extract_page_token(page_text: str) -> str | None:
    matches = PAGE_TOKEN_RE.findall(page_text or "")
    if not matches:
        return None
    return str(matches[-1]).upper()


def _parse_page_meta(page_text: str, base_prefix: str) -> dict[str, str | None]:
    lines = [ln.strip() for ln in (page_text or "").splitlines() if ln.strip()]
    base_codes = [c for c in FIGURE_CODE_RE.findall(page_text or "") if c.startswith(base_prefix)]
    figure_code = None
    if base_codes:
        figure_code = sorted(base_codes, key=len)[-1]

    fig_label = None
    date_text = None
    for ln in reversed(lines[-30:]):
        if not date_text:
            date_match = DATE_RE.search(ln)
            if date_match:
                date_text = date_match.group(0).upper()
        if not fig_label:
            m = FIG_LINE_RE.match(ln)
            if m:
                fig_label = "FIG. " + m.group(1).strip()
                continue
            m = FIGURE_LINE_RE.match(ln)
            if m:
                fig_label = "FIGURE " + m.group(1).strip()
                continue

    m_rf = RF_TEXT_RE.search(page_text or "")
    rf_text = m_rf.group(0).upper() if m_rf else None

    return {
        "figure_code": figure_code,
        "figure_label": fig_label,
        "date_text": date_text,
        "page_token": _extract_page_token(page_text),
        "rf_text": rf_text,
    }


def _canon_figure_suffix(raw: str) -> str:
    """
    Normalize figure number suffix as seen in footer, e.g.:
      - '9' -> '09'
      - '1B' -> '01B'
      - '01B' -> '01B'
      - '02A' -> '02A'
    """
    s = (raw or "").strip().upper()
    s = re.sub(r"\s+", "", s)
    if not s:
        return ""
    m = re.fullmatch(r"(\d{1,2})([A-Z]?)", s)
    if not m:
        return s
    digits = m.group(1) or ""
    suffix = m.group(2) or ""
    if len(digits) == 1:
        digits = "0" + digits
    return digits + suffix


def _parse_meta_clip_text(meta_text: str) -> dict[str, str | None]:
    """
    Parse the footer meta clip (COORD_META_RECT) which is more reliable than scanning the whole page,
    because the page body may contain many cross-reference codes (FOR DETAILS SEE / FOR NHA SEE).
    """
    lines = [ln.strip() for ln in (meta_text or "").splitlines() if ln.strip()]
    if not lines:
        return {
            "figure_code": None,
            "figure_label": None,
            "date_text": None,
            "page_token": None,
            "rf_text": None,
        }

    prefix = lines[0].upper()
    fig_label = None
    fig_code = None
    date_text = None
    page_token = None

    for ln in lines[1:12]:
        if not page_token:
            page_match = PAGE_TOKEN_RE.search(ln)
            if page_match:
                page_token = page_match.group(0).upper()
        if not date_text:
            date_match = DATE_RE.search(ln)
            if date_match:
                date_text = date_match.group(0).upper()
        if not fig_label:
            m = FIG_LINE_RE.match(ln)
            if m:
                fig_label = "FIG. " + m.group(1).strip()
                fig_code = prefix + "-" + _canon_figure_suffix(m.group(1))
                continue
            m = FIGURE_LINE_RE.match(ln)
            if m:
                fig_label = "FIGURE " + m.group(1).strip()
                fig_code = prefix + "-" + _canon_figure_suffix(m.group(1))
                continue

    m_rf = RF_TEXT_RE.search(meta_text or "")
    rf_text = m_rf.group(0).upper() if m_rf else None

    return {
        "figure_code": fig_code,
        "figure_label": fig_label,
        "date_text": date_text,
        "page_token": page_token,
        "rf_text": rf_text,
    }


def _nomenclature_level_and_clean(nomenclature: str) -> tuple[int, str]:
    text = (nomenclature or "").rstrip()
    if not text:
        return 0, ""
    lines = [ln.rstrip() for ln in text.splitlines()]
    first = next((ln for ln in lines if ln.strip()), "")
    m = NOM_LEADING_DOTS_RE.match(first)
    if not m:
        return 0, text.strip()
    dots = m.group(1) or ""
    rest = (m.group(2) or "").lstrip()
    # Keep other lines unchanged, only clean the first visible line.
    cleaned_lines = []
    cleaned_first_done = False
    for ln in lines:
        if not cleaned_first_done and ln.strip():
            cleaned_lines.append(rest)
            cleaned_first_done = True
        else:
            cleaned_lines.append(ln)
    return len(dots), "\n".join([ln for ln in cleaned_lines if ln is not None]).strip()


_NOM_WATERMARK_LEADING = {"OF", "DATE", "OUT"}


def _clean_nomenclature_watermarks(nomenclature: str) -> str:
    """
    Remove known watermark/noise lines without touching normal English content.

    Rules (per user decision):
    - drop any line containing CJK characters (e.g. "资料失效")
    - after that, drop leading lines that equal one of: OF / DATE / OUT
    """

    lines = [ln.rstrip() for ln in (nomenclature or "").splitlines()]
    lines = [ln for ln in lines if ln.strip() and not _has_cjk(ln)]
    while lines and lines[0].strip().upper() in _NOM_WATERMARK_LEADING:
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
    return "\n".join(lines).strip()


def _extract_xrefs(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if not text:
        return out
    for m in re.finditer(r"FOR\s+NHA\s+SEE:\s*([0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}[A-Z]?)", text, re.I):
        out.append(("NHA", m.group(1).upper()))
    for m in re.finditer(r"FOR\s+DETAILS\s+SEE:\s*([0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}[A-Z]?)", text, re.I):
        out.append(("DETAILS", m.group(1).upper()))
    return out


# --- PDF "text-layer coordinates" extraction (senior's approach) ---
PT_PER_CM = 72.0 / 2.54


def _pt(cm: float) -> float:
    return float(cm) * PT_PER_CM


COORD_MARK_RECT = fitz.Rect(_pt(17.5), _pt(25.8), _pt(18.5), _pt(26.2))
COORD_TABLE_RECT = fitz.Rect(_pt(2.3), _pt(2.5), _pt(19.5), _pt(25.4))
COORD_META_RECT = fitz.Rect(_pt(16.3), _pt(25.4), _pt(19.5), _pt(27.4))
COORD_Y_SCAN_START = _pt(3.8)
COORD_Y_TABLE_BOTTOM = _pt(25.4)
COORD_COLS_X = {
    "fig_item": (_pt(2.3), _pt(3.8)),
    "part_number": (_pt(3.8), _pt(7.9)),
    "nomenclature": (_pt(7.9), _pt(16.3)),
    "effect": (_pt(16.3), _pt(18.4)),
    "units": (_pt(18.4), _pt(19.5)),
}


def _clip_text(page: fitz.Page, rect: fitz.Rect) -> str:
    try:
        return page.get_text("text", clip=rect) or ""
    except Exception:
        return ""


def _coords_is_table_page(page: fitz.Page) -> bool:
    mark = _clip_text(page, COORD_MARK_RECT).upper()
    if "FIG" in mark:
        return True
    # Fallback: check for table header keywords near the top of table region
    header_rect = fitz.Rect(COORD_TABLE_RECT.x0, COORD_TABLE_RECT.y0, COORD_TABLE_RECT.x1, _pt(5.2))
    header = _clip_text(page, header_rect).upper()
    return ("PART NUMBER" in header) or ("NOMENCLATURE" in header) or ("FIG" in header and "ITEM" in header)


def _words_by_y(words: list[tuple[Any, ...]], y_tol: float = 2.0) -> list[tuple[float, list[tuple[Any, ...]]]]:
    items = sorted(words, key=lambda w: (float(w[1]), float(w[0])))
    groups: list[tuple[float, list[tuple[Any, ...]]]] = []
    for w in items:
        y = float(w[1])
        if not groups or abs(y - groups[-1][0]) > y_tol:
            groups.append((y, [w]))
        else:
            groups[-1][1].append(w)
    return groups


def _join_words_line(words: list[tuple[Any, ...]], sep: str = " ") -> str:
    parts = [str(w[4]).strip() for w in sorted(words, key=lambda w: float(w[0])) if str(w[4]).strip()]
    return re.sub(r"\s+", " ", sep.join(parts)).strip()


def _coords_col_text(
    table_words: list[tuple[Any, ...]],
    col: str,
    y0: float,
    y1: float,
    *,
    y_tol: float = 2.0,
) -> str:
    if col not in COORD_COLS_X:
        return ""
    x0, x1 = COORD_COLS_X[col]
    picked: list[tuple[Any, ...]] = []
    for w in table_words:
        wx0, wy0, wx1, wy1, *_ = w
        cx = (float(wx0) + float(wx1)) / 2.0
        cy = (float(wy0) + float(wy1)) / 2.0
        if cx < x0 or cx > x1:
            continue
        if cy < y0 or cy >= y1:
            continue
        picked.append(w)
    if not picked:
        return ""
    lines = []
    for _, grp in _words_by_y(picked, y_tol=y_tol):
        s = _join_words_line(grp, sep=" ")
        if s:
            lines.append(s)
    return "\n".join(lines).strip()


def _coords_part_number_anchors(table_words: list[tuple[Any, ...]]) -> list[tuple[float, str]]:
    x0, x1 = COORD_COLS_X["part_number"]
    picked: list[tuple[Any, ...]] = []
    for w in table_words:
        wx0, wy0, wx1, wy1, *_ = w
        cx = (float(wx0) + float(wx1)) / 2.0
        cy = (float(wy0) + float(wy1)) / 2.0
        if cx < x0 or cx > x1:
            continue
        if cy < COORD_Y_SCAN_START or cy > COORD_Y_TABLE_BOTTOM:
            continue
        picked.append(w)

    anchors: list[tuple[float, str]] = []
    # Deduplicate *nearby* duplicates (same visual row), but allow consecutive rows to share the same
    # PART NUMBER (standard hardware often repeats with different FIG ITEM numbers).
    dedup_y_tol = 3.0
    for y, grp in _words_by_y(picked, y_tol=2.0):
        pn = _join_words_line(grp, sep="").replace(" ", "").strip()
        if not _looks_like_part_number_cell(pn):
            continue
        if anchors and pn == anchors[-1][1] and abs(float(y) - float(anchors[-1][0])) <= dedup_y_tol:
            continue
        anchors.append((y, pn))
    return sorted(anchors, key=lambda x: x[0])


def _append_multiline(base: str, addition: str) -> str:
    addition = (addition or "").strip()
    if not addition:
        return base or ""
    base = (base or "").rstrip()
    return addition if not base else (base + "\n" + addition)


@dataclasses.dataclass
class CoordsRecord:
    part_number_cell: str
    start_page: int
    end_page: int
    fig_item_text: str
    nomenclature_text: str
    effect_from_to_text: str
    units_per_assy_text: str
    meta_data_raw: str


def _iter_coords_records(doc: fitz.Document) -> Iterable[CoordsRecord]:
    current: CoordsRecord | None = None

    for page_idx in range(int(doc.page_count)):
        page_num = page_idx + 1
        page = doc[page_idx]
        if not _coords_is_table_page(page):
            if current:
                yield current
                current = None
            continue

        meta_data_raw = _clip_text(page, COORD_META_RECT).strip()
        table_words = page.get_text("words", clip=COORD_TABLE_RECT) or []
        anchors = _coords_part_number_anchors(table_words)

        if not anchors:
            if current:
                current.nomenclature_text = _append_multiline(
                    current.nomenclature_text,
                    _coords_col_text(table_words, "nomenclature", COORD_Y_SCAN_START, COORD_Y_TABLE_BOTTOM),
                )
                current.effect_from_to_text = _append_multiline(
                    current.effect_from_to_text,
                    _coords_col_text(table_words, "effect", COORD_Y_SCAN_START, COORD_Y_TABLE_BOTTOM),
                )
                current.units_per_assy_text = _append_multiline(
                    current.units_per_assy_text,
                    _coords_col_text(table_words, "units", COORD_Y_SCAN_START, COORD_Y_TABLE_BOTTOM),
                )
                current.end_page = page_num
            continue

        # Close previous record at first new part-number anchor.
        if current:
            y_first = float(anchors[0][0])
            current.nomenclature_text = _append_multiline(
                current.nomenclature_text,
                _coords_col_text(table_words, "nomenclature", COORD_Y_SCAN_START, y_first),
            )
            current.effect_from_to_text = _append_multiline(
                current.effect_from_to_text,
                _coords_col_text(table_words, "effect", COORD_Y_SCAN_START, y_first),
            )
            current.units_per_assy_text = _append_multiline(
                current.units_per_assy_text,
                _coords_col_text(table_words, "units", COORD_Y_SCAN_START, y_first),
            )
            current.end_page = page_num
            yield current
            current = None

        for i, (y0, pn) in enumerate(anchors):
            y_start = float(y0)
            y_end = float(anchors[i + 1][0]) if (i + 1) < len(anchors) else float(COORD_Y_TABLE_BOTTOM)

            fig_item_text = _coords_col_text(table_words, "fig_item", y_start, y_end)
            fig_item_text = (fig_item_text.splitlines()[0].strip() if fig_item_text.strip() else "")

            rec = CoordsRecord(
                part_number_cell=pn,
                start_page=page_num,
                end_page=page_num,
                fig_item_text=fig_item_text,
                nomenclature_text=_coords_col_text(table_words, "nomenclature", y_start, y_end),
                effect_from_to_text=_coords_col_text(table_words, "effect", y_start, y_end),
                units_per_assy_text=_coords_col_text(table_words, "units", y_start, y_end),
                meta_data_raw=meta_data_raw,
            )

            if i + 1 < len(anchors):
                yield rec
            else:
                current = rec

    if current:
        yield current


def _init_db(conn: sqlite3.Connection) -> None:
    # Schema is kept compatible with demo/web_server.py so UI can be reused.
    #
    # WAL is usually faster, but some sandboxed / restricted filesystems disallow the required
    # file operations (e.g. atomic rename), leading to "disk I/O error". Fall back to TRUNCATE
    # so we can still build databases in such environments.
    try:
        conn.execute("PRAGMA journal_mode=WAL;").fetchone()
    except sqlite3.OperationalError:
        conn.execute("PRAGMA journal_mode=TRUNCATE;").fetchone()
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(
        """
        DROP TABLE IF EXISTS aliases;
        DROP TABLE IF EXISTS xrefs;
        DROP TABLE IF EXISTS parts;
        DROP TABLE IF EXISTS pages;
        DROP TABLE IF EXISTS documents;

        CREATE TABLE documents (
          id INTEGER PRIMARY KEY,
          pdf_name TEXT NOT NULL UNIQUE,
          pdf_path TEXT NOT NULL,
          miner_dir TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE pages (
          id INTEGER PRIMARY KEY,
          document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          page_num INTEGER NOT NULL,
          figure_code TEXT,
          figure_label TEXT,
          date_text TEXT,
          page_token TEXT,
          rf_text TEXT
        );

        CREATE TABLE parts (
          id INTEGER PRIMARY KEY,
          document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          page_num INTEGER NOT NULL,
          page_end INTEGER NOT NULL,
          extractor TEXT NOT NULL,
          meta_data_raw TEXT,
          figure_code TEXT,
          fig_item_raw TEXT,
          fig_item_no TEXT,
          fig_item_no_source TEXT,
          not_illustrated INTEGER NOT NULL DEFAULT 0,
          part_number_cell TEXT,
          part_number_extracted TEXT,
          part_number_canonical TEXT,
          pn_corrected INTEGER NOT NULL DEFAULT 0,
          pn_method TEXT,
          pn_best_similarity REAL,
          pn_needs_review INTEGER NOT NULL DEFAULT 0,
          correction_note TEXT,
          row_kind TEXT NOT NULL,
          nom_level INTEGER NOT NULL DEFAULT 0,
          nomenclature_clean TEXT,
          parent_part_id INTEGER,
          attached_to_part_id INTEGER,
          nomenclature TEXT,
          effectivity TEXT,
          units_per_assy TEXT,
          miner_table_img_path TEXT
        );

        CREATE TABLE xrefs (
          id INTEGER PRIMARY KEY,
          part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
          kind TEXT NOT NULL,
          target TEXT NOT NULL
        );

        CREATE TABLE aliases (
          id INTEGER PRIMARY KEY,
          part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
          alias_type TEXT NOT NULL,
          alias_value TEXT NOT NULL
        );

        CREATE INDEX idx_parts_pn ON parts(part_number_canonical);
        CREATE INDEX idx_parts_pn_extracted ON parts(part_number_extracted);
        CREATE INDEX idx_parts_pn_cell ON parts(part_number_cell);
        CREATE INDEX idx_parts_figure ON parts(figure_code);
        CREATE INDEX idx_parts_doc_page ON parts(document_id, page_num);
        CREATE INDEX idx_parts_parent ON parts(parent_part_id);
        CREATE INDEX idx_parts_attached ON parts(attached_to_part_id);
        CREATE INDEX idx_parts_nom_clean ON parts(nomenclature_clean);
        CREATE INDEX idx_parts_nom_level ON parts(nom_level);
        CREATE INDEX idx_pages_doc_page ON pages(document_id, page_num);
        CREATE INDEX idx_xrefs_part ON xrefs(part_id);
        CREATE INDEX idx_alias_value ON aliases(alias_value);
        CREATE INDEX idx_alias_part ON aliases(part_id);
        CREATE UNIQUE INDEX idx_parts_row_unique ON parts(
          document_id,
          page_num,
          COALESCE(figure_code, ''),
          COALESCE(fig_item_raw, ''),
          COALESCE(fig_item_no, ''),
          not_illustrated,
          COALESCE(part_number_cell, ''),
          COALESCE(nomenclature_clean, ''),
          COALESCE(effectivity, ''),
          COALESCE(units_per_assy, ''),
          nom_level,
          COALESCE(parent_part_id, 0)
        );
        """
    )


def ensure_schema(conn: sqlite3.Connection) -> None:
    """
    Ensure the SQLite schema exists without dropping existing data.
    """
    try:
        conn.execute("PRAGMA journal_mode=WAL;").fetchone()
    except sqlite3.OperationalError:
        conn.execute("PRAGMA journal_mode=TRUNCATE;").fetchone()
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
          id INTEGER PRIMARY KEY,
          pdf_name TEXT NOT NULL UNIQUE,
          pdf_path TEXT NOT NULL,
          miner_dir TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pages (
          id INTEGER PRIMARY KEY,
          document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          page_num INTEGER NOT NULL,
          figure_code TEXT,
          figure_label TEXT,
          date_text TEXT,
          page_token TEXT,
          rf_text TEXT
        );

        CREATE TABLE IF NOT EXISTS parts (
          id INTEGER PRIMARY KEY,
          document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          page_num INTEGER NOT NULL,
          page_end INTEGER NOT NULL,
          extractor TEXT NOT NULL,
          meta_data_raw TEXT,
          figure_code TEXT,
          fig_item_raw TEXT,
          fig_item_no TEXT,
          fig_item_no_source TEXT,
          not_illustrated INTEGER NOT NULL DEFAULT 0,
          part_number_cell TEXT,
          part_number_extracted TEXT,
          part_number_canonical TEXT,
          pn_corrected INTEGER NOT NULL DEFAULT 0,
          pn_method TEXT,
          pn_best_similarity REAL,
          pn_needs_review INTEGER NOT NULL DEFAULT 0,
          correction_note TEXT,
          row_kind TEXT NOT NULL,
          nom_level INTEGER NOT NULL DEFAULT 0,
          nomenclature_clean TEXT,
          parent_part_id INTEGER,
          attached_to_part_id INTEGER,
          nomenclature TEXT,
          effectivity TEXT,
          units_per_assy TEXT,
          miner_table_img_path TEXT
        );

        CREATE TABLE IF NOT EXISTS xrefs (
          id INTEGER PRIMARY KEY,
          part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
          kind TEXT NOT NULL,
          target TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS aliases (
          id INTEGER PRIMARY KEY,
          part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
          alias_type TEXT NOT NULL DEFAULT '',
          alias_value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_parts_pn ON parts(part_number_canonical);
        CREATE INDEX IF NOT EXISTS idx_parts_pn_extracted ON parts(part_number_extracted);
        CREATE INDEX IF NOT EXISTS idx_parts_pn_cell ON parts(part_number_cell);
        CREATE INDEX IF NOT EXISTS idx_parts_figure ON parts(figure_code);
        CREATE INDEX IF NOT EXISTS idx_parts_doc_page ON parts(document_id, page_num);
        CREATE INDEX IF NOT EXISTS idx_parts_parent ON parts(parent_part_id);
        CREATE INDEX IF NOT EXISTS idx_parts_attached ON parts(attached_to_part_id);
        CREATE INDEX IF NOT EXISTS idx_parts_nom_clean ON parts(nomenclature_clean);
        CREATE INDEX IF NOT EXISTS idx_parts_nom_level ON parts(nom_level);
        CREATE INDEX IF NOT EXISTS idx_pages_doc_page ON pages(document_id, page_num);
        CREATE INDEX IF NOT EXISTS idx_xrefs_part ON xrefs(part_id);
        CREATE INDEX IF NOT EXISTS idx_alias_value ON aliases(alias_value);
        CREATE INDEX IF NOT EXISTS idx_alias_part ON aliases(part_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_parts_row_unique ON parts(
          document_id,
          page_num,
          COALESCE(figure_code, ''),
          COALESCE(fig_item_raw, ''),
          COALESCE(fig_item_no, ''),
          not_illustrated,
          COALESCE(part_number_cell, ''),
          COALESCE(nomenclature_clean, ''),
          COALESCE(effectivity, ''),
          COALESCE(units_per_assy, ''),
          nom_level,
          COALESCE(parent_part_id, 0)
        );
        """
    )
    conn.commit()


def ingest_pdfs(conn: sqlite3.Connection, pdf_paths: list[Path]) -> dict[str, int]:
    """
    Ingest PDFs into an existing SQLite database without dropping prior documents.

    Existing rows for the same `pdf_name` will be replaced.
    """
    ensure_schema(conn)

    if not pdf_paths:
        return {
            "docs_ingested": 0,
            "docs_replaced": 0,
            "parts_ingested": 0,
            "xrefs_ingested": 0,
            "aliases_ingested": 0,
        }

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        tmp_db_path = Path(tmp.name)

    summary = {
        "docs_ingested": 0,
        "docs_replaced": 0,
        "parts_ingested": 0,
        "xrefs_ingested": 0,
        "aliases_ingested": 0,
    }

    try:
        build_db(output_path=tmp_db_path, pdf_paths=pdf_paths)

        src = sqlite3.connect(str(tmp_db_path))
        src.row_factory = sqlite3.Row
        try:
            src_docs = src.execute(
                "SELECT id, pdf_name, pdf_path, miner_dir, created_at FROM documents ORDER BY id"
            ).fetchall()

            for src_doc in src_docs:
                existing = conn.execute(
                    "SELECT id FROM documents WHERE pdf_name = ?",
                    (src_doc["pdf_name"],),
                ).fetchone()
                if existing is not None:
                    conn.execute("DELETE FROM documents WHERE id = ?", (existing[0],))
                    summary["docs_replaced"] += 1

                dst_doc_cur = conn.execute(
                    """
                    INSERT INTO documents(pdf_name, pdf_path, miner_dir, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        src_doc["pdf_name"],
                        src_doc["pdf_path"],
                        src_doc["miner_dir"],
                        src_doc["created_at"],
                    ),
                )
                if dst_doc_cur.lastrowid is None:
                    raise RuntimeError("Failed to insert destination document row")
                dst_doc_id = int(dst_doc_cur.lastrowid)
                src_doc_id = int(src_doc["id"])
                summary["docs_ingested"] += 1

                src_pages = src.execute(
                    """
                    SELECT page_num, figure_code, figure_label, date_text, page_token, rf_text
                    FROM pages
                    WHERE document_id = ?
                    ORDER BY page_num
                    """,
                    (src_doc_id,),
                ).fetchall()
                for page in src_pages:
                    conn.execute(
                        """
                        INSERT INTO pages(document_id, page_num, figure_code, figure_label, date_text, page_token, rf_text)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            dst_doc_id,
                            page["page_num"],
                            page["figure_code"],
                            page["figure_label"],
                            page["date_text"],
                            page["page_token"],
                            page["rf_text"],
                        ),
                    )

                src_parts = src.execute(
                    """
                    SELECT
                      id, page_num, page_end, extractor, meta_data_raw, figure_code,
                      fig_item_raw, fig_item_no, fig_item_no_source, not_illustrated,
                      part_number_cell, part_number_extracted, part_number_canonical,
                      pn_corrected, pn_method, pn_best_similarity, pn_needs_review, correction_note,
                      row_kind, nom_level, nomenclature_clean, parent_part_id, attached_to_part_id,
                      nomenclature, effectivity, units_per_assy, miner_table_img_path
                    FROM parts
                    WHERE document_id = ?
                    ORDER BY id
                    """,
                    (src_doc_id,),
                ).fetchall()

                max_part_id = int(conn.execute("SELECT COALESCE(MAX(id), 0) FROM parts").fetchone()[0])
                part_id_map: dict[int, int] = {}
                for idx, src_part in enumerate(src_parts, start=1):
                    part_id_map[int(src_part["id"])] = max_part_id + idx

                for src_part in src_parts:
                    src_part_id = int(src_part["id"])
                    dst_part_id = part_id_map[src_part_id]
                    src_parent_id = src_part["parent_part_id"]
                    src_attached_id = src_part["attached_to_part_id"]
                    dst_parent_id = part_id_map.get(int(src_parent_id)) if src_parent_id is not None else None
                    dst_attached_id = part_id_map.get(int(src_attached_id)) if src_attached_id is not None else None

                    conn.execute(
                        """
                        INSERT INTO parts(
                          id, document_id, page_num, page_end, extractor, meta_data_raw, figure_code,
                          fig_item_raw, fig_item_no, fig_item_no_source, not_illustrated,
                          part_number_cell, part_number_extracted, part_number_canonical,
                          pn_corrected, pn_method, pn_best_similarity, pn_needs_review, correction_note,
                          row_kind, nom_level, nomenclature_clean, parent_part_id, attached_to_part_id,
                          nomenclature, effectivity, units_per_assy, miner_table_img_path
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            dst_part_id,
                            dst_doc_id,
                            src_part["page_num"],
                            src_part["page_end"],
                            src_part["extractor"],
                            src_part["meta_data_raw"],
                            src_part["figure_code"],
                            src_part["fig_item_raw"],
                            src_part["fig_item_no"],
                            src_part["fig_item_no_source"],
                            src_part["not_illustrated"],
                            src_part["part_number_cell"],
                            src_part["part_number_extracted"],
                            src_part["part_number_canonical"],
                            src_part["pn_corrected"],
                            src_part["pn_method"],
                            src_part["pn_best_similarity"],
                            src_part["pn_needs_review"],
                            src_part["correction_note"],
                            src_part["row_kind"],
                            src_part["nom_level"],
                            src_part["nomenclature_clean"],
                            dst_parent_id,
                            dst_attached_id,
                            src_part["nomenclature"],
                            src_part["effectivity"],
                            src_part["units_per_assy"],
                            src_part["miner_table_img_path"],
                        ),
                    )
                summary["parts_ingested"] += len(src_parts)

                src_xrefs = src.execute(
                    """
                    SELECT x.part_id, x.kind, x.target
                    FROM xrefs x
                    JOIN parts p ON p.id = x.part_id
                    WHERE p.document_id = ?
                    """,
                    (src_doc_id,),
                ).fetchall()
                for xref in src_xrefs:
                    mapped_part_id = part_id_map.get(int(xref["part_id"]))
                    if mapped_part_id is None:
                        continue
                    conn.execute(
                        "INSERT INTO xrefs(part_id, kind, target) VALUES (?, ?, ?)",
                        (mapped_part_id, xref["kind"], xref["target"]),
                    )
                summary["xrefs_ingested"] += len(src_xrefs)

                src_aliases = src.execute(
                    """
                    SELECT a.part_id, a.alias_type, a.alias_value
                    FROM aliases a
                    JOIN parts p ON p.id = a.part_id
                    WHERE p.document_id = ?
                    """,
                    (src_doc_id,),
                ).fetchall()
                for alias in src_aliases:
                    mapped_part_id = part_id_map.get(int(alias["part_id"]))
                    if mapped_part_id is None:
                        continue
                    conn.execute(
                        "INSERT INTO aliases(part_id, alias_type, alias_value) VALUES (?, ?, ?)",
                        (mapped_part_id, alias["alias_type"], alias["alias_value"]),
                    )
                summary["aliases_ingested"] += len(src_aliases)

                conn.commit()
        finally:
            src.close()
    finally:
        try:
            tmp_db_path.unlink(missing_ok=True)
        except Exception:
            pass

    return summary


def _db_pdf_path(pdf_path: Path) -> str:
    """
    Store a cross-platform-friendly path in SQLite.

    - prefer a relative POSIX-style path (forward slashes)
    - fall back to the basename if we can't make it relative
    """

    try:
        rel = pdf_path.resolve().relative_to(Path.cwd().resolve())
        s = rel.as_posix()
    except Exception:
        s = pdf_path.as_posix()

    # Avoid Windows absolute paths like "C:/..." leaking into DB.
    if re.match(r"^[A-Za-z]:/", s):
        return pdf_path.name
    return s


def _pick_20_default_pdfs() -> list[Path]:
    candidates = sorted(Path("IPC/7NG").glob("*___083.pdf"))
    candidates = [p for p in candidates if not p.name.endswith("-fm___083.pdf")]
    return candidates[:20]


def build_db(output_path: Path, pdf_paths: list[Path]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    conn = sqlite3.connect(str(output_path))
    try:
        _init_db(conn)

        totals = {
            "docs": 0,
            "parts": 0,
            "parts_dedup": 0,
            "pn_corrected": 0,
        }

        for pdf_path in pdf_paths:
            pdf_name = pdf_path.name
            db_pdf_path = _db_pdf_path(pdf_path)
            created_at = dt.datetime.now(dt.timezone.utc).isoformat()
            cur = conn.execute(
                "INSERT INTO documents(pdf_name,pdf_path,miner_dir,created_at) VALUES (?,?,?,?)",
                (
                    pdf_name,
                    db_pdf_path,
                    json.dumps({"kind": "pdf_coords", "units": "cm", "pt_per_cm": PT_PER_CM}, ensure_ascii=False),
                    created_at,
                ),
            )
            if cur.lastrowid is None:
                raise RuntimeError(f"Failed to insert document row for {pdf_name}")
            document_id = int(cur.lastrowid)
            totals["docs"] += 1

            base_prefix = pdf_name.split("___")[0]
            doc = fitz.open(str(pdf_path))
            try:
                # Cache: page meta + candidate index per start page
                page_meta_cache: dict[int, dict[str, str | None]] = {}
                pages_inserted: set[int] = set()
                cand_cache: dict[int, tuple[list[str], set[str], dict[str, str]]] = {}

                hier_stack_by_fig: dict[str, list[int]] = {}

                for rec in _iter_coords_records(doc):
                    page_num = int(rec.start_page)
                    if page_num < 1 or page_num > doc.page_count:
                        continue
                    page = doc[page_num - 1]

                    if page_num not in page_meta_cache:
                        # Prefer footer clip, not full-page scan (full page may contain xref codes).
                        page_meta_cache[page_num] = _parse_meta_clip_text(rec.meta_data_raw or "")

                    meta = page_meta_cache[page_num]
                    figure_code = meta.get("figure_code")
                    fig_key = f"{document_id}:{figure_code or f'PAGE{page_num}'}"

                    if page_num not in pages_inserted:
                        conn.execute(
                            "INSERT INTO pages(document_id,page_num,figure_code,figure_label,date_text,page_token,rf_text) VALUES (?,?,?,?,?,?,?)",
                            (
                                document_id,
                                page_num,
                                meta.get("figure_code"),
                                meta.get("figure_label"),
                                meta.get("date_text"),
                                meta.get("page_token"),
                                meta.get("rf_text"),
                            ),
                        )
                        pages_inserted.add(page_num)

                    if page_num not in cand_cache:
                        cand_cache[page_num] = _candidate_index_from_page(page)
                    candidates, candidates_set, candidates_by_loose = cand_cache[page_num]

                    # FIG ITEM parsing
                    fig_item_raw = (rec.fig_item_text or "").strip()
                    not_illustrated = 0
                    fig_item_no: str | None = None
                    fig_item_no_source: str | None = None

                    if fig_item_raw.startswith("-"):
                        not_illustrated = 1
                        m = re.search(r"(\d+[A-Z]?)", fig_item_raw)
                        if m:
                            fig_item_no = m.group(1)
                            fig_item_no_source = "pdf_coords"
                            fig_item_raw = "-"
                    else:
                        m = re.fullmatch(r"(\d+[A-Z]?)", fig_item_raw)
                        if m:
                            fig_item_no = m.group(1)
                            fig_item_no_source = "pdf_coords"
                            fig_item_raw = ""

                    part_number_cell = (rec.part_number_cell or "").strip()
                    part_number_extracted = part_number_cell
                    pn_canon = _canonicalize_part_number_indexed(
                        candidates=candidates,
                        candidates_set=candidates_set,
                        candidates_by_loose=candidates_by_loose,
                        raw=part_number_extracted,
                    )

                    if pn_canon.corrected:
                        totals["pn_corrected"] += 1

                    nomenclature = _clean_nomenclature_watermarks(rec.nomenclature_text or "")
                    effectivity = (rec.effect_from_to_text or "").strip()
                    units = (rec.units_per_assy_text or "").strip()
                    meta_data_raw = (rec.meta_data_raw or "").strip()
                    page_end = int(rec.end_page or page_num)

                    nom_level, nom_clean = _nomenclature_level_and_clean(nomenclature)
                    stack = hier_stack_by_fig.setdefault(fig_key, [])
                    parent_part_id: int | None = None
                    # Only link to an explicit parent at level (nom_level - 1) if it exists in stack.
                    # Avoid guessing parents when the stack is shorter than the current level, otherwise
                    # we may incorrectly connect siblings as parent/child after a context break.
                    if nom_level > 0 and len(stack) >= nom_level:
                        parent_part_id = stack[nom_level - 1]

                    cur = conn.execute(
                        """
                        INSERT OR IGNORE INTO parts(
                          document_id,page_num,page_end,extractor,meta_data_raw,figure_code,fig_item_raw,fig_item_no,fig_item_no_source,not_illustrated,
                          part_number_cell,part_number_extracted,part_number_canonical,
                          pn_corrected,pn_method,pn_best_similarity,pn_needs_review,correction_note,row_kind,
                          nom_level,nomenclature_clean,parent_part_id,attached_to_part_id,
                          nomenclature,effectivity,units_per_assy,miner_table_img_path
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            document_id,
                            page_num,
                            page_end,
                            "pdf_coords",
                            meta_data_raw or None,
                            figure_code,
                            fig_item_raw or None,
                            fig_item_no,
                            fig_item_no_source,
                            not_illustrated,
                            part_number_cell or None,
                            part_number_extracted or None,
                            pn_canon.canonical or None,
                            1 if pn_canon.corrected else 0,
                            pn_canon.method,
                            pn_canon.best_similarity,
                            1 if pn_canon.needs_review else 0,
                            pn_canon.note,
                            "part",
                            int(nom_level),
                            nom_clean or None,
                            parent_part_id,
                            None,
                            nomenclature or None,
                            effectivity or None,
                            units or None,
                            None,
                        ),
                    )
                    inserted = bool(cur.rowcount)
                    if inserted:
                        part_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                        totals["parts"] += 1
                    else:
                        totals["parts_dedup"] += 1
                        existing = conn.execute(
                            """
                            SELECT id FROM parts
                            WHERE
                              document_id = ?
                              AND page_num = ?
                              AND coalesce(figure_code, '') = ?
                              AND coalesce(fig_item_raw, '') = ?
                              AND coalesce(fig_item_no, '') = ?
                              AND not_illustrated = ?
                              AND coalesce(part_number_cell, '') = ?
                              AND coalesce(nomenclature_clean, '') = ?
                              AND coalesce(effectivity, '') = ?
                              AND coalesce(units_per_assy, '') = ?
                              AND nom_level = ?
                              AND coalesce(parent_part_id, 0) = ?
                            ORDER BY id
                            LIMIT 1
                            """,
                            (
                                document_id,
                                page_num,
                                figure_code or "",
                                fig_item_raw or "",
                                fig_item_no or "",
                                not_illustrated,
                                part_number_cell or "",
                                nom_clean or "",
                                effectivity or "",
                                units or "",
                                int(nom_level),
                                parent_part_id or 0,
                            ),
                        ).fetchone()
                        part_id = int(existing[0]) if existing else 0

                    if len(stack) <= nom_level:
                        # Extend with placeholders for missing levels; we don't want to backfill with
                        # the current node because that would fabricate hierarchy.
                        stack.extend([0] * (nom_level + 1 - len(stack)))
                    stack[nom_level] = part_id
                    del stack[nom_level + 1 :]

                    if inserted:
                        for kind, target in _extract_xrefs(nomenclature):
                            conn.execute(
                                "INSERT INTO xrefs(part_id,kind,target) VALUES (?,?,?)",
                                (part_id, kind, target),
                            )

                conn.commit()
            finally:
                doc.close()

        print(f"[OK] wrote {output_path}")
        print("[SUM] docs={docs} parts={parts} parts_dedup={parts_dedup} pn_corrected={pn_corrected}".format(**totals))
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default="tmp/ipc_coords_demo.sqlite", help="SQLite 输出路径（新库）")
    parser.add_argument("--pdf", action="append", default=[], help="要处理的 PDF 路径（可重复传参）")
    parser.add_argument("--pdf-glob", action="append", default=[], help="用 glob 选择 PDF（可重复传参）")
    parser.add_argument("--limit", type=int, default=20, help="未指定 --pdf 时默认取前 N 个（默认 20）")
    parser.add_argument(
        "--exclude-frontmatter",
        action="store_true",
        help="排除前言/说明类 PDF（例如 '*-fm*.pdf', '*-0fm.pdf', '0-FRONT.pdf'）",
    )
    args = parser.parse_args()

    output_path = Path(args.output)

    pdf_paths: list[Path] = []
    for p in args.pdf or []:
        pdf_paths.append(Path(p))
    for pattern in args.pdf_glob or []:
        for hit in sorted(Path(".").glob(pattern)):
            pdf_paths.append(Path(hit))

    if not pdf_paths:
        pdf_paths = _pick_20_default_pdfs()
        pdf_paths = pdf_paths[: max(1, int(args.limit))]

    if args.exclude_frontmatter:
        out: list[Path] = []
        for p in pdf_paths:
            name = p.name.lower()
            if name == "0-front.pdf":
                continue
            if "-0fm" in name:
                continue
            if "-fm" in name:
                continue
            out.append(p)
        pdf_paths = out

    # Deduplicate, keep order
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in pdf_paths:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    pdf_paths = uniq

    missing = [str(p) for p in pdf_paths if not p.exists()]
    if missing:
        print("[ERR] Missing PDF files:", ", ".join(missing))
        return 2

    build_db(output_path=output_path, pdf_paths=pdf_paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
