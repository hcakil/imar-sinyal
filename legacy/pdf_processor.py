"""Legacy PDF processor retained for regression reference."""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

import fitz  # PyMuPDF
import requests

from scraper import PlanRecord, _session

logger = logging.getLogger(__name__)

DEFAULT_PDF_DIR = Path("temp_pdfs")
DEFAULT_IMAGE_DIR = Path("temp_pdfs/images")
DEFAULT_DPI = 200
DEFAULT_TIMEOUT = 120


@dataclass
class PageImage:
    page_number: int  # 1-based
    png_path: Path
    base64_png: str
    width: int
    height: int


@dataclass
class ProcessedPlanPdf:
    globalid: str
    source_type: str
    plan_name: Optional[str]
    pdf_path: Path
    page_count: int
    pages: list[PageImage] = field(default_factory=list)

    @property
    def base64_images(self) -> list[str]:
        return [p.base64_png for p in self.pages]


def _safe_slug(value: str, max_len: int = 80) -> str:
    slug = re.sub(r"[^\w\-]+", "_", value, flags=re.UNICODE).strip("_")
    return (slug or "plan")[:max_len]


def pdf_filename_for_plan(plan: PlanRecord) -> str:
    gid = plan.globalid.strip("{}")
    return f"{plan.source_type}_{gid}_plannotu.pdf"


def download_pdf(
    url: str,
    dest_path: Path,
    *,
    session: Optional[requests.Session] = None,
    force: bool = False,
) -> Path:
    """Download a PDF to dest_path. Skips if file already exists unless force=True."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists() and dest_path.stat().st_size > 0 and not force:
        logger.info("PDF already present: %s", dest_path)
        return dest_path

    http = session or _session()
    logger.info("Downloading PDF: %s", unquote(urlparse(url).path))
    response = http.get(url, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    content = response.content
    if not content.startswith(b"%PDF"):
        content_type = response.headers.get("Content-Type", "")
        raise ValueError(
            f"URL did not return a PDF (Content-Type={content_type}, "
            f"size={len(content)}): {url}"
        )
    dest_path.write_bytes(content)
    logger.info("Saved %s (%d bytes)", dest_path, len(content))
    return dest_path


def download_plan_pdf(
    plan: PlanRecord,
    *,
    pdf_dir: Path = DEFAULT_PDF_DIR,
    session: Optional[requests.Session] = None,
    force: bool = False,
) -> Path:
    if not plan.plan_note_url:
        raise ValueError(f"Plan {plan.globalid} has no plan_note_url")
    dest = pdf_dir / pdf_filename_for_plan(plan)
    return download_pdf(plan.plan_note_url, dest, session=session, force=force)


def pdf_to_page_images(
    pdf_path: Path,
    *,
    output_dir: Optional[Path] = None,
    dpi: int = DEFAULT_DPI,
    max_pages: Optional[int] = None,
    save_png: bool = True,
) -> list[PageImage]:
    """
    Render each PDF page to a PNG (and base64) using PyMuPDF.

    High DPI is important so strikethrough / crossed-out text remains readable
    for the Vision model.
    """
    pdf_path = Path(pdf_path)
    if output_dir is None:
        output_dir = DEFAULT_IMAGE_DIR / pdf_path.stem
    output_dir = Path(output_dir)
    if save_png:
        output_dir.mkdir(parents=True, exist_ok=True)

    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    pages: list[PageImage] = []

    with fitz.open(pdf_path) as doc:
        total = len(doc)
        limit = min(total, max_pages) if max_pages else total
        logger.info("Rendering %d/%d page(s) from %s @ %d DPI", limit, total, pdf_path.name, dpi)

        for i in range(limit):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            png_bytes = pix.tobytes("png")
            b64 = base64.b64encode(png_bytes).decode("ascii")

            png_path = output_dir / f"page_{i + 1:03d}.png"
            if save_png:
                png_path.write_bytes(png_bytes)

            pages.append(
                PageImage(
                    page_number=i + 1,
                    png_path=png_path,
                    base64_png=b64,
                    width=pix.width,
                    height=pix.height,
                )
            )

    return pages


def process_plan_pdf(
    plan: PlanRecord,
    *,
    pdf_dir: Path = DEFAULT_PDF_DIR,
    image_dir: Path = DEFAULT_IMAGE_DIR,
    dpi: int = DEFAULT_DPI,
    max_pages: Optional[int] = None,
    force_download: bool = False,
    session: Optional[requests.Session] = None,
) -> ProcessedPlanPdf:
    """Download a plan's Plan Note PDF and convert pages to Vision-ready images."""
    pdf_path = download_plan_pdf(
        plan, pdf_dir=pdf_dir, session=session, force=force_download
    )
    out_dir = image_dir / pdf_path.stem
    pages = pdf_to_page_images(
        pdf_path, output_dir=out_dir, dpi=dpi, max_pages=max_pages, save_png=True
    )
    return ProcessedPlanPdf(
        globalid=plan.globalid,
        source_type=plan.source_type,
        plan_name=plan.plan_name,
        pdf_path=pdf_path,
        page_count=len(pages),
        pages=pages,
    )


def main() -> None:
    import argparse
    import json

    from scraper import fetch_active_plans

    parser = argparse.ArgumentParser(description="Download & rasterize Plan Note PDFs.")
    parser.add_argument("--limit", type=int, default=1, help="Max plans to process.")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Re-download PDFs.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    plans = fetch_active_plans(verify_pdf=False)[: args.limit]
    results = []
    for plan in plans:
        processed = process_plan_pdf(
            plan, dpi=args.dpi, max_pages=args.max_pages, force_download=args.force
        )
        results.append(
            {
                "globalid": processed.globalid,
                "plan_name": processed.plan_name,
                "pdf_path": str(processed.pdf_path),
                "page_count": processed.page_count,
                "image_paths": [str(p.png_path) for p in processed.pages],
            }
        )
        print(f"{processed.plan_name}: {processed.page_count} page(s) -> {processed.pdf_path}")

    out = Path("exports/processed_pdfs.json")
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
