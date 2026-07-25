"""
Legacy Ankara İmar Askı bulletin scraper.

Reverse-engineered from planaski.ankara.bel.tr:
  PlanBulletinQueryAllManager.Business.GetAllPlans / ShowPlanNote

Active plan polygons come from BaskentCBS ArcGIS Feature layers.
Plan Note PDFs are served from:
  {APP_ROOT}/_files/askiplanlari/{UIP|NIP|NIP25|CDP}/{globalid}/plannotu.pdf
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

APP_ROOT = "https://planaski.ankara.bel.tr/planaski"
DEFAULT_TIMEOUT = 60
PAGE_SIZE = 1000

# Mirrors PlanBulletinQueryAllManager.Configuration.AskiUrls
ASKI_SOURCES: list[dict[str, str]] = [
    {
        "type": "UIP",
        "title": "1 / 1 000 Ölçekli UİP",
        "url": "https://baskentcbs.ankara.bel.tr/server/rest/services/aktifAski/SinirUipAski/MapServer/0",
    },
    {
        "type": "NIP",
        "title": "1 / 5 000 Ölçekli NİP",
        "url": "https://baskentcbs.ankara.bel.tr/server/rest/services/aktifAski/SinirNipAski/MapServer/0",
    },
    {
        "type": "NIP25",
        "title": "1 / 25 000 Ölçekli NİP",
        "url": "https://baskentcbs.ankara.bel.tr/server/rest/services/aktifAski/SinirNip25Aski/MapServer/0",
    },
    {
        "type": "CDP",
        "title": "1 / 100 000 Ölçekli ÇDP",
        "url": "https://planaski.ankara.bel.tr/webgis/rest/services/aktifAski/aktifAskiCdp100000/MapServer/0",
    },
]

_DATE_FIELDS = (
    "onaytarihi",
    "baslangictarihi",
    "bitistarihi",
    "askiyacikistarihi",
    "askidaninistarihi",
    "buyuksehirmecliskarartarih",
    "ilcemecliskarartarih",
    "kurumonaytarihi",
)


@dataclass
class PlanRecord:
    """One active askı plan with constructed document URLs."""

    globalid: str
    source_type: str
    source_title: str
    plan_name: Optional[str]
    objectid: Optional[int] = None
    pin: Optional[str] = None
    ada_parsel: Optional[str] = None
    tapu_ilce_mahalle: Optional[str] = None
    onay_tarihi: Optional[str] = None
    aski_baslangic: Optional[str] = None
    aski_bitis: Optional[str] = None
    onay_sayisi: Optional[Any] = None
    plan_note_url: Optional[str] = None
    meclis_karari_url: Optional[str] = None
    plan_pafta_url: Optional[str] = None
    plan_note_available: Optional[bool] = None
    raw_attributes: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self, include_raw: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if not include_raw:
            data.pop("raw_attributes", None)
        return data


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "ImarASKI-Pipeline/1.0 (+https://planaski.ankara.bel.tr/planaski; research)"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{APP_ROOT}/",
        }
    )
    return session


def _ms_to_iso(value: Any) -> Optional[str]:
    """Convert ArcGIS epoch-ms (or already-string) dates to ISO-8601 UTC."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value
    try:
        ts = int(value)
        # ArcGIS sometimes returns seconds; prefer ms when large.
        if ts < 10_000_000_000:
            ts *= 1000
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return str(value)


def _normalize_globalid(globalid: str) -> str:
    """Ensure GUID is wrapped in braces, matching ShowPlanNote path segment."""
    gid = (globalid or "").strip()
    if not gid:
        return gid
    if not gid.startswith("{"):
        gid = "{" + gid
    if not gid.endswith("}"):
        gid = gid + "}"
    return gid.upper() if re.fullmatch(r"\{[0-9A-Fa-f\-]+\}", gid) else gid


def build_document_url(source_type: str, globalid: str, filename: str) -> str:
    """
    Reconstruct ShowPlanNote / ShowPlanReport / ShowPlanPafta URLs.

    Example:
      https://planaski.ankara.bel.tr/planaski/_files/askiplanlari/UIP/%7B...%7D/plannotu.pdf
    """
    gid = _normalize_globalid(globalid)
    # Braces must be percent-encoded; raw `{` returns 404 on this host.
    encoded_gid = quote(gid, safe="")
    return f"{APP_ROOT}/_files/askiplanlari/{source_type}/{encoded_gid}/{filename}"


def query_layer_features(
    layer_url: str,
    *,
    where: str = "1=1",
    out_fields: str = "*",
    return_geometry: bool = False,
    session: Optional[requests.Session] = None,
) -> list[dict[str, Any]]:
    """Paginated ArcGIS REST query against a MapServer/Feature layer."""
    http = session or _session()
    features: list[dict[str, Any]] = []
    offset = 0

    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": str(return_geometry).lower(),
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
            "orderByFields": "objectid ASC",
            "f": "pjson",
        }
        response = http.get(f"{layer_url}/query", params=params, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        payload = response.json()

        if "error" in payload:
            raise RuntimeError(
                f"ArcGIS query failed for {layer_url}: {payload['error']}"
            )

        batch = payload.get("features") or []
        features.extend(batch)

        if not payload.get("exceededTransferLimit") or not batch:
            break
        offset += len(batch)

    return features


def check_url_exists(
    url: str,
    *,
    session: Optional[requests.Session] = None,
) -> bool:
    """HEAD the PDF URL; fall back to a ranged GET if HEAD is blocked."""
    http = session or _session()
    try:
        head = http.head(url, timeout=DEFAULT_TIMEOUT, allow_redirects=True)
        if head.status_code == 200 and "pdf" in head.headers.get("Content-Type", "").lower():
            return True
        if head.status_code in (403, 405, 501):
            get = http.get(
                url,
                timeout=DEFAULT_TIMEOUT,
                allow_redirects=True,
                headers={"Range": "bytes=0-0"},
            )
            return get.status_code in (200, 206)
        return head.status_code == 200
    except requests.RequestException as exc:
        logger.debug("URL check failed for %s: %s", url, exc)
        return False


def _pick_attr(attrs: dict[str, Any], *names: str) -> Any:
    lower_map = {k.lower(): v for k, v in attrs.items()}
    for name in names:
        if name in attrs:
            return attrs[name]
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return None


def feature_to_plan(
    feature: dict[str, Any],
    *,
    source_type: str,
    source_title: str,
    verify_pdf: bool = False,
    session: Optional[requests.Session] = None,
) -> Optional[PlanRecord]:
    attrs = feature.get("attributes") or {}
    globalid = _pick_attr(attrs, "globalid", "GLOBALID")
    if not globalid:
        logger.warning("Skipping feature without globalid: objectid=%s", attrs.get("objectid"))
        return None

    gid = _normalize_globalid(str(globalid))
    plan_note_url = build_document_url(source_type, gid, "plannotu.pdf")
    meclis_url = build_document_url(source_type, gid, "mecliskarari.pdf")
    pafta_url = build_document_url(source_type, gid, "planpafta.pdf")

    note_available: Optional[bool] = None
    if verify_pdf:
        note_available = check_url_exists(plan_note_url, session=session)

    aski_start = _ms_to_iso(
        _pick_attr(attrs, "askiyacikistarihi", "baslangictarihi")
    )
    aski_end = _ms_to_iso(_pick_attr(attrs, "askidaninistarihi", "bitistarihi"))

    return PlanRecord(
        globalid=gid,
        source_type=source_type,
        source_title=source_title,
        plan_name=str(_pick_attr(attrs, "ad") or "").strip() or None,
        objectid=_pick_attr(attrs, "objectid"),
        pin=_pick_attr(attrs, "pin"),
        ada_parsel=_pick_attr(attrs, "ada_parsel"),
        tapu_ilce_mahalle=_pick_attr(
            attrs,
            "tapu_ilce_mahalle",
            "tapu_ılce_mahalle",
            "tapu_ılce_mahahle",
        ),
        onay_tarihi=_ms_to_iso(_pick_attr(attrs, "onaytarihi")),
        aski_baslangic=aski_start,
        aski_bitis=aski_end,
        onay_sayisi=_pick_attr(attrs, "onay_sayisi", "onaysayisi"),
        plan_note_url=plan_note_url,
        meclis_karari_url=meclis_url,
        plan_pafta_url=pafta_url,
        plan_note_available=note_available,
        raw_attributes={
            k: (_ms_to_iso(v) if k.lower() in _DATE_FIELDS else v)
            for k, v in attrs.items()
            if k.lower() != "se_anno_cad_data"
        },
    )


def fetch_active_plans(
    *,
    sources: Optional[Iterable[dict[str, str]]] = None,
    verify_pdf: bool = False,
    include_unavailable_services: bool = False,
    session: Optional[requests.Session] = None,
) -> list[PlanRecord]:
    """
    Fetch all currently published askı plans and attach Plan Note PDF URLs.

    This is the Python equivalent of PlanBulletinQueryAllManager.Business.GetAllPlans
    + ShowPlanNote URL construction.
    """
    http = session or _session()
    plans: list[PlanRecord] = []

    for source in sources or ASKI_SOURCES:
        source_type = source["type"]
        source_title = source["title"]
        layer_url = source["url"]
        logger.info("Querying %s (%s)", source_type, layer_url)

        try:
            features = query_layer_features(layer_url, session=http)
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            level = logging.WARNING if include_unavailable_services else logging.ERROR
            logger.log(level, "Failed to query %s: %s", source_type, exc)
            if not include_unavailable_services:
                continue
            features = []

        logger.info("  -> %d feature(s)", len(features))
        for feature in features:
            plan = feature_to_plan(
                feature,
                source_type=source_type,
                source_title=source_title,
                verify_pdf=verify_pdf,
                session=http,
            )
            if plan:
                plans.append(plan)

    plans.sort(
        key=lambda p: (
            p.aski_bitis or "",
            p.source_type,
            p.plan_name or "",
        ),
        reverse=True,
    )
    return plans


def export_plans_json(
    plans: list[PlanRecord],
    output_path: Path | str,
    *,
    include_raw: bool = False,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scraped_at": datetime.now(tz=timezone.utc).isoformat(),
        "count": len(plans),
        "plans": [p.to_dict(include_raw=include_raw) for p in plans],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Scrape Ankara İmar Askı active plans and Plan Note PDF URLs."
    )
    parser.add_argument(
        "--verify-pdf",
        action="store_true",
        help="HEAD each plannotu.pdf URL to mark plan_note_available.",
    )
    parser.add_argument(
        "--include-raw",
        action="store_true",
        help="Include full ArcGIS attributes in JSON export.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("exports/active_plans.json"),
        help="JSON export path (default: exports/active_plans.json).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    plans = fetch_active_plans(verify_pdf=args.verify_pdf)
    out = export_plans_json(plans, args.output, include_raw=args.include_raw)

    print(f"\nFetched {len(plans)} active plan(s).")
    by_type: dict[str, int] = {}
    for plan in plans:
        by_type[plan.source_type] = by_type.get(plan.source_type, 0) + 1
    for source_type, count in sorted(by_type.items()):
        print(f"  {source_type}: {count}")

    print(f"\nExported -> {out}")
    print("\nSample (up to 5):")
    for plan in plans[:5]:
        avail = ""
        if plan.plan_note_available is not None:
            avail = f" [pdf={'yes' if plan.plan_note_available else 'no'}]"
        print(f"  - [{plan.source_type}] {plan.plan_name}{avail}")
        print(f"    {plan.plan_note_url}")


if __name__ == "__main__":
    main()
