from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

import fitz
from google import genai
from google.genai import types
from google.cloud import storage
from PIL import Image

from .models import Evidence, ExtractedChange, MetricChange, SourceRecord
from .normalization import categories_from_text, normalize_metric_kind
from .sources.http import http_session

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.5-flash-lite"
FALLBACK_MODEL = "gemini-3.6-flash"
MAX_RELEVANT_PAGES = 12
MAX_DOWNLOAD_BYTES = 250 * 1024 * 1024
KEYWORDS = (
    "emsal",
    "kaks",
    "taks",
    "yençok",
    "yükseklik",
    "kat adedi",
    "yoğunluk",
    "konut",
    "ticaret",
    "fonksiyon",
    "plan notu",
    "ada",
    "parsel",
)

EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": ["string", "null"]},
        "categories": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "construction_conditions",
                    "land_use",
                    "plan_note",
                    "public_infrastructure",
                    "transportation",
                    "procedural",
                ],
            },
        },
        "function": {"$ref": "#/$defs/metric"},
        "emsal": {"$ref": "#/$defs/metric"},
        "taks": {"$ref": "#/$defs/metric"},
        "yencok": {"$ref": "#/$defs/metric"},
        "density": {"$ref": "#/$defs/metric"},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "page": {"type": ["integer", "null"]},
                    "paragraph": {"type": ["integer", "null"]},
                    "excerpt": {"type": ["string", "null"]},
                    "field_names": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "id",
                    "page",
                    "paragraph",
                    "excerpt",
                    "field_names",
                ],
            },
        },
    },
    "required": [
        "summary",
        "categories",
        "function",
        "emsal",
        "taks",
        "yencok",
        "density",
        "evidence",
    ],
    "$defs": {
        "metric": {
            "type": "object",
            "properties": {
                "old_value": {"type": ["string", "number", "null"]},
                "new_value": {"type": ["string", "number", "null"]},
                "unit": {"type": ["string", "null"]},
                "evidence_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["old_value", "new_value", "unit", "evidence_ids"],
        }
    },
}

SYSTEM_PROMPT = """You extract factual Turkish zoning-plan changes.
Return only the requested structured data.
Rules:
- Crossed-out text is OLD only when the visual strike is unambiguous.
- Never place population density (kişi/ha) in emsal.
- Never place TAKS in emsal.
- Emsal/KAKS, TAKS, Yençok, density and land-use function are separate fields.
- Do not infer a previous value. Use null when the source does not state it.
- Every non-null metric must cite an evidence id pointing to a provided page or paragraph.
- The summary must be factual, neutral, Turkish, and at most two sentences.
- Never call a change an investment opportunity or give advice.
- If evidence is ambiguous, leave the structured value null.
"""


def download_pdf(url: str, path: Path) -> Path:
    response = http_session().get(url, timeout=180, stream=True)
    response.raise_for_status()
    total = 0
    with path.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                raise ValueError("PDF exceeds 250 MiB safety limit")
            handle.write(chunk)
    with path.open("rb") as handle:
        if handle.read(4) != b"%PDF":
            raise ValueError("Source did not return a PDF")
    return path


def download_image_as_pdf(url: str, path: Path) -> tuple[Path, bytes]:
    response = http_session().get(url, timeout=120)
    response.raise_for_status()
    content = response.content
    if not content or len(content) > MAX_DOWNLOAD_BYTES:
        raise ValueError("Image is empty or exceeds 250 MiB safety limit")
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
        source = fitz.open(stream=content, filetype="png")
    except Exception:
        try:
            source = fitz.open(stream=content, filetype="jpeg")
        except Exception as exc:
            raise ValueError("Source did not return a supported image") from exc
    pdf_bytes = source.convert_to_pdf()
    source.close()
    path.write_bytes(pdf_bytes)
    return path, content


def upload_evidence_previews(
    *,
    record: SourceRecord,
    rendered: list[tuple[int, bytes]],
    bucket_name: str | None = None,
) -> dict[int, str]:
    bucket_name = bucket_name or os.getenv("EVIDENCE_BUCKET")
    if not bucket_name:
        return {}
    client = storage.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT") or None)
    bucket = client.bucket(bucket_name)
    urls: dict[int, str] = {}
    for page_number, png in rendered:
        with Image.open(io.BytesIO(png)) as image:
            image.thumbnail((1200, 1600))
            output = io.BytesIO()
            image.save(output, format="WEBP", quality=72, method=4)
        object_name = (
            "evidence/"
            f"{re.sub(r'[^A-Za-z0-9_-]', '_', record.source_id)}/"
            f"{record.snapshot_hash or 'unknown'}-p{page_number}.webp"
        )
        blob = bucket.blob(object_name)
        blob.upload_from_string(output.getvalue(), content_type="image/webp")
        urls[page_number] = f"gs://{bucket_name}/{object_name}"
    return urls


def rank_pdf_pages(pdf_path: Path) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    with fitz.open(pdf_path) as document:
        for index, page in enumerate(document):
            text = page.get_text("text")
            folded = text.casefold()
            score = sum(folded.count(keyword.casefold()) for keyword in KEYWORDS)
            drawings = page.get_drawings()
            # Short horizontal strokes near text often represent redlines. This is
            # a ranking hint only; the vision model still decides whether text is old.
            horizontal_lines = 0
            for drawing in drawings:
                rect = drawing.get("rect")
                if rect and rect.width > 20 and rect.height < 8:
                    horizontal_lines += 1
            score += min(horizontal_lines, 10) * 2
            pages.append(
                {
                    "page": index + 1,
                    "text": text,
                    "score": score,
                    "horizontal_lines": horizontal_lines,
                }
            )
    ranked = sorted(pages, key=lambda item: (-item["score"], item["page"]))
    selected = [item for item in ranked if item["score"] > 0][
        :MAX_RELEVANT_PAGES
    ]
    if not selected:
        selected = ranked[: min(3, len(ranked))]
    return sorted(selected, key=lambda item: item["page"])


def render_pages(
    pdf_path: Path, selected_pages: list[dict[str, Any]], dpi: int = 200
) -> list[tuple[int, bytes]]:
    rendered: list[tuple[int, bytes]] = []
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    with fitz.open(pdf_path) as document:
        for item in selected_pages:
            page_number = int(item["page"])
            page = document.load_page(page_number - 1)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            rendered.append((page_number, pixmap.tobytes("png")))
    return rendered


def _client(client: genai.Client | None = None) -> genai.Client:
    if client:
        return client
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(timeout=180_000),
    )


def _metric(data: dict[str, Any] | None) -> MetricChange:
    value = data or {}
    return MetricChange(
        old_value=value.get("old_value"),
        new_value=value.get("new_value"),
        unit=value.get("unit"),
        evidence_ids=[
            str(item) for item in (value.get("evidence_ids") or [])
        ],
    )


def _parse_result(
    payload: dict[str, Any],
    *,
    source_url: str,
    model: str,
) -> ExtractedChange:
    evidence = [
        Evidence(
            id=str(item["id"]),
            document_url=source_url,
            page=item.get("page"),
            paragraph=item.get("paragraph"),
            excerpt=(item.get("excerpt") or "")[:500] or None,
            field_names=[str(name) for name in item.get("field_names") or []],
        )
        for item in (payload.get("evidence") or [])
        if item.get("id")
    ]
    change = ExtractedChange(
        function=_metric(payload.get("function")),
        emsal=_metric(payload.get("emsal")),
        taks=_metric(payload.get("taks")),
        yencok=_metric(payload.get("yencok")),
        density=_metric(payload.get("density")),
        categories=[
            str(item) for item in (payload.get("categories") or [])
        ],
        summary=payload.get("summary"),
        evidence=evidence,
        model=model,
    )
    return normalize_metric_kind(change)


def _generate(
    contents: list[Any],
    *,
    source_url: str,
    client: genai.Client | None = None,
) -> ExtractedChange:
    gemini = _client(client)
    last_error: Exception | None = None
    for model in (DEFAULT_MODEL, FALLBACK_MODEL):
        try:
            response = gemini.models.generate_content(
                model=model,
                contents=contents,
                config={
                    "system_instruction": SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                    "response_json_schema": EXTRACTION_SCHEMA,
                },
            )
            raw = response.text or "{}"
            payload = json.loads(raw)
            return _parse_result(payload, source_url=source_url, model=model)
        except Exception as exc:
            last_error = exc
            logger.warning("Extraction with %s failed: %s", model, exc)
    return ExtractedChange(
        parse_error=f"Gemini extraction failed: {last_error}",
        model=FALLBACK_MODEL,
    )


def extract_pdf_record(
    record: SourceRecord,
    *,
    workdir: Path,
    client: genai.Client | None = None,
) -> ExtractedChange:
    document = record.documents.get("plan_note") or record.documents.get("primary")
    if not document:
        return ExtractedChange(parse_error="No PDF document")
    workdir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", record.source_id)
    if (document.media_type or "").startswith("image/"):
        pdf_path, source_bytes = download_image_as_pdf(
            document.url, workdir / f"{safe_name}.pdf"
        )
        document.sha256 = hashlib.sha256(source_bytes).hexdigest()
        document.size_bytes = len(source_bytes)
    else:
        pdf_path = download_pdf(document.url, workdir / f"{safe_name}.pdf")
        document.sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        document.size_bytes = pdf_path.stat().st_size
    selected = rank_pdf_pages(pdf_path)
    rendered = render_pages(pdf_path, selected)
    preview_urls = upload_evidence_previews(record=record, rendered=rendered)
    contents: list[Any] = [
        (
            f"Known source title: {record.title}\n"
            f"Pages supplied: {[number for number, _ in rendered]}.\n"
            "Evidence page numbers must use these original PDF page numbers."
        )
    ]
    for page_number, png in rendered:
        contents.append(f"Original PDF page {page_number}:")
        contents.append(types.Part.from_bytes(data=png, mime_type="image/png"))
    result = _generate(contents, source_url=document.url, client=client)
    for evidence in result.evidence:
        if evidence.page in preview_urls:
            evidence.image_url = preview_urls[evidence.page]
    if not result.categories:
        result.categories = categories_from_text(record.title)
    return result


def extract_text_record(
    record: SourceRecord,
    text: str,
    *,
    client: genai.Client | None = None,
) -> ExtractedChange:
    document = record.documents.get("primary")
    source_url = document.url if document else ""
    contents = [
        (
            f"Known source title: {record.title}\n"
            "The document below contains paragraph numbers in [P:n] markers. "
            "Use those numbers in evidence.paragraph.\n\n"
            f"{text[:150_000]}"
        )
    ]
    result = _generate(contents, source_url=source_url, client=client)
    if not result.categories:
        result.categories = categories_from_text(f"{record.title} {text}")
    return result


def numbered_paragraph_text(
    evidence: list[dict[str, object]],
) -> str:
    return "\n".join(
        f"[P:{item['paragraph']}] {item['text']}" for item in evidence
    )


def extraction_debug_json(change: ExtractedChange) -> str:
    return json.dumps(asdict(change), ensure_ascii=False, indent=2)
