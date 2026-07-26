from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ..models import SourceDocument, SourceRecord
from ..normalization import (
    neighborhood_from_text,
    normalize_parcels,
    plan_scales_from_text,
    stable_hash,
)
from .http import http_session

logger = logging.getLogger(__name__)

POLATLI_LIST_URL = "https://www.polatli.bel.tr/imarplanlari"
KECIOREN_LIST_URL = (
    "https://www.kecioren.bel.tr/imar-parselasyon-duyurularimiz.html"
)
TIMEOUT = 60
MAX_KECIOREN_PAGES = 20

PLAN_TERMS = (
    "imar plan",
    "uygulama imar",
    "nazım imar",
    "parselasyon plan",
    "plan değişik",
    "planı değişik",
)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _tr_date(value: str) -> date:
    return datetime.strptime(value.replace("/", "."), "%d.%m.%Y").date()


def _appeal_dates(text: str) -> tuple[str | None, str | None]:
    range_match = re.search(
        r"(\d{1,2}[./]\d{1,2}[./]\d{4})\s*[-–]\s*"
        r"(\d{1,2}[./]\d{1,2}[./]\d{4})",
        text,
    )
    if range_match:
        return (
            _tr_date(range_match.group(1)).isoformat(),
            _tr_date(range_match.group(2)).isoformat(),
        )

    start_match = re.search(
        r"(\d{1,2}[./]\d{1,2}[./]\d{4})\s+tarihinden itibaren\s+"
        r"(?:bir|1|30)\s*(ay|gün)",
        text,
        flags=re.IGNORECASE,
    )
    if start_match:
        start = _tr_date(start_match.group(1))
        # Belediye metinleri bu ilanları "1 ay" veya "30 gün" diye yayımlıyor.
        # Kaynak özel bir bitiş tarihi vermediğinde ortak 30 günlük süreyi
        # kullanıyoruz; ayrıntı sayfası yine resmî kaynak olarak gösterilir.
        return start.isoformat(), (start + timedelta(days=30)).isoformat()

    return None, None


def _latest_date(text: str) -> str | None:
    values: list[date] = []
    for raw in re.findall(r"\d{1,2}[./]\d{1,2}[./]\d{4}", text):
        try:
            values.append(_tr_date(raw))
        except ValueError:
            continue
    return max(values).isoformat() if values else None


def _decision_number(text: str) -> str | None:
    matches = re.findall(
        r"(?:Büyükşehir Belediye (?:Meclisi|Encümeni)[^,.]{0,90}?"
        r"(?:tarih ve|tarihli)\s*)(\d+(?:/\d+)?)\s*sayılı",
        text,
        flags=re.IGNORECASE,
    )
    return matches[-1] if matches else None


def _media_type(url: str) -> str:
    path = urlparse(url).path.casefold()
    if path.endswith(".pdf"):
        return "application/pdf"
    if path.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if path.endswith(".png"):
        return "image/png"
    return "text/html"


def _title_from_detail(
    soup: BeautifulSoup, fallback: str, *, selector: str
) -> str:
    heading = soup.select_one(selector)
    if heading:
        value = (
            heading.get("content", "")
            if heading.name == "meta"
            else heading.get_text(" ", strip=True)
        )
        value = _clean(str(value)).split(" | ")[0]
        if value:
            return value
    if soup.title:
        value = _clean(soup.title.get_text(" ", strip=True)).split(" | ")[0]
        if value:
            return value
    return fallback.replace("Devamını Oku", "").strip(" .")


def _record(
    *,
    municipality: str,
    source_type: str,
    external_id: str,
    title: str,
    detail_url: str,
    detail_text: str,
    attachment_url: str | None,
) -> SourceRecord:
    start, end = _appeal_dates(detail_text)
    documents = {
        "source_page": SourceDocument(
            url=detail_url,
            media_type="text/html",
        )
    }
    if attachment_url:
        documents["plan_note"] = SourceDocument(
            url=attachment_url,
            media_type=_media_type(attachment_url),
        )
    else:
        documents["primary"] = documents["source_page"]

    payload = {
        "title": title,
        "detail_text": detail_text,
        "documents": {name: item.url for name, item in documents.items()},
        "appeal_start_date": start,
        "appeal_end_date": end,
    }
    return SourceRecord(
        source_id=f"aski:{source_type}:{external_id}",
        source_kind="aski",
        source_type=source_type,
        title=title,
        event_date=start or _latest_date(detail_text) or date.today().isoformat(),
        district=municipality,
        neighborhood=neighborhood_from_text(detail_text),
        parcels=normalize_parcels(f"{title} {detail_text}"),
        plan_scales=plan_scales_from_text(f"{title} {detail_text}"),
        appeal_start_date=start,
        appeal_end_date=end,
        decision_number=_decision_number(detail_text),
        documents=documents,
        raw={
            "summary": detail_text,
            "source_page": detail_url,
            "municipality": municipality,
        },
        snapshot_hash=stable_hash(payload),
    )


def parse_polatli_detail(
    html: str, *, detail_url: str, fallback_title: str
) -> SourceRecord:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("div.post-detail")
    if not content:
        raise ValueError("Polatlı detail content was not found")
    title = _title_from_detail(
        soup,
        fallback_title,
        selector="meta[property='og:title']",
    )
    detail_text = _clean(content.get_text(" ", strip=True))
    attachment = next(
        (
            urljoin(detail_url, link.get("href", ""))
            for link in content.select("a[href]")
            if link.get("href", "").casefold().endswith(".pdf")
        ),
        None,
    )
    external_id = detail_url.rstrip("/").rsplit("/", 1)[-1]
    return _record(
        municipality="Polatlı",
        source_type="POLATLI_ASKI",
        external_id=external_id,
        title=title,
        detail_url=detail_url,
        detail_text=detail_text,
        attachment_url=attachment,
    )


def parse_kecioren_detail(
    html: str, *, detail_url: str, fallback_title: str
) -> SourceRecord:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("div.etext")
    if not content:
        raise ValueError("Keçiören detail content was not found")
    title = _title_from_detail(
        soup,
        fallback_title,
        selector="section.subheader h2",
    )
    detail_text = _clean(content.get_text(" ", strip=True))
    attachment = next(
        (
            urljoin(detail_url, link.get("href", ""))
            for link in content.select("a[href]")
            if _media_type(urljoin(detail_url, link.get("href", ""))).startswith(
                ("application/pdf", "image/")
            )
        ),
        None,
    )
    match = re.search(r"-(\d+)-duyuru\.html", detail_url)
    external_id = match.group(1) if match else stable_hash(detail_url)[:16]
    return _record(
        municipality="Keçiören",
        source_type="KECIOREN_ASKI",
        external_id=external_id,
        title=title,
        detail_url=detail_url,
        detail_text=detail_text,
        attachment_url=attachment,
    )


def fetch_polatli_records(
    session: requests.Session | None = None,
) -> tuple[list[SourceRecord], list[str]]:
    http = session or http_session()
    records: list[SourceRecord] = []
    errors: list[str] = []
    try:
        response = http.get(POLATLI_LIST_URL, timeout=TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        candidates = [
            (
                _clean(link.get_text(" ", strip=True)),
                urljoin(POLATLI_LIST_URL, link.get("href", "")),
            )
            for link in soup.select("a[href*='/imarplani/']")
        ]
    except requests.RequestException as exc:
        return [], [f"POLATLI_ASKI: {exc}"]

    seen: set[str] = set()
    for fallback_title, detail_url in candidates:
        if detail_url in seen:
            continue
        seen.add(detail_url)
        try:
            response = http.get(detail_url, timeout=TIMEOUT)
            response.raise_for_status()
            records.append(
                parse_polatli_detail(
                    response.text,
                    detail_url=detail_url,
                    fallback_title=fallback_title,
                )
            )
        except (requests.RequestException, ValueError) as exc:
            errors.append(f"POLATLI_ASKI {detail_url}: {exc}")
    logger.info("POLATLI_ASKI: %d record(s)", len(records))
    return records, errors


def _is_plan_candidate(text: str) -> bool:
    folded = text.casefold()
    return any(term in folded for term in PLAN_TERMS)


def fetch_kecioren_records(
    session: requests.Session | None = None,
) -> tuple[list[SourceRecord], list[str]]:
    http = session or http_session()
    records: list[SourceRecord] = []
    errors: list[str] = []
    seen: set[str] = set()
    from_date = date.fromisoformat(
        os.getenv("MUNICIPAL_FROM_DATE", "2026-01-01")
    )
    page_limit = min(
        int(os.getenv("KECIOREN_MAX_PAGES", str(MAX_KECIOREN_PAGES))),
        MAX_KECIOREN_PAGES,
    )
    for page in range(1, page_limit + 1):
        try:
            response = http.get(
                KECIOREN_LIST_URL,
                params={} if page == 1 else {"page": page},
                timeout=TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            errors.append(f"KECIOREN_ASKI page={page}: {exc}")
            break
        soup = BeautifulSoup(response.text, "html.parser")
        boxes = soup.select("div.news-box")
        page_dates: list[date] = []
        for box in boxes:
            link = box.select_one("h6 a[href*='-duyuru.html']")
            if not link:
                continue
            title = _clean(link.get_text(" ", strip=True))
            card_text = _clean(box.get_text(" ", strip=True))
            if not _is_plan_candidate(f"{title} {card_text}"):
                continue
            detail_url = urljoin(KECIOREN_LIST_URL, link.get("href", ""))
            if detail_url in seen:
                continue
            seen.add(detail_url)
            try:
                detail_response = http.get(detail_url, timeout=TIMEOUT)
                detail_response.raise_for_status()
                record = parse_kecioren_detail(
                    detail_response.text,
                    detail_url=detail_url,
                    fallback_title=title,
                )
                event_date = date.fromisoformat(record.event_date)
                page_dates.append(event_date)
                if event_date >= from_date:
                    records.append(record)
            except (requests.RequestException, ValueError) as exc:
                errors.append(f"KECIOREN_ASKI {detail_url}: {exc}")
        if page > 1 and not boxes:
            break
        if page_dates and max(page_dates) < from_date:
            break
    logger.info("KECIOREN_ASKI: %d record(s)", len(records))
    return records, errors


def fetch_municipal_aski_records(
    session: requests.Session | None = None,
) -> tuple[list[SourceRecord], list[str]]:
    http = session or http_session()
    records: list[SourceRecord] = []
    errors: list[str] = []
    for fetcher in (fetch_polatli_records, fetch_kecioren_records):
        source_records, source_errors = fetcher(http)
        records.extend(source_records)
        errors.extend(source_errors)
    return records, errors
