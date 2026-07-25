from __future__ import annotations

import json
import logging
import os
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .models import PlanningEvent, SourceRecord

logger = logging.getLogger(__name__)


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


class Repository(ABC):
    @abstractmethod
    def save_source_records(
        self, records: Iterable[SourceRecord]
    ) -> tuple[set[str], set[str]]:
        """Return (changed source ids, unchanged source ids)."""

    @abstractmethod
    def save_event(self, event: PlanningEvent) -> bool:
        """Return True when the stored representation changed."""

    @abstractmethod
    def list_events(self, published_only: bool = False) -> list[PlanningEvent]:
        pass

    @abstractmethod
    def record_run(self, run: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def mark_unseen_aski(self, seen_external_ids: set[str]) -> int:
        pass


class SQLiteRepository(Repository):
    def __init__(self, path: str | Path = "data/imarsinyal-local.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                external_id TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                found_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS source_external_idx
                ON source_snapshots(source_type, external_id);
            CREATE TABLE IF NOT EXISTS planning_events (
                event_id TEXT PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                publication_status TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS planning_event_versions (
                event_id TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (event_id, content_hash)
            );
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pipeline_state (
                state_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def save_source_records(
        self, records: Iterable[SourceRecord]
    ) -> tuple[set[str], set[str]]:
        changed: set[str] = set()
        unchanged: set[str] = set()
        for record in records:
            payload = json.dumps(asdict(record), ensure_ascii=False, sort_keys=True)
            existing = self.connection.execute(
                """
                SELECT content_hash FROM source_snapshots
                WHERE source_type = ? AND external_id = ?
                ORDER BY found_at DESC LIMIT 1
                """,
                (record.source_type, record.external_id),
            ).fetchone()
            if existing and existing["content_hash"] == record.content_hash:
                unchanged.add(record.source_id)
                self.connection.execute(
                    """
                    UPDATE source_snapshots SET active = 1
                    WHERE source_type = ? AND external_id = ?
                    """,
                    (record.source_type, record.external_id),
                )
                continue
            changed.add(record.source_id)
            self.connection.execute(
                """
                INSERT OR IGNORE INTO source_snapshots
                (snapshot_id, source_type, external_id, content_hash, found_at, active, payload)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    record.snapshot_id,
                    record.source_type,
                    record.external_id,
                    record.content_hash,
                    record.found_at,
                    payload,
                ),
            )
        self.connection.commit()
        return changed, unchanged

    def save_event(self, event: PlanningEvent) -> bool:
        payload = json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True)
        content_hash = __import__("hashlib").sha256(payload.encode()).hexdigest()
        existing = self.connection.execute(
            "SELECT content_hash FROM planning_events WHERE event_id = ?", (event.id,)
        ).fetchone()
        if existing and existing["content_hash"] == content_hash:
            return False
        self.connection.execute(
            """
            INSERT INTO planning_events
            (event_id, slug, publication_status, content_hash, updated_at, payload)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                slug = excluded.slug,
                publication_status = excluded.publication_status,
                content_hash = excluded.content_hash,
                updated_at = excluded.updated_at,
                payload = excluded.payload
            """,
            (
                event.id,
                event.slug,
                event.publication_status,
                content_hash,
                utcnow_iso(),
                payload,
            ),
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO planning_event_versions
            (event_id, content_hash, created_at, payload)
            VALUES (?, ?, ?, ?)
            """,
            (event.id, content_hash, utcnow_iso(), payload),
        )
        for evidence in event.changes.evidence:
            self.connection.execute(
                """
                INSERT OR REPLACE INTO evidence (evidence_id, event_id, payload)
                VALUES (?, ?, ?)
                """,
                (
                    f"{event.id}::{evidence.id}",
                    event.id,
                    json.dumps(asdict(evidence), ensure_ascii=False, sort_keys=True),
                ),
            )
        self.connection.commit()
        return True

    def list_events(self, published_only: bool = False) -> list[PlanningEvent]:
        query = "SELECT payload FROM planning_events"
        params: tuple[Any, ...] = ()
        if published_only:
            query += " WHERE publication_status != ?"
            params = ("withheld",)
        rows = self.connection.execute(query, params).fetchall()
        return [PlanningEvent.from_dict(json.loads(row["payload"])) for row in rows]

    def record_run(self, run: dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO pipeline_runs (run_id, started_at, payload) VALUES (?, ?, ?)",
            (
                run["run_id"],
                run["started_at"],
                json.dumps(run, ensure_ascii=False, sort_keys=True),
            ),
        )
        row = self.connection.execute(
            "SELECT payload FROM pipeline_state WHERE state_id = 'nightly'"
        ).fetchone()
        state = json.loads(row["payload"]) if row else {}
        streak = 0 if run.get("active_aski_records") else int(
            state.get("consecutive_empty_scrapes", 0)
        ) + 1
        self.connection.execute(
            """
            INSERT OR REPLACE INTO pipeline_state (state_id, payload)
            VALUES ('nightly', ?)
            """,
            (
                json.dumps(
                    {
                        "consecutive_empty_scrapes": streak,
                        "last_run_id": run["run_id"],
                        "updated_at": utcnow_iso(),
                    }
                ),
            ),
        )
        self.connection.commit()
        if streak >= 3:
            logger.error(
                "THREE_CONSECUTIVE_EMPTY_SCRAPES streak=%d run_id=%s",
                streak,
                run["run_id"],
            )

    def mark_unseen_aski(self, seen_external_ids: set[str]) -> int:
        rows = self.connection.execute(
            """
            SELECT DISTINCT external_id FROM source_snapshots
            WHERE source_type = 'abb_aski' AND active = 1
            """
        ).fetchall()
        unseen = {row["external_id"] for row in rows} - seen_external_ids
        if not unseen:
            return 0
        self.connection.executemany(
            """
            UPDATE source_snapshots SET active = 0
            WHERE source_type = 'abb_aski' AND external_id = ?
            """,
            [(external_id,) for external_id in unseen],
        )
        self.connection.commit()
        return len(unseen)


class FirestoreRepository(Repository):
    def __init__(self, project_id: str | None = None) -> None:
        import firebase_admin
        from firebase_admin import firestore

        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={"projectId": project_id} if project_id else None)
        self.db = firestore.client()

    def save_source_records(
        self, records: Iterable[SourceRecord]
    ) -> tuple[set[str], set[str]]:
        changed: set[str] = set()
        unchanged: set[str] = set()
        for record in records:
            latest_ref = self.db.collection("sources").document(
                f"{record.source_type}__{record.external_id}"
            )
            latest = latest_ref.get()
            if latest.exists and latest.to_dict().get("content_hash") == record.content_hash:
                unchanged.add(record.source_id)
                latest_ref.set({"active": True, "last_seen_at": record.found_at}, merge=True)
                continue
            changed.add(record.source_id)
            payload = asdict(record)
            batch = self.db.batch()
            batch.set(
                self.db.collection("source_snapshots").document(record.snapshot_id),
                {**payload, "active": True},
            )
            batch.set(
                latest_ref,
                {
                    "source_kind": record.source_kind,
                    "source_type": record.source_type,
                    "external_id": record.external_id,
                    "content_hash": record.content_hash,
                    "latest_snapshot_id": record.snapshot_id,
                    "active": True,
                    "last_seen_at": record.found_at,
                },
                merge=True,
            )
            batch.commit()
        return changed, unchanged

    def save_event(self, event: PlanningEvent) -> bool:
        import hashlib

        payload = event.to_dict()
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        content_hash = hashlib.sha256(serialized.encode()).hexdigest()
        ref = self.db.collection("planning_events").document(event.id)
        existing = ref.get()
        if existing.exists and existing.to_dict().get("content_hash") == content_hash:
            return False
        updated_at = utcnow_iso()
        batch = self.db.batch()
        batch.set(ref, {**payload, "content_hash": content_hash, "updated_at": updated_at})
        safe_event_id = event.id.replace("/", "_").replace(":", "__")
        batch.set(
            self.db.collection("change_versions").document(
                f"{safe_event_id}__{content_hash[:16]}"
            ),
            {
                "event_id": event.id,
                "content_hash": content_hash,
                "created_at": updated_at,
                "payload": payload,
            },
        )
        for evidence in event.changes.evidence:
            safe_evidence_id = evidence.id.replace("/", "_").replace(":", "__")
            batch.set(
                self.db.collection("evidence").document(
                    f"{safe_event_id}__{safe_evidence_id}"
                ),
                {
                    **asdict(evidence),
                    "event_id": event.id,
                    "updated_at": updated_at,
                },
            )
        batch.commit()
        return True

    def list_events(self, published_only: bool = False) -> list[PlanningEvent]:
        query = self.db.collection("planning_events")
        if published_only:
            query = query.where("publication_status", "!=", "withheld")
        return [PlanningEvent.from_dict(snapshot.to_dict()) for snapshot in query.stream()]

    def record_run(self, run: dict[str, Any]) -> None:
        self.db.collection("pipeline_runs").document(run["run_id"]).set(run)
        state_ref = self.db.collection("pipeline_state").document("nightly")
        state = state_ref.get()
        previous = state.to_dict() if state.exists else {}
        streak = 0 if run.get("active_aski_records") else int(
            previous.get("consecutive_empty_scrapes", 0)
        ) + 1
        state_ref.set(
            {
                "consecutive_empty_scrapes": streak,
                "last_run_id": run["run_id"],
                "updated_at": utcnow_iso(),
            }
        )
        if streak >= 3:
            logger.error(
                "THREE_CONSECUTIVE_EMPTY_SCRAPES streak=%d run_id=%s",
                streak,
                run["run_id"],
            )

    def mark_unseen_aski(self, seen_external_ids: set[str]) -> int:
        unseen = []
        query = self.db.collection("sources").where("source_kind", "==", "aski")
        for snapshot in query.stream():
            data = snapshot.to_dict()
            if data.get("active") and data.get("external_id") not in seen_external_ids:
                unseen.append(snapshot.reference)
        for ref in unseen:
            ref.set({"active": False, "removed_at": utcnow_iso()}, merge=True)
        return len(unseen)


def create_repository() -> Repository:
    backend = os.getenv("DATA_BACKEND", "sqlite").lower()
    if backend == "firestore":
        return FirestoreRepository(os.getenv("GOOGLE_CLOUD_PROJECT"))
    return SQLiteRepository(os.getenv("SQLITE_PATH", "data/imarsinyal-local.db"))
