from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from typing import Any

from .models import ExtractedChange, MetricChange, SourceRecord

DISTRICTS = (
    "Akyurt",
    "Altındağ",
    "Ayaş",
    "Bala",
    "Beypazarı",
    "Çamlıdere",
    "Çankaya",
    "Çubuk",
    "Elmadağ",
    "Etimesgut",
    "Evren",
    "Gölbaşı",
    "Güdül",
    "Haymana",
    "Kahramankazan",
    "Kalecik",
    "Keçiören",
    "Kızılcahamam",
    "Mamak",
    "Nallıhan",
    "Polatlı",
    "Pursaklar",
    "Sincan",
    "Şereflikoçhisar",
    "Yenimahalle",
)

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "construction_conditions": (
        "emsal",
        "kaks",
        "taks",
        "yençok",
        "yükseklik",
        "kat adedi",
        "yoğunluk",
    ),
    "land_use": (
        "fonksiyon",
        "kullanım",
        "konut",
        "ticaret",
        "sanayi",
        "sosyal tesis",
    ),
    "plan_note": ("plan notu", "plan notları", "not ilavesi", "notu değişikliği"),
    "public_infrastructure": (
        "trafo",
        "regülatör",
        "kamu hizmet",
        "belediye hizmet",
        "altyapı",
        "park alanı",
    ),
    "transportation": ("yol", "kavşak", "ulaşım", "otopark"),
    "procedural": ("karar tarih", "karar numara", "teknik düzeltme"),
}


def stable_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def slugify(value: str, max_length: int = 110) -> str:
    table = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    text = unicodedata.normalize("NFKD", value.translate(table))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (text or "imar-degisikligi")[:max_length].rstrip("-")


def normalize_parcels(text: str | None) -> list[str]:
    if not text:
        return []
    normalized = text.replace("\\", "/").replace("–", "-")
    pairs = re.findall(
        r"(?P<ada>\d{1,6})\s*(?:ada)?\s*[/,\- ]\s*(?P<parsel>\d{1,6})\s*(?:parsel)?",
        normalized,
        flags=re.IGNORECASE,
    )
    result: list[str] = []
    for ada, parcel in pairs:
        value = f"{int(ada)}/{int(parcel)}"
        if value not in result:
            result.append(value)

    if result:
        return result

    ada_match = re.search(r"(\d{1,6})\s*ada", normalized, flags=re.IGNORECASE)
    if not ada_match:
        return []
    ada = str(int(ada_match.group(1)))
    tail = normalized[ada_match.end() :]
    parcel_match = re.search(
        r"([\d,\s]+)\s*parsel", tail, flags=re.IGNORECASE
    )
    if parcel_match:
        for parcel in re.findall(r"\d+", parcel_match.group(1)):
            value = f"{ada}/{int(parcel)}"
            if value not in result:
                result.append(value)
    return result


def district_from_text(text: str) -> str | None:
    folded = text.casefold()
    for district in DISTRICTS:
        if district.casefold() in folded:
            return district
    return None


def neighborhood_from_text(text: str) -> str | None:
    match = re.search(
        r"([A-ZÇĞİÖŞÜa-zçğıöşü][A-ZÇĞİÖŞÜa-zçğıöşü\s()/-]{1,50}?)\s+Mah(?:allesi|\.| )",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    value = re.sub(r"\s+", " ", match.group(1)).strip(" ,-")
    stop_words = {"ilçesi", "ilçe", "ankara"}
    parts = [part for part in value.split() if part.casefold() not in stop_words]
    return " ".join(parts[-3:]).title() if parts else None


def plan_scales_from_text(text: str) -> list[str]:
    found: list[str] = []
    for raw in re.findall(r"1\s*/\s*(1\s*000|5\s*000|25\s*000|100\s*000)", text):
        scale = "1/" + raw.replace(" ", "")
        if scale not in found:
            found.append(scale)
    return found


def categories_from_text(text: str) -> list[str]:
    folded = text.casefold()
    categories = [
        category
        for category, keywords in CATEGORY_KEYWORDS.items()
        if any(keyword.casefold() in folded for keyword in keywords)
    ]
    return categories or ["procedural"]


def normalize_metric_kind(change: ExtractedChange) -> ExtractedChange:
    """Prevent density/TAKS values from leaking into the emsal field."""
    emsal_unit = (change.emsal.unit or "").casefold()
    for attr in ("old_value", "new_value"):
        value = getattr(change.emsal, attr)
        if value is None:
            continue
        text = str(value).casefold()
        if (
            "kişi/ha" in text
            or "kisi/ha" in text
            or "kişi" in emsal_unit
            or "kisi" in emsal_unit
        ):
            setattr(change.density, attr, value)
            change.density.unit = "kişi/ha"
            change.density.evidence_ids = list(change.emsal.evidence_ids)
            setattr(change.emsal, attr, None)
        elif "taks" in text or "taks" in emsal_unit:
            number = re.search(r"\d+(?:[.,]\d+)?", text)
            setattr(change.taks, attr, number.group(0).replace(",", ".") if number else value)
            change.taks.evidence_ids = list(change.emsal.evidence_ids)
            setattr(change.emsal, attr, None)

    if change.emsal.old_value is None and change.emsal.new_value is None:
        change.emsal.unit = None
        change.emsal.evidence_ids = []
    return change


def verified_fields_have_evidence(change: ExtractedChange) -> bool:
    evidence_ids = {item.id for item in change.evidence}
    for metric in (
        change.function,
        change.emsal,
        change.taks,
        change.yencok,
        change.density,
    ):
        if metric.old_value is None and metric.new_value is None:
            continue
        if not metric.evidence_ids or not set(metric.evidence_ids).issubset(evidence_ids):
            return False
    return bool(evidence_ids)


def impact_score(change: ExtractedChange) -> int:
    score = 10
    if change.emsal.old_value is not None or change.emsal.new_value is not None:
        score += 30
    if change.taks.old_value is not None or change.taks.new_value is not None:
        score += 20
    if change.yencok.old_value is not None or change.yencok.new_value is not None:
        score += 20
    if change.function.old_value is not None or change.function.new_value is not None:
        score += 25
    if change.density.old_value is not None or change.density.new_value is not None:
        score += 15
    if "plan_note" in change.categories:
        score += 10
    if "public_infrastructure" in change.categories:
        score -= 30
    if change.categories == ["procedural"]:
        score -= 15
    return max(0, min(100, score))


def source_stage(record: SourceRecord, today: date | None = None) -> str:
    if record.source_kind == "council":
        return "council_approved"
    current = today or date.today()
    if record.appeal_end_date:
        end = date.fromisoformat(record.appeal_end_date)
        return "on_appeal" if end >= current else "appeal_ended"
    return "on_appeal"


def empty_change_from_record(record: SourceRecord) -> ExtractedChange:
    text = f"{record.title} {record.raw.get('summary', '')}"
    return ExtractedChange(
        categories=categories_from_text(text),
        summary=record.raw.get("summary") or record.title,
    )
