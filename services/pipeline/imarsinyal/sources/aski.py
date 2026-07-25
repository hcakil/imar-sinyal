from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests

from ..models import SourceDocument, SourceRecord
from ..normalization import (
    district_from_text,
    neighborhood_from_text,
    normalize_parcels,
    plan_scales_from_text,
    stable_hash,
)
from .http import http_session

logger = logging.getLogger(__name__)

APP_ROOT = "https://planaski.ankara.bel.tr/planaski"
PAGE_SIZE = 1000
TIMEOUT = 90

ASKI_SOURCES: tuple[dict[str, str], ...] = (
    {
        "type": "UIP",
        "title": "1/1000 Uygulama İmar Planı",
        "url": "https://baskentcbs.ankara.bel.tr/server/rest/services/aktifAski/SinirUipAski/MapServer/0",
    },
    {
        "type": "NIP",
        "title": "1/5000 Nazım İmar Planı",
        "url": "https://baskentcbs.ankara.bel.tr/server/rest/services/aktifAski/SinirNipAski/MapServer/0",
    },
    {
        "type": "NIP25",
        "title": "1/25000 Nazım İmar Planı",
        "url": "https://baskentcbs.ankara.bel.tr/server/rest/services/aktifAski/SinirNip25Aski/MapServer/0",
    },
    {
        "type": "CDP",
        "title": "1/100000 Çevre Düzeni Planı",
        "url": "https://planaski.ankara.bel.tr/webgis/rest/services/aktifAski/aktifAskiCdp100000/MapServer/0",
    },
)

DEFAULT_SCALES = {
    "UIP": ["1/1000"],
    "NIP": ["1/5000"],
    "NIP25": ["1/25000"],
    "CDP": ["1/100000"],
}


def _pick(attrs: dict[str, Any], *names: str) -> Any:
    folded = {key.casefold(): value for key, value in attrs.items()}
    for name in names:
        if name in attrs:
            return attrs[name]
        if name.casefold() in folded:
            return folded[name.casefold()]
    return None


def _date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        match = re.search(r"\d{4}-\d{2}-\d{2}", value)
        return match.group(0) if match else value
    try:
        number = int(value)
        if number < 10_000_000_000:
            number *= 1000
        return datetime.fromtimestamp(
            number / 1000, tz=timezone.utc
        ).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return str(value)


def _globalid(value: Any) -> str:
    text = str(value or "").strip().strip("{}")
    return text.upper()


def _document_url(source_type: str, globalid: str, filename: str) -> str:
    encoded = quote(f"{{{globalid}}}", safe="")
    return (
        f"{APP_ROOT}/_files/askiplanlari/{source_type}/{encoded}/{filename}"
    )


def _bbox_and_centroid(geometry: dict[str, Any] | None) -> dict[str, Any] | None:
    if not geometry:
        return None
    points: list[tuple[float, float]] = []
    if geometry.get("rings"):
        for ring in geometry["rings"]:
            points.extend((float(pair[0]), float(pair[1])) for pair in ring)
    elif geometry.get("paths"):
        for path in geometry["paths"]:
            points.extend((float(pair[0]), float(pair[1])) for pair in path)
    elif "x" in geometry and "y" in geometry:
        points.append((float(geometry["x"]), float(geometry["y"])))
    if not points:
        return {"geojson": geometry}
    xs, ys = zip(*points)
    return {
        "geojson": geometry,
        "bbox": [
            round(min(xs), 6),
            round(min(ys), 6),
            round(max(xs), 6),
            round(max(ys), 6),
        ],
        "centroid": [
            round(sum(xs) / len(xs), 6),
            round(sum(ys) / len(ys), 6),
        ],
    }


def query_layer(
    layer_url: str, session: requests.Session | None = None
) -> list[dict[str, Any]]:
    http = session or http_session()
    offset = 0
    features: list[dict[str, Any]] = []
    while True:
        response = http.get(
            f"{layer_url}/query",
            params={
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": "4326",
                "resultOffset": offset,
                "resultRecordCount": PAGE_SIZE,
                "orderByFields": "objectid ASC",
                "f": "json",
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise RuntimeError(f"ArcGIS error: {payload['error']}")
        batch = payload.get("features") or []
        features.extend(batch)
        if not payload.get("exceededTransferLimit") or not batch:
            break
        offset += len(batch)
    return features


def feature_to_record(
    feature: dict[str, Any], *, source_type: str, source_title: str
) -> SourceRecord | None:
    attrs = feature.get("attributes") or {}
    globalid = _globalid(_pick(attrs, "globalid", "GLOBALID"))
    if not globalid:
        return None
    title = str(_pick(attrs, "ad", "planadi") or source_title).strip()
    start = _date(_pick(attrs, "askiyacikistarihi", "baslangictarihi"))
    end = _date(_pick(attrs, "askidaninistarihi", "bitistarihi"))
    event_date = start or _date(_pick(attrs, "onaytarihi")) or "1970-01-01"
    parcel_text = str(_pick(attrs, "ada_parsel") or title)
    district_text = str(
        _pick(
            attrs,
            "tapu_ilce_mahalle",
            "tapu_ılce_mahalle",
            "tapu_ılce_mahahle",
        )
        or title
    )
    plan_note = _document_url(source_type, globalid, "plannotu.pdf")
    documents = {
        "plan_note": SourceDocument(url=plan_note, media_type="application/pdf"),
        "council_decision": SourceDocument(
            url=_document_url(source_type, globalid, "mecliskarari.pdf"),
            media_type="application/pdf",
        ),
        "plan_sheet": SourceDocument(
            url=_document_url(source_type, globalid, "planpafta.pdf"),
            media_type="application/pdf",
        ),
    }
    snapshot_payload = {
        "attributes": attrs,
        "geometry": feature.get("geometry"),
        "documents": {name: doc.url for name, doc in documents.items()},
    }
    return SourceRecord(
        source_id=f"aski:{source_type}:{globalid}",
        source_kind="aski",
        source_type=source_type,
        title=title,
        event_date=event_date,
        district=district_from_text(district_text),
        neighborhood=neighborhood_from_text(district_text),
        parcels=normalize_parcels(parcel_text),
        plan_scales=plan_scales_from_text(title) or DEFAULT_SCALES[source_type],
        appeal_start_date=start,
        appeal_end_date=end,
        decision_number=str(_pick(attrs, "onay_sayisi", "onaysayisi") or "")
        or None,
        documents=documents,
        geometry=_bbox_and_centroid(feature.get("geometry")),
        raw={"attributes": attrs, "source_title": source_title},
        snapshot_hash=stable_hash(snapshot_payload),
    )


def fetch_aski_records(
    session: requests.Session | None = None,
) -> tuple[list[SourceRecord], list[str]]:
    http = session or http_session()
    records: list[SourceRecord] = []
    errors: list[str] = []
    for source in ASKI_SOURCES:
        try:
            features = query_layer(source["url"], session=http)
            logger.info("%s: %d active record(s)", source["type"], len(features))
            for feature in features:
                record = feature_to_record(
                    feature,
                    source_type=source["type"],
                    source_title=source["title"],
                )
                if record:
                    records.append(record)
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            message = f"{source['type']}: {exc}"
            errors.append(message)
            logger.warning("Source unavailable: %s", message)
    return records, errors
