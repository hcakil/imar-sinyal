from __future__ import annotations

import hashlib
import hmac
import html
import os
import base64
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Any

import requests

from .repository import FirestoreRepository, Repository

RESEND_URL = "https://api.resend.com/emails"


def _unsubscribe_token(email: str) -> str:
    secret = os.environ["UNSUBSCRIBE_SECRET"].encode()
    normalized = email.casefold().strip()
    signature = base64.urlsafe_b64encode(
        hmac.new(secret, normalized.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")
    return base64.urlsafe_b64encode(
        f"{normalized}.{signature}".encode()
    ).decode().rstrip("=")


def _published_since(repository: Repository, since: date):
    return sorted(
        (
            event
            for event in repository.list_events(published_only=True)
            if date.fromisoformat(event.event_date) >= since
        ),
        key=lambda item: (item.impact_score, item.event_date),
        reverse=True,
    )


def render_weekly_html(
    *,
    events: list[Any],
    recipient: str,
    site_url: str,
) -> str:
    district_counts = Counter(event.district for event in events)
    high_impact = [event for event in events if event.impact_score >= 55][:5]
    on_appeal = [event for event in events if event.stage == "on_appeal"]
    ending_soon = sorted(
        (
            event
            for event in on_appeal
            if event.appeal_end_date
            and date.fromisoformat(event.appeal_end_date)
            <= date.today() + timedelta(days=7)
        ),
        key=lambda item: item.appeal_end_date or "",
    )
    district_html = "".join(
        f"<li>{html.escape(name)}: {count}</li>"
        for name, count in district_counts.most_common()
    ) or "<li>Bu hafta yeni kayıt yok.</li>"
    event_html = "".join(
        (
            "<li style='margin-bottom:12px'>"
            f"<a href='{site_url}/degisiklik/{event.slug}'>"
            f"{html.escape(event.title)}</a><br>"
            f"{html.escape(event.district)} · Etki {event.impact_score}/100"
            "</li>"
        )
        for event in high_impact
    ) or "<li>Yüksek etkili yeni olay bulunmadı.</li>"
    ending_html = "".join(
        (
            "<li>"
            f"{html.escape(event.district)} — "
            f"{html.escape(event.title)} "
            f"({html.escape(event.appeal_end_date or '')})"
            "</li>"
        )
        for event in ending_soon
    ) or "<li>Önümüzdeki 7 günde bitişi yaklaşan askı bulunmadı.</li>"
    token = _unsubscribe_token(recipient)
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:680px;margin:auto;color:#17352c">
      <p style="color:#ba5b2d;font-weight:700">İMAR SİNYALİ · HAFTALIK</p>
      <h1>Ankara'da bu hafta {len(events)} planlama olayı</h1>
      <p>Resmî kaynaklardan derlenen haftalık değişiklik özeti.</p>
      <h2>İlçelere göre</h2><ul>{district_html}</ul>
      <h2>Yüksek etkili kayıtlar</h2><ol>{event_html}</ol>
      <h2>Askı bitişi yaklaşanlar</h2><ul>{ending_html}</ul>
      <p><a href="{site_url}/degisiklikler">Tüm değişiklikleri incele</a></p>
      <hr>
      <p style="font-size:12px;color:#5f706a">
        AI analizi resmî imar belgesi değildir. Karar vermeden önce kaynak
        belgeyi ve yetkili kurumu kontrol edin.
      </p>
      <p style="font-size:12px">
        <a href="{site_url}/api/unsubscribe?token={token}">
          Abonelikten çık
        </a>
      </p>
    </div>
    """


def _active_subscribers(repository: Repository) -> list[str]:
    if not isinstance(repository, FirestoreRepository):
        test_recipient = os.getenv("NEWSLETTER_TEST_RECIPIENT")
        return [test_recipient] if test_recipient else []
    results: list[str] = []
    for snapshot in repository.db.collection("subscribers").where(
        "status", "==", "active"
    ).stream():
        email = snapshot.to_dict().get("email")
        if email:
            results.append(str(email))
    return results


def send_weekly_newsletter(
    repository: Repository,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(UTC)
    site_url = os.getenv("SITE_URL", "http://localhost:3000").rstrip("/")
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not configured")
    public_sends = os.getenv("NEWSLETTER_PUBLIC_SENDS", "false").lower() == "true"
    if public_sends:
        recipients = _active_subscribers(repository)
    else:
        test_recipient = (
            os.getenv("NEWSLETTER_TEST_RECIPIENT")
            or os.getenv("ACCOUNT_OWNER_EMAIL")
        )
        recipients = [test_recipient] if test_recipient else []
    if not recipients:
        raise RuntimeError("No newsletter recipient is configured")

    events = _published_since(repository, current.date() - timedelta(days=7))
    sent = failed = 0
    errors: list[str] = []
    for recipient in sorted(set(recipients)):
        response = requests.post(
            RESEND_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": os.getenv(
                    "NEWSLETTER_FROM",
                    "İmarSinyal Ankara <onboarding@resend.dev>",
                ),
                "to": [recipient],
                "subject": f"Ankara'da bu hafta {len(events)} imar olayı",
                "html": render_weekly_html(
                    events=events,
                    recipient=recipient,
                    site_url=site_url,
                ),
            },
            timeout=30,
        )
        if response.ok:
            sent += 1
        else:
            failed += 1
            errors.append(f"{recipient}: {response.status_code} {response.text[:200]}")
    return {
        "sent": sent,
        "failed": failed,
        "public_sends": public_sends,
        "event_count": len(events),
        "errors": errors,
    }
