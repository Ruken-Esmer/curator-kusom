"""MİMAR — Local research data store."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

GENESIS = "0" * 64


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))


def sha256(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


class Store:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            if self.path != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS docs (
                    collection TEXT NOT NULL, id TEXT NOT NULL, parent TEXT,
                    data TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY (collection, id));
                CREATE INDEX IF NOT EXISTS ix_docs_parent ON docs(collection, parent);
                CREATE TABLE IF NOT EXISTS artifacts (
                    hash TEXT PRIMARY KEY, kind TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT, action TEXT NOT NULL,
                    entity TEXT, details TEXT, prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
                """
            )

    # documents
    def put(self, collection: str, data: dict[str, Any], id: str | None = None,
            parent: str | None = None) -> dict[str, Any]:
        id = id or data.get("id") or uuid.uuid4().hex[:12]
        data = {**data, "id": id}
        ts = now_iso()
        with self._lock:
            row = self._db.execute("SELECT created_at FROM docs WHERE collection=? AND id=?",
                                   (collection, id)).fetchone()
            created = row["created_at"] if row else ts
            data.setdefault("created_at", created)
            self._db.execute(
                "INSERT OR REPLACE INTO docs(collection,id,parent,data,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                (collection, id, parent, canonical(data), created, ts))
        return data

    def put_many(self, collection: str, rows: Iterable[dict[str, Any]], parent: str | None = None) -> int:
        ts = now_iso()
        payload = []
        for r in rows:
            r = {**r, "id": r.get("id") or uuid.uuid4().hex[:12]}
            r.setdefault("created_at", ts)
            payload.append((collection, r["id"], parent, canonical(r), ts, ts))
        with self._lock:
            self._db.execute("BEGIN")
            try:
                self._db.executemany(
                    "INSERT OR REPLACE INTO docs(collection,id,parent,data,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                    payload)
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
        return len(payload)

    def get(self, collection: str, id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute("SELECT data FROM docs WHERE collection=? AND id=?", (collection, id)).fetchone()
        return json.loads(row["data"]) if row else None

    def update(self, collection: str, id: str, patch: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute("SELECT data, parent FROM docs WHERE collection=? AND id=?",
                                   (collection, id)).fetchone()
            if not row:
                raise KeyError(f"{collection}/{id} not found")
            data = {**json.loads(row["data"]), **patch}
            self._db.execute("UPDATE docs SET data=?, updated_at=? WHERE collection=? AND id=?",
                             (canonical(data), now_iso(), collection, id))
        return data

    def list(self, collection: str, parent: str | None = None, **eq: Any) -> list[dict[str, Any]]:
        with self._lock:
            if parent is None:
                rows = self._db.execute("SELECT data FROM docs WHERE collection=? ORDER BY created_at, id",
                                        (collection,)).fetchall()
            else:
                rows = self._db.execute(
                    "SELECT data FROM docs WHERE collection=? AND parent=? ORDER BY created_at, id",
                    (collection, parent)).fetchall()
        out = [json.loads(r["data"]) for r in rows]
        if eq:
            out = [d for d in out if all(d.get(k) == v for k, v in eq.items())]
        return out

    def count(self, collection: str, parent: str | None = None) -> int:
        with self._lock:
            if parent is None:
                return self._db.execute("SELECT COUNT(*) c FROM docs WHERE collection=?", (collection,)).fetchone()["c"]
            return self._db.execute("SELECT COUNT(*) c FROM docs WHERE collection=? AND parent=?",
                                    (collection, parent)).fetchone()["c"]

    def delete(self, collection: str, id: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM docs WHERE collection=? AND id=?", (collection, id))

    # immutable artifacts
    def put_artifact(self, kind: str, obj: Any) -> str:
        h = sha256(obj)
        with self._lock:
            self._db.execute("INSERT OR IGNORE INTO artifacts(hash,kind,data,created_at) VALUES (?,?,?,?)",
                             (h, kind, canonical(obj), now_iso()))
        return h

    def get_artifact(self, h: str) -> Any:
        with self._lock:
            row = self._db.execute("SELECT data FROM artifacts WHERE hash=?", (h,)).fetchone()
        if not row:
            raise KeyError(f"artifact {h} not found")
        obj = json.loads(row["data"])
        if sha256(obj) != h:
            raise ValueError(f"artifact {h} failed integrity check")
        return obj

    # audit chain
    def audit(self, actor: str | None, action: str, entity: str | None = None,
              details: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            last = self._db.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
            prev = last["hash"] if last else GENESIS
            entry = {"ts": now_iso(), "actor": actor, "action": action, "entity": entity,
                     "details": details or {}}
            h = hashlib.sha256((prev + canonical(entry)).encode()).hexdigest()
            cur = self._db.execute(
                "INSERT INTO audit(ts,actor,action,entity,details,prev_hash,hash) VALUES (?,?,?,?,?,?,?)",
                (entry["ts"], actor, action, entity, canonical(entry["details"]), prev, h))
        return {**entry, "seq": cur.lastrowid, "prev_hash": prev, "hash": h}

    def audit_log(self, limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM audit ORDER BY seq DESC LIMIT ? OFFSET ?",
                                    (limit, offset)).fetchall()
        return [{**dict(r), "details": json.loads(r["details"] or "{}")} for r in rows]

    def verify_audit(self) -> dict[str, Any]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM audit ORDER BY seq").fetchall()
        prev = GENESIS
        for r in rows:
            entry = {"ts": r["ts"], "actor": r["actor"], "action": r["action"], "entity": r["entity"],
                     "details": json.loads(r["details"] or "{}")}
            h = hashlib.sha256((prev + canonical(entry)).encode()).hexdigest()
            if r["prev_hash"] != prev or r["hash"] != h:
                return {"valid": False, "entries": len(rows), "broken_at": r["seq"]}
            prev = h
        return {"valid": True, "entries": len(rows), "head": prev}
