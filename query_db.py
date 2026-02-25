from __future__ import annotations

import argparse
import sqlite3
import sys
from textwrap import shorten


def _force_utf8_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass


_force_utf8_stdout()


def query(db_path: str, part_number: str) -> int:
    part_number = part_number.strip().upper()
    if not part_number:
        print("[ERR] empty part number")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
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
              p.part_number_extracted,
              p.part_number_canonical,
              p.pn_corrected,
              p.pn_method,
              p.pn_needs_review,
              p.correction_note,
              p.row_kind,
              p.nomenclature,
              p.effectivity,
              p.units_per_assy
            FROM parts p
            JOIN documents d ON d.id = p.document_id
            LEFT JOIN aliases a ON a.part_id = p.id
            WHERE
              UPPER(p.part_number_canonical) = ?
              OR UPPER(p.part_number_extracted) = ?
              OR UPPER(p.part_number_cell) = ?
              OR UPPER(a.alias_value) = ?
            ORDER BY d.pdf_name, p.figure_code, p.page_num, p.fig_item_no
            """,
            (part_number, part_number, part_number, part_number),
        ).fetchall()

        if not rows:
            print(f"[MISS] {part_number} not found")
            return 1

        print(f"[HIT] {part_number}  ({len(rows)} rows)")
        for r in rows:
            title = shorten((r["nomenclature"] or "").replace("\n", " "), width=90, placeholder="…")
            fig_raw = (r["fig_item_raw"] or "").strip()
            fig_no = (r["fig_item_no"] or "").strip()
            if fig_raw == "-" and fig_no:
                fig_item = f"- {fig_no}"
            elif fig_raw and fig_no:
                fig_item = f"{fig_raw} {fig_no}"
            else:
                fig_item = fig_raw or fig_no

            corr = " corrected" if r["pn_corrected"] else ""
            warn = " review" if r["pn_needs_review"] else ""
            raw_hint = ""
            if r["pn_corrected"] and r["part_number_extracted"] and (r["part_number_extracted"] != r["part_number_canonical"]):
                raw_hint = f" raw={r['part_number_extracted']}"
            print(
                f"- {r['source_pdf']} p{r['page_num']} {r['figure_code'] or ''}  FIG_ITEM={fig_item or ''}"
                f"  PN={r['part_number_canonical'] or ''}{corr}{warn} ({r['pn_method']}){raw_hint}  QTY={r['units_per_assy'] or ''}"
            )
            if title:
                print(f"  {title}")

        # show xrefs (optional)
        part_ids = [r["id"] for r in rows]
        q_marks = ",".join(["?"] * len(part_ids))
        xrefs = conn.execute(
            f"SELECT part_id, kind, target FROM xrefs WHERE part_id IN ({q_marks}) ORDER BY part_id, kind",
            part_ids,
        ).fetchall()
        if xrefs:
            print("\n[XREF]")
            for xr in xrefs:
                print(f"- part_id={xr['part_id']} {xr['kind']}: {xr['target']}")

        return 0
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("part_number", type=str, help="要查询的件号/模块号（不区分大小写）")
    parser.add_argument("--db", type=str, default="tmp/ipc_coords_demo.sqlite", help="SQLite 路径（新库）")
    args = parser.parse_args()
    return query(args.db, args.part_number)


if __name__ == "__main__":
    raise SystemExit(main())
