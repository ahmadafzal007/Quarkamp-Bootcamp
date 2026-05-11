"""
MongoDB-backed UI chat transcripts (same shape as frontend message array).
No auth: session_id is an opaque UUID from the browser.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from backend.config import CHAT_COLL, MONGO_DB, MONGO_URI

logger = logging.getLogger("chat_store")

_MAX_MESSAGES = 500
_MAX_DOCUMENT_BYTES = 14 * 1024 * 1024  # leave headroom below 16MB BSON limit


_client: MongoClient | None = None
_indexes_ensured = False


def _collection() -> Collection | None:
    global _client, _indexes_ensured
    if not MONGO_URI:
        return None
    if _client is None:
        try:
            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
            _client.admin.command("ping")
            logger.info("MongoDB connected (db=%s, coll=%s)", MONGO_DB, CHAT_COLL)
        except PyMongoError as exc:
            logger.warning("MongoDB unavailable: %s", exc)
            _client = None
            return None
    db = _client[MONGO_DB]
    col = db[CHAT_COLL]
    if not _indexes_ensured:
        try:
            col.create_index("session_id", unique=True)
        except PyMongoError as exc:
            logger.warning("Mongo index creation: %s", exc)
        _indexes_ensured = True
    return col


def is_configured() -> bool:
    return bool(MONGO_URI)


def ping_ok() -> bool:
    """True if URI is set and server responds."""
    col = _collection()
    return col is not None


def valid_session_id(s: str) -> bool:
    if not s or len(s) > 48:
        return False
    try:
        uuid.UUID(s)
        return True
    except ValueError:
        return False


def _trim(messages: list[dict]) -> list[dict]:
    out = messages[-_MAX_MESSAGES:]
    # Drop from the front until JSON fits
    while out:
        blob = json.dumps(out, separators=(",", ":"), ensure_ascii=False)
        if len(blob.encode("utf-8")) <= _MAX_DOCUMENT_BYTES:
            break
        out = out[1:]
    return out


def load_messages(session_id: str) -> list[dict]:
    """Return stored messages or []."""
    col = _collection()
    if col is None:
        return []
    try:
        doc = col.find_one({"session_id": session_id})
        if not doc:
            return []
        msgs = doc.get("messages")
        return msgs if isinstance(msgs, list) else []
    except PyMongoError as exc:
        logger.warning("Mongo load chat failed: %s", exc)
        return []


def delete_messages(session_id: str) -> bool:
    """Delete a session document from Mongo. Returns True on success."""
    col = _collection()
    if col is None:
        return False
    try:
        col.delete_one({"session_id": session_id})
        return True
    except PyMongoError as exc:
        logger.warning("Mongo delete chat failed: %s", exc)
        return False


def save_messages(session_id: str, messages: list[dict]) -> bool:
    """Upsert transcript. messages must be JSON-serializable dicts."""
    col = _collection()
    if col is None:
        return False
    if not isinstance(messages, list):
        return False
    clean: list[dict] = [m for m in messages if isinstance(m, dict)]
    trimmed = _trim(clean)
    try:
        col.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "messages": trimmed,
                    "updated_at": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
        return True
    except PyMongoError as exc:
        logger.warning("Mongo save chat failed: %s", exc)
        return False
