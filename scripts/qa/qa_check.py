from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

try:
    from scripts.qa.pdf_truth import find_part_rows_on_page, parse_footer_meta_from_page, truth_parent_for_row
except ImportError:
    from pdf_truth import find_part_rows_on_page, parse_footer_meta_from_page, truth_parent_for_row  # type: ignore


def _force_utf8_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    try:
        if callable(reconfigure):
            reconfigure(encoding="utf-8")
    except Exception:
        pass


_force_utf8_stdout()


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


def _open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _norm_fig_item_token(s: str) -> str:
    t = (s or "").strip()
    return t[2:] if t.startswith("- ") else t


def _find_rows(
    conn: sqlite3.Connection,
    pdf_name: str,
    page_num: int,
    part_number: str,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
          p.id,
          d.pdf_name AS source_pdf,
          p.page_num,
          p.figure_code,
          p.fig_item_raw,
          p.fig_item_no,
          p.not_illustrated,
          p.part_number_cell,
          p.part_number_canonical,
          p.part_number_extracted,
          p.nom_level,
          p.parent_part_id
        FROM parts p
        JOIN documents d ON d.id = p.document_id
        WHERE d.pdf_name = ? AND p.page_num = ? AND UPPER(coalesce(p.part_number_cell, p.part_number_canonical, p.part_number_extracted, '')) = ?
        ORDER BY p.id
        """,
        (pdf_name, int(page_num), part_number.strip().upper()),
    ).fetchall()


def _parent_pn(conn: sqlite3.Connection, parent_id: int | None) -> str:
    if not parent_id:
        return ""
    row = conn.execute(
        """
        SELECT coalesce(part_number_cell, part_number_canonical, part_number_extracted, '') AS pn
        FROM parts
        WHERE id = ?
        """,
        (int(parent_id),),
    ).fetchone()
    if not row:
        return ""
    return str(row["pn"] or "").strip().upper()


def check(db_path: Path, samples_path: Path) -> int:
    samples = json.loads(samples_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    with _open_db(db_path) as conn:
        for s in samples:
            name = str(s.get("name") or "")
            pdf_name = str(s.get("pdf_name") or "")
            page_num = int(s.get("page_num") or 0)
            pn = str(s.get("part_number") or "").strip().upper()
            expected = s.get("expected") or {}
            pdf_root = Path(str(s.get("pdf_root") or "IPC/7NG"))
            pdf_path = pdf_root / pdf_name

            rows = _find_rows(conn, pdf_name, page_num, pn)
            if not rows:
                failures.append(f"{name}: missing row (pdf={pdf_name} page={page_num} pn={pn})")
                continue

            fig_item = s.get("fig_item")
            if fig_item is not None:
                fig_item = str(fig_item).strip()
                hit = None
                for r in rows:
                    disp = _fig_item_display(r["fig_item_raw"], r["fig_item_no"], int(r["not_illustrated"] or 0)).strip()
                    if disp == fig_item:
                        hit = r
                        break
                if not hit:
                    got = [
                        _fig_item_display(r["fig_item_raw"], r["fig_item_no"], int(r["not_illustrated"] or 0)).strip()
                        for r in rows
                    ]
                    failures.append(f"{name}: fig_item not found, want={fig_item!r} got={got!r}")
                    continue
                rows_to_check = [hit]
            else:
                rows_to_check = rows

            fig_item_set = s.get("fig_item_set")
            if fig_item_set is not None:
                want = {_norm_fig_item_token(str(x)) for x in fig_item_set}
                got_set = {
                    _fig_item_display(r["fig_item_raw"], r["fig_item_no"], int(r["not_illustrated"] or 0)).strip()
                    for r in rows
                }
                got2 = {_norm_fig_item_token(g) for g in got_set}
                if not want.issubset(got2):
                    failures.append(f"{name}: fig_item_set mismatch, want={sorted(want)!r} got={sorted(got2)!r}")

            min_nom_level = expected.get("min_nom_level")
            if min_nom_level is not None:
                want_level = int(min_nom_level)
                got_level = max(int(r["nom_level"] or 0) for r in rows_to_check)
                if got_level < want_level:
                    failures.append(f"{name}: nom_level too small, want>={want_level} got={got_level}")

            exp_fig = expected.get("figure_code")
            if exp_fig is not None:
                want_fig = str(exp_fig).strip().upper()
                got_fig = str(rows_to_check[0]["figure_code"] or "").strip().upper()
                if got_fig != want_fig:
                    failures.append(f"{name}: figure_code mismatch, want={want_fig} got={got_fig}")

            exp_parent = expected.get("parent_part_number")
            if exp_parent is not None:
                want_parent = str(exp_parent).strip().upper()
                got_parent = _parent_pn(conn, rows_to_check[0]["parent_part_id"])
                if got_parent != want_parent:
                    failures.append(f"{name}: parent mismatch, want={want_parent} got={got_parent}")

            exp_count = expected.get("count_at_least")
            if exp_count is not None:
                want_n = int(exp_count)
                if len(rows) < want_n:
                    failures.append(f"{name}: row count too small, want>={want_n} got={len(rows)}")

            if expected.get("pdf_truth") == 1:
                if not pdf_path.exists():
                    failures.append(f"{name}: pdf not found for truth check: {pdf_path}")
                else:
                    truth_rows = find_part_rows_on_page(pdf_path, page_num, pn)
                    if not truth_rows:
                        failures.append(f"{name}: pdf truth missing (pdf={pdf_path} page={page_num} pn={pn})")
                    else:
                        want_set = expected.get("fig_item_set")
                        if want_set is not None:
                            want = {_norm_fig_item_token(str(x)) for x in want_set}
                            truth_fig_set = {str(r.get('fig_item') or '').strip() for r in truth_rows}
                            truth_fig_set = {_norm_fig_item_token(g) for g in truth_fig_set}
                            if not want.issubset(truth_fig_set):
                                failures.append(
                                    f"{name}: pdf truth fig_item_set mismatch, want={sorted(want)!r} got={sorted(truth_fig_set)!r}"
                                )

                        want_min = expected.get("min_nom_level")
                        if want_min is not None:
                            got_max = max(int(r.get('nom_level') or 0) for r in truth_rows)
                            if got_max < int(want_min):
                                failures.append(
                                    f"{name}: pdf truth nom_level too small, want>={int(want_min)} got={got_max}"
                                )

                        want_fig_truth = expected.get("figure_code")
                        if want_fig_truth is not None:
                            import fitz  # PyMuPDF

                            with fitz.open(str(pdf_path)) as doc:
                                meta = parse_footer_meta_from_page(doc[page_num - 1])
                            if (meta.figure_code or "").strip().upper() != str(want_fig_truth).strip().upper():
                                failures.append(
                                    f"{name}: pdf truth footer figure_code mismatch, want={str(want_fig_truth).strip().upper()} got={(meta.figure_code or '').strip().upper()}"
                                )

                        if expected.get("pdf_truth_parent") == 1:
                            # Compare DB parent against PDF-truth derived parent within the same footer figure_code.
                            truth = truth_parent_for_row(
                                pdf_path=pdf_path,
                                page_num=page_num,
                                part_number=pn,
                                fig_item=str(fig_item or ""),
                            )
                            want_parent = (truth.get("parent") or "").strip().upper()
                            got_parent = _parent_pn(conn, rows_to_check[0]["parent_part_id"])
                            if want_parent and got_parent != want_parent:
                                failures.append(f"{name}: pdf truth parent mismatch, want={want_parent} got={got_parent}")

    if failures:
        print("[FAIL]")
        for f in failures:
            print("-", f)
        return 1

    print("[OK] all QA samples passed")
    return 0


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=str, default="data/ipc.sqlite")
    parser.add_argument("--samples", type=str, default="data/fixtures/qa/baseline/qa_samples.json")
    args = parser.parse_args()
    return check(Path(args.db), Path(args.samples))


if __name__ == "__main__":
    raise SystemExit(main())
