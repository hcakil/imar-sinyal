"""
Legacy Vision extraction prototype retained for regression reference.

Uses Google Gemini (gemini-2.5-flash) to visually read strikethrough /
crossed-out text as OLD values vs replacement text as NEW values.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an expert Turkish urban planner and real estate data analyst. "
    "Examine the provided municipal plan note images. Pay close attention to "
    "crossed-out (strikethrough) text, which represents the OLD rules, and the "
    "text replacing it, which represents the NEW rules. Extract the data into a "
    "strict JSON format with the following keys:\n"
    "- `plan_name`: (String) General name or location of the plan.\n"
    "- `ada_parsel_list`: (Array of Strings) List of affected block/parcel "
    "(Ada/Parsel) numbers mentioned.\n"
    "- `old_emsal`: (Float or String) The old floor area ratio (Emsal), usually crossed out.\n"
    "- `new_emsal`: (Float or String) The new floor area ratio.\n"
    "- `old_function`: (String) e.g., Tarla, Konut.\n"
    "- `new_function`: (String) e.g., Ticaret, Konut.\n"
    "- `summary`: (String) A brief 2-sentence summary of what this plan changes.\n"
    "If a value is not found, return null."
)

DEFAULT_MODEL = "gemini-2.5-flash"
# gemini-2.5-flash is listed but rejected for many new API keys; fall back in order.
FALLBACK_MODELS = (
    "gemini-3-flash-preview",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
)
MAX_PAGES_DEFAULT = 8

EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "plan_name": {"type": ["string", "null"]},
        "ada_parsel_list": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
        "old_emsal": {"type": ["number", "string", "null"]},
        "new_emsal": {"type": ["number", "string", "null"]},
        "old_function": {"type": ["string", "null"]},
        "new_function": {"type": ["string", "null"]},
        "summary": {"type": ["string", "null"]},
    },
    "required": [
        "plan_name",
        "ada_parsel_list",
        "old_emsal",
        "new_emsal",
        "old_function",
        "new_function",
        "summary",
    ],
}


@dataclass
class ExtractionResult:
    plan_name: Optional[str] = None
    ada_parsel_list: Optional[list[str]] = None
    old_emsal: Any = None
    new_emsal: Any = None
    old_function: Optional[str] = None
    new_function: Optional[str] = None
    summary: Optional[str] = None
    model: Optional[str] = None
    raw_response: Optional[str] = None
    parse_error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def ok(self) -> bool:
        return self.parse_error is None


def _get_api_key() -> str:
    load_dotenv()
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip().strip('"').strip("'")
    if not api_key:
        raise RuntimeError("Missing Gemini API key. Set GEMINI_API_KEY in .env")
    return api_key


def _get_client(client: Optional[genai.Client] = None) -> genai.Client:
    if client is not None:
        return client
    # 120s timeout avoids infinite hangs on overloaded models / retries.
    return genai.Client(
        api_key=_get_api_key(),
        http_options=types.HttpOptions(timeout=120_000),
    )


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_extraction_json(text: str) -> tuple[dict[str, Any], Optional[str]]:
    cleaned = _strip_code_fence(text)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data, None
        return {}, "Response JSON was not an object"
    except json.JSONDecodeError as exc:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    return data, None
            except json.JSONDecodeError:
                pass
        return {}, f"JSON parse error: {exc}"


def _result_from_data(
    data: dict[str, Any],
    *,
    model_name: str,
    raw: str,
    err: Optional[str] = None,
) -> ExtractionResult:
    ada_list = data.get("ada_parsel_list")
    if ada_list is not None and not isinstance(ada_list, list):
        ada_list = [str(ada_list)]

    return ExtractionResult(
        plan_name=data.get("plan_name"),
        ada_parsel_list=ada_list,
        old_emsal=data.get("old_emsal"),
        new_emsal=data.get("new_emsal"),
        old_function=data.get("old_function"),
        new_function=data.get("new_function"),
        summary=data.get("summary"),
        model=model_name,
        raw_response=raw,
        parse_error=err,
    )


def _is_model_unavailable_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "404" in text
        or "not_found" in text
        or "no longer available" in text
        or "not found" in text
        or "deadline_exceeded" in text
        or "504" in text
    )


def _generate_with_fallback(
    gemini: genai.Client,
    *,
    model_name: str,
    contents: list[Any],
    config: dict[str, Any],
    skip_models: Optional[set[str]] = None,
) -> tuple[Any, str]:
    """Try preferred model, then fallbacks if Google retired it for new keys."""
    skipped = skip_models if skip_models is not None else set()
    candidates = [model_name]
    for fallback in FALLBACK_MODELS:
        if fallback not in candidates:
            candidates.append(fallback)

    last_error: Optional[Exception] = None
    for candidate in candidates:
        if candidate in skipped:
            continue
        try:
            if candidate != model_name:
                logger.warning(
                    "Model %s unavailable; falling back to %s",
                    model_name,
                    candidate,
                )
            response = gemini.models.generate_content(
                model=candidate,
                contents=contents,
                config=config,
            )
            return response, candidate
        except Exception as exc:
            last_error = exc
            if _is_model_unavailable_error(exc):
                skipped.add(candidate)
                continue
            raise
    assert last_error is not None
    raise last_error


# Process-wide memory of models that returned 404 / unavailable for this key.
_UNAVAILABLE_MODELS: set[str] = set()


def extract_from_base64_images(
    base64_images: list[str],
    *,
    client: Optional[genai.Client] = None,
    model: Optional[str] = None,
    max_pages: int = MAX_PAGES_DEFAULT,
    plan_context: Optional[str] = None,
) -> ExtractionResult:
    """
    Send page images to Gemini Vision and return structured zoning data.

    Errors are returned via ExtractionResult.parse_error so callers (main.py)
    can log the failure and continue with remaining plans.
    """
    preferred_model = model or os.getenv("GEMINI_VISION_MODEL") or DEFAULT_MODEL

    if not base64_images:
        return ExtractionResult(
            model=preferred_model,
            parse_error="No page images provided",
        )

    images = base64_images[:max_pages]
    user_text = (
        "Extract the zoning change data from these plan note page images. "
        "Return ONLY valid JSON matching the schema in the system prompt."
    )
    if plan_context:
        user_text += f"\n\nKnown plan title from GIS: {plan_context}"

    contents: list[Any] = [user_text]
    for b64 in images:
        contents.append(
            types.Part.from_bytes(
                data=base64.b64decode(b64),
                mime_type="image/png",
            )
        )

    effective_model = preferred_model
    if preferred_model in _UNAVAILABLE_MODELS and FALLBACK_MODELS:
        effective_model = next(
            (m for m in FALLBACK_MODELS if m not in _UNAVAILABLE_MODELS),
            FALLBACK_MODELS[0],
        )
        logger.info(
            "Using %s (preferred %s previously unavailable)",
            effective_model,
            preferred_model,
        )

    logger.info(
        "Calling %s with %d page image(s)%s",
        effective_model,
        len(images),
        (
            f" (context={plan_context[:60]}…)"
            if plan_context and len(plan_context) > 60
            else ""
        ),
    )

    # User-required JSON MIME type; schema keeps keys stable.
    config = {
        "system_instruction": SYSTEM_PROMPT,
        "response_mime_type": "application/json",
        "response_json_schema": EXTRACTION_JSON_SCHEMA,
        "temperature": 0,
    }

    try:
        gemini = _get_client(client)
        response, model_used = _generate_with_fallback(
            gemini,
            model_name=effective_model,
            contents=contents,
            config=config,
            skip_models=_UNAVAILABLE_MODELS,
        )
    except Exception as exc:
        logger.error("Gemini extraction failed: %s", exc)
        return ExtractionResult(
            model=preferred_model,
            parse_error=f"Gemini API error: {exc}",
        )

    raw = getattr(response, "text", None) or ""
    if not raw:
        return ExtractionResult(
            model=model_used,
            raw_response=raw,
            parse_error="Empty response from Gemini",
        )

    data, err = _parse_extraction_json(raw)
    return _result_from_data(data, model_name=model_used, raw=raw, err=err)


def extract_from_processed_pdf(
    processed,
    *,
    client: Optional[genai.Client] = None,
    model: Optional[str] = None,
    max_pages: int = MAX_PAGES_DEFAULT,
) -> ExtractionResult:
    """Convenience wrapper around ProcessedPlanPdf from pdf_processor."""
    return extract_from_base64_images(
        processed.base64_images,
        client=client,
        model=model,
        max_pages=max_pages,
        plan_context=processed.plan_name,
    )


def main() -> None:
    import argparse

    from pdf_processor import pdf_to_page_images

    parser = argparse.ArgumentParser(
        description="Extract zoning data from a Plan Note PDF via Gemini."
    )
    parser.add_argument("pdf", type=Path, help="Path to a local plannotu.pdf")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES_DEFAULT)
    parser.add_argument("--model", default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    pages = pdf_to_page_images(args.pdf, dpi=args.dpi, max_pages=args.max_pages)
    result = extract_from_base64_images(
        [p.base64_png for p in pages],
        model=args.model,
        max_pages=args.max_pages,
        plan_context=args.pdf.stem,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
