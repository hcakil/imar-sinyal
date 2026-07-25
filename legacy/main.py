"""Legacy prototype; use ``services/pipeline/imarsinyal`` for the product pipeline."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ai_extractor import ExtractionResult, extract_from_processed_pdf
from pdf_processor import process_plan_pdf
from scraper import PlanRecord, export_plans_json, fetch_active_plans

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/zoning_data.db")
DEFAULT_EXPORT_PATH = Path("exports/extractions.json")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS plans (
    globalid            TEXT PRIMARY KEY,
    source_type         TEXT NOT NULL,
    source_title        TEXT,
    plan_name           TEXT,
    objectid            INTEGER,
    pin                 TEXT,
    ada_parsel          TEXT,
    tapu_ilce_mahalle   TEXT,
    onay_tarihi         TEXT,
    aski_baslangic      TEXT,
    aski_bitis          TEXT,
    onay_sayisi         TEXT,
    plan_note_url       TEXT,
    scraped_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS extractions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    globalid            TEXT NOT NULL,
    source_type         TEXT,
    gis_plan_name       TEXT,
    plan_name           TEXT,
    ada_parsel_list     TEXT,
    old_emsal           TEXT,
    new_emsal           TEXT,
    old_function        TEXT,
    new_function        TEXT,
    summary             TEXT,
    model               TEXT,
    pdf_path            TEXT,
    page_count          INTEGER,
    raw_response        TEXT,
    parse_error         TEXT,
    extracted_at        TEXT NOT NULL,
    UNIQUE(globalid),
    FOREIGN KEY (globalid) REFERENCES plans(globalid)
);
"""


def init_db(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def upsert_plan(conn: sqlite3.Connection, plan: PlanRecord, scraped_at: str) -> None:
    conn.execute(
        """
        INSERT INTO plans (
            globalid, source_type, source_title, plan_name, objectid, pin,
            ada_parsel, tapu_ilce_mahalle, onay_tarihi, aski_baslangic,
            aski_bitis, onay_sayisi, plan_note_url, scraped_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(globalid) DO UPDATE SET
            source_type=excluded.source_type,
            source_title=excluded.source_title,
            plan_name=excluded.plan_name,
            objectid=excluded.objectid,
            pin=excluded.pin,
            ada_parsel=excluded.ada_parsel,
            tapu_ilce_mahalle=excluded.tapu_ilce_mahalle,
            onay_tarihi=excluded.onay_tarihi,
            aski_baslangic=excluded.aski_baslangic,
            aski_bitis=excluded.aski_bitis,
            onay_sayisi=excluded.onay_sayisi,
            plan_note_url=excluded.plan_note_url,
            scraped_at=excluded.scraped_at
        """,
        (
            plan.globalid,
            plan.source_type,
            plan.source_title,
            plan.plan_name,
            plan.objectid,
            plan.pin,
            plan.ada_parsel,
            plan.tapu_ilce_mahalle,
            plan.onay_tarihi,
            plan.aski_baslangic,
            plan.aski_bitis,
            str(plan.onay_sayisi) if plan.onay_sayisi is not None else None,
            plan.plan_note_url,
            scraped_at,
        ),
    )


def already_extracted(conn: sqlite3.Connection, globalid: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM extractions WHERE globalid = ? AND parse_error IS NULL",
        (globalid,),
    ).fetchone()
    return row is not None


def upsert_extraction(
    conn: sqlite3.Connection,
    *,
    plan: PlanRecord,
    extraction: ExtractionResult,
    pdf_path: Path,
    page_count: int,
    extracted_at: str,
) -> None:
    ada_json = (
        json.dumps(extraction.ada_parsel_list, ensure_ascii=False)
        if extraction.ada_parsel_list is not None
        else None
    )
    conn.execute(
        """
        INSERT INTO extractions (
            globalid, source_type, gis_plan_name, plan_name, ada_parsel_list,
            old_emsal, new_emsal, old_function, new_function, summary,
            model, pdf_path, page_count, raw_response, parse_error, extracted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(globalid) DO UPDATE SET
            source_type=excluded.source_type,
            gis_plan_name=excluded.gis_plan_name,
            plan_name=excluded.plan_name,
            ada_parsel_list=excluded.ada_parsel_list,
            old_emsal=excluded.old_emsal,
            new_emsal=excluded.new_emsal,
            old_function=excluded.old_function,
            new_function=excluded.new_function,
            summary=excluded.summary,
            model=excluded.model,
            pdf_path=excluded.pdf_path,
            page_count=excluded.page_count,
            raw_response=excluded.raw_response,
            parse_error=excluded.parse_error,
            extracted_at=excluded.extracted_at
        """,
        (
            plan.globalid,
            plan.source_type,
            plan.plan_name,
            extraction.plan_name,
            ada_json,
            _as_text(extraction.old_emsal),
            _as_text(extraction.new_emsal),
            extraction.old_function,
            extraction.new_function,
            extraction.summary,
            extraction.model,
            str(pdf_path),
            page_count,
            extraction.raw_response,
            extraction.parse_error,
            extracted_at,
        ),
    )


def _as_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _change_label(extraction: ExtractionResult) -> str:
    bits: list[str] = []
    if extraction.old_emsal is not None or extraction.new_emsal is not None:
        bits.append(f"Emsal {extraction.old_emsal} → {extraction.new_emsal}")
    if extraction.old_function or extraction.new_function:
        bits.append(
            f"Function {extraction.old_function} → {extraction.new_function}"
        )
    if not bits and extraction.summary:
        return extraction.summary.split(".")[0].strip()
    return "; ".join(bits) if bits else "(no structured change fields)"


def run_pipeline(
    *,
    limit: Optional[int] = None,
    skip_existing: bool = True,
    dpi: int = 200,
    max_pages: int = 8,
    verify_pdf: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
    export_path: Path = DEFAULT_EXPORT_PATH,
    force_download: bool = False,
) -> dict[str, Any]:
    scraped_at = datetime.now(tz=timezone.utc).isoformat()
    conn = init_db(db_path)

    logger.info("Fetching active askı plans…")
    plans = fetch_active_plans(verify_pdf=verify_pdf)
    export_plans_json(plans, Path("exports/active_plans.json"))

    for plan in plans:
        upsert_plan(conn, plan, scraped_at)
    conn.commit()

    if limit is not None:
        plans = plans[:limit]

    processed_new = 0
    skipped = 0
    failed = 0
    results: list[dict[str, Any]] = []

    for idx, plan in enumerate(plans, start=1):
        logger.info("[%d/%d] %s — %s", idx, len(plans), plan.source_type, plan.plan_name)

        if skip_existing and already_extracted(conn, plan.globalid):
            logger.info("  Skipping (already extracted)")
            skipped += 1
            continue

        if not plan.plan_note_url:
            logger.warning("  No plan_note_url; skipping")
            skipped += 1
            continue

        try:
            processed = process_plan_pdf(
                plan, dpi=dpi, max_pages=max_pages, force_download=force_download
            )
            extraction = extract_from_processed_pdf(
                processed, max_pages=max_pages
            )
            extracted_at = datetime.now(tz=timezone.utc).isoformat()
            upsert_extraction(
                conn,
                plan=plan,
                extraction=extraction,
                pdf_path=processed.pdf_path,
                page_count=processed.page_count,
                extracted_at=extracted_at,
            )
            conn.commit()

            if extraction.ok:
                processed_new += 1
                change = _change_label(extraction)
                logger.info("  Extracted: %s", change)
            else:
                failed += 1
                logger.error("  Parse error: %s", extraction.parse_error)

            results.append(
                {
                    "globalid": plan.globalid,
                    "source_type": plan.source_type,
                    "gis_plan_name": plan.plan_name,
                    "extraction": extraction.to_dict(),
                    "pdf_path": str(processed.pdf_path),
                    "page_count": processed.page_count,
                    "extracted_at": extracted_at,
                }
            )
        except Exception as exc:
            failed += 1
            logger.exception("  Failed: %s", exc)
            results.append(
                {
                    "globalid": plan.globalid,
                    "source_type": plan.source_type,
                    "gis_plan_name": plan.plan_name,
                    "error": str(exc),
                }
            )

    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(
        json.dumps(
            {
                "run_at": scraped_at,
                "active_plans": len(plans) if limit is None else None,
                "processed_new": processed_new,
                "skipped": skipped,
                "failed": failed,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary = {
        "active_plans_scraped": conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0],
        "total_extractions": conn.execute("SELECT COUNT(*) FROM extractions").fetchone()[0],
        "processed_new": processed_new,
        "skipped": skipped,
        "failed": failed,
        "db_path": str(db_path),
        "export_path": str(export_path),
    }
    conn.close()
    return summary


def print_summary(summary: dict[str, Any], results_preview: Optional[Path] = None) -> None:
    print("\n===== İmar Askı Pipeline Summary =====")
    print(f"Active plans in DB : {summary['active_plans_scraped']}")
    print(f"Extractions in DB  : {summary['total_extractions']}")
    print(f"Newly processed    : {summary['processed_new']}")
    print(f"Skipped            : {summary['skipped']}")
    print(f"Failed             : {summary['failed']}")
    print(f"SQLite             : {summary['db_path']}")
    print(f"JSON export        : {summary['export_path']}")

    if results_preview and results_preview.exists():
        payload = json.loads(results_preview.read_text(encoding="utf-8"))
        print("\nDetected changes:")
        for item in payload.get("results", []):
            name = item.get("gis_plan_name") or item.get("globalid")
            if "error" in item:
                print(f"  ✗ [{item.get('source_type')}] {name}: {item['error']}")
                continue
            ext = item.get("extraction") or {}
            label_bits = []
            if ext.get("old_emsal") is not None or ext.get("new_emsal") is not None:
                label_bits.append(f"Emsal {ext.get('old_emsal')} → {ext.get('new_emsal')}")
            if ext.get("old_function") or ext.get("new_function"):
                label_bits.append(
                    f"Function {ext.get('old_function')} → {ext.get('new_function')}"
                )
            detail = "; ".join(label_bits) or (ext.get("summary") or "(see JSON)")
            if ext.get("parse_error"):
                print(f"  ✗ [{item.get('source_type')}] {name}: {ext['parse_error']}")
            else:
                print(f"  • [{item.get('source_type')}] {name}")
                print(f"      {detail}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Ankara İmar Askı scrape → Vision extract → SQLite pipeline."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N plans (useful for smoke tests).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all active plans (ignore default caution).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract even if already in SQLite; also re-download PDFs.",
    )
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--max-pages", type=int, default=8)
    parser.add_argument("--verify-pdf", action="store_true")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--export", type=Path, default=DEFAULT_EXPORT_PATH)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    limit = args.limit
    if limit is None and not args.all:
        # Safe default for first runs / cost control
        limit = 2
        logger.info("No --limit/--all given; defaulting to --limit 2 for cost control")

    summary = run_pipeline(
        limit=limit,
        skip_existing=not args.force,
        dpi=args.dpi,
        max_pages=args.max_pages,
        verify_pdf=args.verify_pdf,
        db_path=args.db,
        export_path=args.export,
        force_download=args.force,
    )
    print_summary(summary, results_preview=args.export)


if __name__ == "__main__":
    main()
