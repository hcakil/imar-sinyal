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
    found: list[tuple[int, int, str]] = []
    sequence = 0

    for match in re.finditer(
        r"(\d{1,6})\s*ada\s+"
        r"((?:\d{1,6}\s*(?:,|ve)?\s*){1,200})"
        r"(?:sayılı\s+)?parseller?(?:e|i|in)?",
        normalized,
        flags=re.IGNORECASE,
    ):
        ada = str(int(match.group(1)))
        for parcel in re.findall(r"\d{1,6}", match.group(2)):
            value = f"{ada}/{int(parcel)}"
            found.append((match.start(), sequence, value))
            sequence += 1

    for match in re.finditer(
        r"(\d{1,6})\s*ada(?:sı)?\s+(\d{1,6})\s*"
        r"(?:sayılı\s+)?parsel",
        normalized,
        flags=re.IGNORECASE,
    ):
        value = f"{int(match.group(1))}/{int(match.group(2))}"
        found.append((match.start(), sequence, value))
        sequence += 1

    # İlçe ilanlarında birden fazla ada tek cümlede ve "1 ila 18" aralığıyla
    # yazılabiliyor. Her ada bölümünü bir sonraki ada/parsel sınırına kadar
    # ayrı okuyarak aralıkları ve uzun listeleri kaybetmiyoruz.
    for match in re.finditer(
        r"(\d{1,6})\s*ada\s+(.{1,900}?)"
        r"(?=(?:,\s*)?\d{1,6}\s*ada\b|"
        r"(?:sayılı\s+|numaralı\s+)?parsel(?:ler)?\w*\b|$)",
        normalized,
        flags=re.IGNORECASE,
    ):
        ada = str(int(match.group(1)))
        segment = match.group(2)
        values: list[int] = []
        for range_match in re.finditer(
            r"(\d{1,6})\s*(?:ila|-)\s*(\d{1,6})",
            segment,
            flags=re.IGNORECASE,
        ):
            start, end = map(int, range_match.groups())
            if start <= end and end - start <= 500:
                values.extend(range(start, end + 1))
        values.extend(int(value) for value in re.findall(r"\d{1,6}", segment))
        for parcel in values:
            value = f"{ada}/{parcel}"
            found.append((match.start(), sequence, value))
            sequence += 1

    shorthand_matches = list(
        re.finditer(
            r"(?<![\d/])(\d{2,6})\s*/\s*(\d{1,6})(?!\d)",
            normalized,
        )
    )
    for index, match in enumerate(shorthand_matches):
        ada_number = int(match.group(1))
        if 1900 <= ada_number <= 2100:
            # Belediye karar numaraları ve tarihler sıkça 2026/750 biçiminde
            # yazılır; bunlar ada/parsel değildir.
            continue
        suffix = normalized[match.end() : match.end() + 80]
        if re.match(
            r"\s*(?:NPP\b|(?:nolu|numaralı)\s+parselasyon\s+planı\b|"
            r"sayılı\s+karar\w*\b)",
            suffix,
            flags=re.IGNORECASE,
        ):
            # "86230/1 NPP" veya "3629/16 nolu parselasyon planı" bir plan
            # dosya numarasıdır; ada/parsel değildir.
            continue
        value = f"{ada_number}/{int(match.group(2))}"
        found.append((match.start(), sequence, value))
        sequence += 1
        # Belediye başlıkları "863/1, 2, 3, 4 ve 2150/4, 5" biçimini de
        # kullanıyor. Bir sonraki açık ada/parsel çiftine kadar yalnızca
        # bitişik virgül/"ve" parçalarını aynı adanın parselleri say.
        end = (
            shorthand_matches[index + 1].start()
            if index + 1 < len(shorthand_matches)
            else len(normalized)
        )
        remainder = normalized[match.end() : end]
        cursor = 0
        while continuation := re.match(
            r"\s*(?:,|ve)\s*(\d{1,6})(?!\d)", remainder[cursor:]
        ):
            parcel = int(continuation.group(1))
            found.append((match.start(), sequence, f"{ada_number}/{parcel}"))
            sequence += 1
            cursor += continuation.end()

    result: list[str] = []
    for _, _, value in sorted(found):
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
    def folded(value: str) -> str:
        return value.casefold().replace("\N{COMBINING DOT ABOVE}", "")

    stop_words = {
        "ili",
        "il",
        "ilçesi",
        "ilçe",
        "ilçemiz",
        "dan",
        "den",
        "nden",
        "ankara",
        "onay",
        "tarihi",
        "plan",
        "planı",
        "değişikliği",
        "parselasyon",
        "konusu",
        "mevkii",
        "uygulama",
        "imar",
        "nolu",
        "belediyesi",
        "başkanlığından",
    }
    district_names = {folded(district) for district in DISTRICTS}
    selected: list[str] = []
    for part in reversed(value.split()):
        key = folded(part.strip(" ,-/()"))
        if key in stop_words or key in district_names:
            if selected:
                break
            continue
        selected.append(part)
        if len(selected) == 3:
            break
    return " ".join(reversed(selected)).title() if selected else None


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


def _comparable_metric_value(value: str | float | int) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip().casefold()
    numeric = re.fullmatch(r"\d+(?:[.,]\d+)?", text)
    if numeric:
        return str(float(text.replace(",", ".")))
    return text


def clear_unchanged_metrics(change: ExtractedChange) -> ExtractedChange:
    """Do not publish an identical old/new value as a planning change."""
    for metric in (
        change.function,
        change.emsal,
        change.taks,
        change.yencok,
        change.density,
    ):
        if metric.old_value is None or metric.new_value is None:
            continue
        if _comparable_metric_value(metric.old_value) != _comparable_metric_value(
            metric.new_value
        ):
            continue
        metric.old_value = None
        metric.new_value = None
        metric.unit = None
        metric.evidence_ids = []
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
