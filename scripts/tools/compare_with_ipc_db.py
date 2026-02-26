from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any


def _force_utf8_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass


_force_utf8_stdout()


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def compare(*, coords_db: Path, ipc_db: Path, limit: int) -> dict[str, Any]:
    t0 = time.time()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA temp_store=MEMORY;").fetchone()
        conn.execute("ATTACH DATABASE ? AS coords", (str(coords_db),)).fetchone()
        conn.execute("ATTACH DATABASE ? AS ipc", (str(ipc_db),)).fetchone()

        # Normalize both DBs into TEMP tables so comparisons are stable and fast.
        #
        # key3: (source_pdf, start_page, part_number)
        # key4: (source_pdf, start_page, part_number, fig_item_text)
        conn.executescript(
            """
            CREATE TEMP TABLE coords_norm AS
            SELECT
              p.id AS part_id,
              d.pdf_name AS source_pdf,
              CAST(p.page_num AS INT) AS start_page,
              UPPER(TRIM(COALESCE(p.part_number_canonical, p.part_number_extracted, p.part_number_cell, ''))) AS part_number,
              TRIM(
                CASE
                  WHEN TRIM(COALESCE(p.fig_item_raw, '')) = '-' AND TRIM(COALESCE(p.fig_item_no, '')) <> '' THEN '- ' || TRIM(p.fig_item_no)
                  WHEN TRIM(COALESCE(p.fig_item_raw, '')) <> '' AND TRIM(COALESCE(p.fig_item_no, '')) <> '' THEN TRIM(p.fig_item_raw) || ' ' || TRIM(p.fig_item_no)
                  WHEN TRIM(COALESCE(p.fig_item_raw, '')) <> '' THEN TRIM(p.fig_item_raw)
                  WHEN TRIM(COALESCE(p.fig_item_no, '')) <> '' THEN CASE WHEN COALESCE(p.not_illustrated, 0) <> 0 THEN '- ' || TRIM(p.fig_item_no) ELSE TRIM(p.fig_item_no) END
                  ELSE ''
                END
              ) AS fig_item_text,
              CAST(COALESCE(p.nom_level, 0) AS INT) AS nom_level,
              UPPER(TRIM(COALESCE(pp.part_number_canonical, pp.part_number_extracted, pp.part_number_cell, ''))) AS parent_pn
            FROM coords.parts p
            JOIN coords.documents d ON d.id = p.document_id
            LEFT JOIN coords.parts pp ON pp.id = p.parent_part_id
            WHERE p.row_kind = 'part';

            CREATE TEMP TABLE ipc_norm AS
            SELECT
              id AS ipc_id,
              TRIM(source_pdf) AS source_pdf,
              CAST(TRIM(start_page) AS INT) AS start_page,
              UPPER(TRIM(part_number)) AS part_number,
              TRIM(COALESCE(fig_item_text, '')) AS fig_item_text,
              UPPER(TRIM(COALESCE(Parent_PN, ''))) AS parent_pn,
              CAST(COALESCE(NULLIF(TRIM(IPC_Level), ''), '0') AS INT) AS ipc_level
            FROM ipc.ipc_rows;

            CREATE INDEX idx_coords_key3 ON coords_norm(source_pdf, start_page, part_number);
            CREATE INDEX idx_ipc_key3 ON ipc_norm(source_pdf, start_page, part_number);
            CREATE INDEX idx_coords_key4 ON coords_norm(source_pdf, start_page, part_number, fig_item_text);
            CREATE INDEX idx_ipc_key4 ON ipc_norm(source_pdf, start_page, part_number, fig_item_text);
            """
        )

        ipc_total = int(conn.execute("SELECT count(*) AS n FROM ipc_norm").fetchone()["n"])
        coords_total = int(conn.execute("SELECT count(*) AS n FROM coords_norm").fetchone()["n"])

        missing_key3 = int(
            conn.execute(
                """
                SELECT count(*) AS n
                FROM ipc_norm i
                LEFT JOIN coords_norm c
                  ON c.source_pdf = i.source_pdf
                 AND c.start_page = i.start_page
                 AND c.part_number = i.part_number
                WHERE c.part_number IS NULL
                """
            ).fetchone()["n"]
        )
        extra_key3 = int(
            conn.execute(
                """
                SELECT count(*) AS n
                FROM coords_norm c
                LEFT JOIN ipc_norm i
                  ON c.source_pdf = i.source_pdf
                 AND c.start_page = i.start_page
                 AND c.part_number = i.part_number
                WHERE i.part_number IS NULL
                """
            ).fetchone()["n"]
        )
        missing_key4 = int(
            conn.execute(
                """
                SELECT count(*) AS n
                FROM ipc_norm i
                LEFT JOIN coords_norm c
                  ON c.source_pdf = i.source_pdf
                 AND c.start_page = i.start_page
                 AND c.part_number = i.part_number
                 AND c.fig_item_text = i.fig_item_text
                WHERE c.part_id IS NULL
                """
            ).fetchone()["n"]
        )
        extra_key4 = int(
            conn.execute(
                """
                SELECT count(*) AS n
                FROM coords_norm c
                LEFT JOIN ipc_norm i
                  ON c.source_pdf = i.source_pdf
                 AND c.start_page = i.start_page
                 AND c.part_number = i.part_number
                 AND c.fig_item_text = i.fig_item_text
                WHERE i.ipc_id IS NULL
                """
            ).fetchone()["n"]
        )

        missing_key3_samples = _rows_to_dicts(
            conn.execute(
                """
                SELECT i.source_pdf, i.start_page, i.fig_item_text, i.part_number, i.parent_pn, i.ipc_level
                FROM ipc_norm i
                LEFT JOIN coords_norm c
                  ON c.source_pdf = i.source_pdf
                 AND c.start_page = i.start_page
                 AND c.part_number = i.part_number
                WHERE c.part_number IS NULL
                ORDER BY i.source_pdf, i.start_page
                LIMIT :limit
                """,
                {"limit": limit},
            ).fetchall()
        )
        extra_key3_samples = _rows_to_dicts(
            conn.execute(
                """
                SELECT c.source_pdf, c.start_page, c.fig_item_text, c.part_number, c.parent_pn, c.nom_level
                FROM coords_norm c
                LEFT JOIN ipc_norm i
                  ON i.source_pdf = c.source_pdf
                 AND i.start_page = c.start_page
                 AND i.part_number = c.part_number
                WHERE i.part_number IS NULL
                ORDER BY c.source_pdf, c.start_page
                LIMIT :limit
                """,
                {"limit": limit},
            ).fetchall()
        )

        parent_mismatch_key4 = int(
            conn.execute(
                """
                SELECT count(*) AS n
                FROM ipc_norm i
                JOIN coords_norm c
                  ON c.source_pdf = i.source_pdf
                 AND c.start_page = i.start_page
                 AND c.part_number = i.part_number
                 AND c.fig_item_text = i.fig_item_text
                WHERE i.parent_pn NOT IN ('', 'MAIN') AND c.parent_pn <> i.parent_pn
                """
            ).fetchone()["n"]
        )
        parent_mismatch_key4_samples = _rows_to_dicts(
            conn.execute(
                """
                SELECT
                  i.source_pdf, i.start_page, i.fig_item_text, i.part_number,
                  i.parent_pn AS ipc_parent_pn,
                  c.parent_pn AS coords_parent_pn
                FROM ipc_norm i
                JOIN coords_norm c
                  ON c.source_pdf = i.source_pdf
                 AND c.start_page = i.start_page
                 AND c.part_number = i.part_number
                 AND c.fig_item_text = i.fig_item_text
                WHERE i.parent_pn NOT IN ('', 'MAIN') AND c.parent_pn <> i.parent_pn
                ORDER BY i.source_pdf, i.start_page
                LIMIT :limit
                """,
                {"limit": limit},
            ).fetchall()
        )

        level_mismatch_key4 = int(
            conn.execute(
                """
                SELECT count(*) AS n
                FROM ipc_norm i
                JOIN coords_norm c
                  ON c.source_pdf = i.source_pdf
                 AND c.start_page = i.start_page
                 AND c.part_number = i.part_number
                 AND c.fig_item_text = i.fig_item_text
                WHERE i.ipc_level <> c.nom_level
                """
            ).fetchone()["n"]
        )
        level_mismatch_key4_samples = _rows_to_dicts(
            conn.execute(
                """
                SELECT
                  i.source_pdf, i.start_page, i.fig_item_text, i.part_number,
                  i.ipc_level AS ipc_level,
                  c.nom_level AS coords_level
                FROM ipc_norm i
                JOIN coords_norm c
                  ON c.source_pdf = i.source_pdf
                 AND c.start_page = i.start_page
                 AND c.part_number = i.part_number
                 AND c.fig_item_text = i.fig_item_text
                WHERE i.ipc_level <> c.nom_level
                ORDER BY i.source_pdf, i.start_page
                LIMIT :limit
                """,
                {"limit": limit},
            ).fetchall()
        )

        elapsed_ms = int((time.time() - t0) * 1000)
        return {
            "coords_db": str(coords_db),
            "ipc_db": str(ipc_db),
            "elapsed_ms": elapsed_ms,
            "totals": {
                "ipc_rows": ipc_total,
                "coords_parts": coords_total,
            },
            "key3": {
                "missing": missing_key3,
                "extra": extra_key3,
                "missing_samples": missing_key3_samples,
                "extra_samples": extra_key3_samples,
            },
            "key4": {
                "missing": missing_key4,
                "extra": extra_key4,
                "parent_mismatch_excluding_main": parent_mismatch_key4,
                "level_mismatch": level_mismatch_key4,
                "parent_mismatch_samples": parent_mismatch_key4_samples,
                "level_mismatch_samples": level_mismatch_key4_samples,
            },
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coords-db", type=str, default="data/ipc.sqlite")
    parser.add_argument("--ipc-db", type=str, default="ipc.db")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--output", type=str, default="tmp/compare_ipc_vs_coords.json")
    args = parser.parse_args()

    coords_db = Path(args.coords_db)
    ipc_db = Path(args.ipc_db)
    output = Path(args.output)

    if not coords_db.exists():
        print(f"[ERR] coords db not found: {coords_db}")
        return 2
    if not ipc_db.exists():
        print(f"[ERR] ipc db not found: {ipc_db}")
        return 2

    report = compare(coords_db=coords_db, ipc_db=ipc_db, limit=max(1, int(args.limit)))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    totals = report["totals"]
    print("[OK] compare done")
    print(f"     - ipc_rows:    {totals['ipc_rows']}")
    print(f"     - coords_parts:{totals['coords_parts']}")
    print(f"     - key3 missing:{report['key3']['missing']}  extra:{report['key3']['extra']}")
    print(f"     - key4 missing:{report['key4']['missing']}  extra:{report['key4']['extra']}")
    print(f"     - parent_mismatch(excl MAIN): {report['key4']['parent_mismatch_excluding_main']}")
    print(f"     - level_mismatch:             {report['key4']['level_mismatch']}")
    print(f"     - report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
