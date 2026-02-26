from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


MONTHS = "(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)"
DATE_RE = re.compile(rf"\b{MONTHS}\s+\d{{1,2}}/\d{{2}}\b", re.I)
PAGE_TOKEN_RE = re.compile(r"\bPAGE\s+[0-9A-Z]+\b", re.I)
FIG_LINE_RE = re.compile(r"^FIG\.?\s+(.+)$", re.I)
FIGURE_LINE_RE = re.compile(r"^FIGURE\s+(.+)$", re.I)

NOM_LEADING_DOTS_RE = re.compile(r"^\s*(\.+)\s*(.*)$", re.S)


def _canon_figure_suffix(raw: str) -> str:
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


def _nomenclature_level(nomenclature_first_line: str) -> int:
    m = NOM_LEADING_DOTS_RE.match((nomenclature_first_line or "").strip())
    if not m:
        return 0
    return len(m.group(1) or "")


PT_PER_CM = 72.0 / 2.54


def _pt(cm: float) -> float:
    return float(cm) * PT_PER_CM


COORD_META_RECT = fitz.Rect(_pt(16.3), _pt(25.4), _pt(19.5), _pt(27.4))
COORD_TABLE_RECT = fitz.Rect(_pt(2.3), _pt(2.5), _pt(19.5), _pt(25.4))
COORD_Y_SCAN_START = _pt(3.8)
COORD_Y_TABLE_BOTTOM = _pt(25.4)
COORD_COLS_X = {
    "fig_item": (_pt(2.3), _pt(3.8)),
    "part_number": (_pt(3.8), _pt(7.9)),
    "nomenclature": (_pt(7.9), _pt(16.3)),
}


@dataclass(frozen=True)
class FooterMeta:
    prefix: str
    figure_code: str | None
    figure_label: str | None
    date_text: str | None
    page_token: str | None


def parse_footer_meta_from_page(page: fitz.Page) -> FooterMeta:
    text = page.get_text("text", clip=COORD_META_RECT) or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    prefix = (lines[0].upper() if lines else "")
    fig_label = None
    fig_code = None
    date_text = None
    page_token = None
    for ln in lines[1:12]:
        if not page_token and PAGE_TOKEN_RE.search(ln):
            page_token = PAGE_TOKEN_RE.search(ln).group(0).upper()
        if not date_text and DATE_RE.search(ln):
            date_text = DATE_RE.search(ln).group(0).upper()
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
    return FooterMeta(prefix=prefix, figure_code=fig_code, figure_label=fig_label, date_text=date_text, page_token=page_token)


def find_part_rows_on_page(pdf_path: Path, page_num: int, part_number: str) -> list[dict[str, Any]]:
    pn_target = (part_number or "").strip().upper()
    if not pn_target:
        return []
    with fitz.open(str(pdf_path)) as doc:
        page = doc[page_num - 1]
        words = page.get_text("words", clip=COORD_TABLE_RECT) or []

        x0, x1 = COORD_COLS_X["part_number"]
        fx0, fx1 = COORD_COLS_X["fig_item"]
        nx0, nx1 = COORD_COLS_X["nomenclature"]

        pn_words: list[tuple[Any, ...]] = []
        fig_words: list[tuple[Any, ...]] = []
        nom_words: list[tuple[Any, ...]] = []
        for w in words:
            wx0, wy0, wx1, wy1, *_ = w
            cx = (float(wx0) + float(wx1)) / 2.0
            cy = (float(wy0) + float(wy1)) / 2.0
            if cy < COORD_Y_SCAN_START or cy > COORD_Y_TABLE_BOTTOM:
                continue
            if x0 <= cx <= x1:
                pn_words.append(w)
            if fx0 <= cx <= fx1:
                fig_words.append(w)
            if nx0 <= cx <= nx1:
                nom_words.append(w)

        hits_y: list[float] = []
        for y, grp in _words_by_y(pn_words, y_tol=2.0):
            pn = _join_words_line(grp, sep="").replace(" ", "").strip().upper()
            if pn == pn_target:
                hits_y.append(float(y))

        out: list[dict[str, Any]] = []
        for y in hits_y:
            fig_near = [
                w for w in fig_words if abs(((float(w[1]) + float(w[3])) / 2.0) - float(y)) <= 6.0
            ]
            fig_item = _join_words_line(fig_near, sep=" ").strip()

            nom_near = [
                w for w in nom_words if abs(((float(w[1]) + float(w[3])) / 2.0) - float(y)) <= 9.0
            ]
            nom_first = _join_words_line(nom_near, sep=" ").strip()
            nom_level = _nomenclature_level(nom_first)

            out.append({"y": y, "fig_item": fig_item, "nomenclature_first": nom_first, "nom_level": nom_level})

        return out


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


def _looks_like_part_number(s: str) -> bool:
    t = (s or "").strip().upper()
    if not t:
        return False
    if t.isdigit():
        return len(t) >= 3
    if not any(ch.isdigit() for ch in t):
        return False
    # allow typical IPC PN charset
    return bool(re.fullmatch(r"[A-Z0-9][A-Z0-9\-\./]*", t))


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
    dedup_y_tol = 3.0
    for y, grp in _words_by_y(picked, y_tol=2.0):
        pn = _join_words_line(grp, sep="").replace(" ", "").strip().upper()
        if not _looks_like_part_number(pn):
            continue
        if anchors and pn == anchors[-1][1] and abs(float(y) - float(anchors[-1][0])) <= dedup_y_tol:
            continue
        anchors.append((float(y), pn))
    return sorted(anchors, key=lambda x: x[0])


def extract_rows_on_page(pdf_path: Path, page_num: int) -> list[dict[str, Any]]:
    """
    Extract table rows on a page using the same "fixed coordinates + y segments" idea.
    This is used as a PDF-grounded oracle for QA, not as the production extractor.
    """
    with fitz.open(str(pdf_path)) as doc:
        page = doc[page_num - 1]
        table_words = page.get_text("words", clip=COORD_TABLE_RECT) or []
        anchors = _coords_part_number_anchors(table_words)
        out: list[dict[str, Any]] = []
        for i, (y0, pn) in enumerate(anchors):
            y_start = float(y0)
            y_end = float(anchors[i + 1][0]) if (i + 1) < len(anchors) else float(COORD_Y_TABLE_BOTTOM)
            fig_item_text = _coords_col_text(table_words, "fig_item", y_start, y_end)
            fig_item_text = (fig_item_text.splitlines()[0].strip() if fig_item_text.strip() else "")
            nom = _coords_col_text(table_words, "nomenclature", y_start, y_end)
            first = (nom.splitlines()[0] if nom.strip() else "").strip()
            out.append(
                {
                    "y": y_start,
                    "part_number": pn,
                    "fig_item": fig_item_text,
                    "nomenclature_first": first,
                    "nom_level": _nomenclature_level(first),
                }
            )
        return out


def truth_parent_for_row(pdf_path: Path, page_num: int, part_number: str, fig_item: str | None) -> dict[str, str]:
    """
    Build a PDF-truth hierarchy within the same footer figure_code (across all pages of that figure),
    then return the parent/root part_number for the requested row.
    """
    pn_target = (part_number or "").strip().upper()
    fig_item_target = (fig_item or "").strip()

    with fitz.open(str(pdf_path)) as doc:
        if page_num < 1 or page_num > doc.page_count:
            return {"parent": "", "root": "", "figure_code": ""}
        meta = parse_footer_meta_from_page(doc[page_num - 1])
        code = (meta.figure_code or "").strip().upper()
        if not code:
            return {"parent": "", "root": "", "figure_code": ""}

        # gather pages belonging to this figure_code, up to current page
        pages = []
        for i in range(doc.page_count):
            m = parse_footer_meta_from_page(doc[i])
            if (m.figure_code or "").strip().upper() == code:
                pages.append(i + 1)
        pages = [p for p in pages if p <= page_num]
        pages.sort()

    # build stack using extracted rows in page order, then y order
    stack: list[str] = []
    parent_for_key: dict[tuple[int, str, str], str] = {}
    root_for_key: dict[tuple[int, str, str], str] = {}

    for p in pages:
        rows = extract_rows_on_page(pdf_path, p)
        rows.sort(key=lambda r: float(r.get("y") or 0.0))
        for r in rows:
            pn = str(r.get("part_number") or "").strip().upper()
            fig = str(r.get("fig_item") or "").strip()
            lvl = int(r.get("nom_level") or 0)
            parent = ""
            if lvl > 0 and len(stack) >= lvl:
                parent = stack[lvl - 1]

            if len(stack) <= lvl:
                stack.extend([""] * (lvl + 1 - len(stack)))
            stack[lvl] = pn
            del stack[lvl + 1 :]

            root = stack[0] if stack else ""
            parent_for_key[(p, pn, fig)] = parent
            root_for_key[(p, pn, fig)] = root

    # try to match
    key_candidates = [k for k in parent_for_key.keys() if k[0] == page_num and k[1] == pn_target]
    if not key_candidates:
        return {"parent": "", "root": "", "figure_code": code}

    key = None
    if fig_item_target:
        for k in key_candidates:
            if k[2] == fig_item_target:
                key = k
                break
    if key is None:
        key = key_candidates[0]

    return {"parent": parent_for_key.get(key, ""), "root": root_for_key.get(key, ""), "figure_code": code}
