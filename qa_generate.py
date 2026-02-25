from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz  # PyMuPDF

from pdf_truth import extract_rows_on_page, find_part_rows_on_page, parse_footer_meta_from_page


def _force_utf8_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass


_force_utf8_stdout()


def _scan_deep_dots(pdf_path: Path, *, min_dots: int, limit: int) -> list[dict]:
    out: list[dict] = []
    with fitz.open(str(pdf_path)) as doc:
        for i in range(doc.page_count):
            page_num = i + 1
            text = doc[i].get_text("text") or ""
            if not any(ln.lstrip().startswith("." * min_dots) for ln in text.splitlines()):
                continue
            # try to pick any PN on this page that has min_dots in its nomenclature first line
            # (brute force by looking at several candidate PNs from this page's text)
            # Keep it cheap: sample tokens that look like part numbers.
            tokens = set()
            for tok in text.upper().split():
                if len(tok) < 5:
                    continue
                if any(ch.isdigit() for ch in tok) and all(ch.isalnum() or ch in "-./" for ch in tok):
                    tokens.add(tok.strip())
            for pn in sorted(tokens)[:200]:
                rows = find_part_rows_on_page(pdf_path, page_num, pn)
                if not rows:
                    continue
                if max(r.get("nom_level", 0) for r in rows) >= min_dots:
                    out.append(
                        {
                            "name": f"auto-deep-dots-{pdf_path.name}-p{page_num}-{pn}",
                            "pdf_name": pdf_path.name,
                            "page_num": page_num,
                            "part_number": pn,
                            "expected": {"min_nom_level": min_dots, "pdf_truth": 1},
                        }
                    )
                    break
            if len(out) >= limit:
                break
    return out


def _scan_cross_page_same_figure(pdf_path: Path, *, limit: int) -> list[dict]:
    out: list[dict] = []
    with fitz.open(str(pdf_path)) as doc:
        # find pairs where same figure_code repeats across consecutive pages and page token increments
        metas = []
        for i in range(doc.page_count):
            m = parse_footer_meta_from_page(doc[i])
            metas.append((i + 1, m.figure_code or "", m.page_token or ""))

        for i in range(1, len(metas)):
            p0, code0, token0 = metas[i - 1]
            p1, code1, token1 = metas[i]
            if not code0 or code0 != code1:
                continue
            if p1 != p0 + 1:
                continue
            if "PAGE 1" not in token0.upper() or "PAGE 2" not in token1.upper():
                continue
            # pick a PN on page2 to verify parent linkage via pdf_truth later
            text = doc[p1 - 1].get_text("text") or ""
            tokens = set()
            for tok in text.upper().split():
                if len(tok) < 5:
                    continue
                if any(ch.isdigit() for ch in tok) and all(ch.isalnum() or ch in "-./" for ch in tok):
                    tokens.add(tok.strip())
            picked = None
            picked_fig = None
            for pn in sorted(tokens)[:250]:
                rows = find_part_rows_on_page(pdf_path, p1, pn)
                if rows:
                    picked = pn
                    picked_fig = str(rows[0].get("fig_item") or "").strip()
                    break
            if not picked:
                continue
            out.append(
                {
                    "name": f"auto-cross-page-{pdf_path.name}-{code1}-p{p1}-{picked}",
                    "pdf_name": pdf_path.name,
                    "page_num": p1,
                    "part_number": picked,
                    "fig_item": picked_fig or None,
                    "expected": {"figure_code": code1, "pdf_truth": 1, "pdf_truth_parent": 1},
                }
            )
            if len(out) >= limit:
                break
    return out


def _scan_duplicate_pn_items(pdf_path: Path, *, min_distinct_items: int, limit: int) -> list[dict]:
    out: list[dict] = []
    with fitz.open(str(pdf_path)) as doc:
        for i in range(doc.page_count):
            page_num = i + 1
            rows = extract_rows_on_page(pdf_path, page_num)
            by_pn: dict[str, set[str]] = {}
            for r in rows:
                pn = str(r.get("part_number") or "").strip().upper()
                fig = str(r.get("fig_item") or "").strip()
                if not pn or not fig:
                    continue
                by_pn.setdefault(pn, set()).add(fig)
            # pick one pn that repeats with many items
            picks = [(len(v), pn, sorted(v)) for pn, v in by_pn.items() if len(v) >= min_distinct_items]
            picks.sort(reverse=True)
            for n, pn, fig_items in picks[:2]:
                out.append(
                    {
                        "name": f"auto-dup-pn-{pdf_path.name}-p{page_num}-{pn}",
                        "pdf_name": pdf_path.name,
                        "page_num": page_num,
                        "part_number": pn,
                        "fig_item_set": fig_items,
                        "expected": {"count_at_least": n, "pdf_truth": 1},
                    }
                )
                if len(out) >= limit:
                    return out
    return out


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", action="append", default=[], help="PDF path(s) to scan")
    parser.add_argument("--min-dots", type=int, default=4)
    parser.add_argument("--deep-limit", type=int, default=10)
    parser.add_argument("--cross-limit", type=int, default=5)
    parser.add_argument("--out", type=str, default="demo_coords/qa_samples.auto.json")
    args = parser.parse_args()

    pdfs = [Path(p) for p in args.pdf]
    if not pdfs:
        print("[ERR] no --pdf provided")
        return 2

    samples: list[dict] = []
    for p in pdfs:
        samples.extend(_scan_deep_dots(p, min_dots=int(args.min_dots), limit=int(args.deep_limit)))
        samples.extend(_scan_cross_page_same_figure(p, limit=int(args.cross_limit)))
        samples.extend(_scan_duplicate_pn_items(p, min_distinct_items=3, limit=10))

    out_path = Path(args.out)
    out_path.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] wrote {out_path} ({len(samples)} samples)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
