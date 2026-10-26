from __future__ import annotations

import hashlib
import sqlite3
import zlib
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit, urlunsplit

import requests


@dataclass(frozen=True)
class CachedSourcePage:
    normalized_url: str
    original_url: str
    effective_url: str
    html: str
    content_sha256: str
    etag: str
    last_modified: str
    fetched_at: str
    checked_at: str
    status_code: int


def normalize_source_url(url: str) -> str:
    """Normalize URL components that do not identify a different resource."""
    parts = urlsplit(str(url or "").strip())
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            parts.path or "/",
            parts.query,
            "",
        )
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _header_value(headers: Any, expected_name: str) -> str:
    if not hasattr(headers, "items"):
        return ""
    for name, value in headers.items():
        if str(name).casefold() == expected_name.casefold():
            return str(value or "").strip()
    return ""


class PersistentSourcePageRepository:
    """SQLite-backed HTML cache; each operation owns and closes its connection."""

    def __init__(self, db_path: str | Path) -> None:
        value = str(db_path or "").strip()
        if not value or value == ":memory:":
            raise ValueError("La caché persistente requiere una ruta SQLite en disco.")
        self.db_path = value
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _ensure_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS source_page_cache (
                    normalized_url TEXT PRIMARY KEY,
                    original_url TEXT NOT NULL,
                    effective_url TEXT NOT NULL,
                    html_zlib BLOB NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    etag TEXT NOT NULL DEFAULT '',
                    last_modified TEXT NOT NULL DEFAULT '',
                    fetched_at TEXT NOT NULL,
                    checked_at TEXT NOT NULL,
                    status_code INTEGER NOT NULL DEFAULT 200
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_source_page_cache_checked_at "
                "ON source_page_cache(checked_at)"
            )
            connection.commit()
        finally:
            connection.close()

    def get(self, url: str) -> CachedSourcePage | None:
        key = normalize_source_url(url)
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT normalized_url, original_url, effective_url, html_zlib,
                       content_sha256, etag, last_modified, fetched_at,
                       checked_at, status_code
                FROM source_page_cache
                WHERE normalized_url = ?
                """,
                (key,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        try:
            html = zlib.decompress(bytes(row["html_zlib"])).decode("utf-8")
        except (TypeError, ValueError, UnicodeDecodeError, zlib.error):
            return None
        return CachedSourcePage(
            normalized_url=str(row["normalized_url"]),
            original_url=str(row["original_url"]),
            effective_url=str(row["effective_url"]),
            html=html,
            content_sha256=str(row["content_sha256"]),
            etag=str(row["etag"] or ""),
            last_modified=str(row["last_modified"] or ""),
            fetched_at=str(row["fetched_at"]),
            checked_at=str(row["checked_at"]),
            status_code=int(row["status_code"] or 200),
        )

    def make_entry(self, url: str, html: str, response: Any) -> CachedSourcePage:
        """Build a cache entry without opening a SQLite write transaction."""
        normalized_url = normalize_source_url(url)
        original_url = str(url).strip()
        response_url = str(getattr(response, "url", "") or original_url)
        effective_url = normalize_source_url(response_url)
        headers = getattr(response, "headers", {}) or {}
        now = _utc_now()
        payload = html.encode("utf-8")
        return CachedSourcePage(
            normalized_url=normalized_url,
            original_url=original_url,
            effective_url=effective_url,
            html=html,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            etag=_header_value(headers, "ETag"),
            last_modified=_header_value(headers, "Last-Modified"),
            fetched_at=now,
            checked_at=now,
            status_code=int(getattr(response, "status_code", 200) or 200),
        )

    def save_entry(self, entry: CachedSourcePage) -> None:
        """Persist an entry in a short transaction owned by this repository."""
        compressed = zlib.compress(entry.html.encode("utf-8"), level=6)
        connection = self._connect()
        try:
            connection.execute(
                """
                INSERT INTO source_page_cache (
                    normalized_url, original_url, effective_url, html_zlib,
                    content_sha256, etag, last_modified, fetched_at,
                    checked_at, status_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(normalized_url) DO UPDATE SET
                    original_url=excluded.original_url,
                    effective_url=excluded.effective_url,
                    html_zlib=excluded.html_zlib,
                    content_sha256=excluded.content_sha256,
                    etag=excluded.etag,
                    last_modified=excluded.last_modified,
                    fetched_at=excluded.fetched_at,
                    checked_at=excluded.checked_at,
                    status_code=excluded.status_code
                """,
                (
                    entry.normalized_url,
                    entry.original_url,
                    entry.effective_url,
                    sqlite3.Binary(compressed),
                    entry.content_sha256,
                    entry.etag,
                    entry.last_modified,
                    entry.fetched_at,
                    entry.checked_at,
                    entry.status_code,
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def store(self, url: str, html: str, response: Any) -> CachedSourcePage:
        entry = self.make_entry(url, html, response)
        self.save_entry(entry)
        saved = self.get(entry.normalized_url)
        if saved is None:
            raise RuntimeError("No se pudo verificar la página guardada en caché.")
        return saved

    def mark_checked(self, url: str, response_headers: Any = None) -> None:
        key = normalize_source_url(url)
        etag = _header_value(response_headers or {}, "ETag")
        last_modified = _header_value(response_headers or {}, "Last-Modified")
        connection = self._connect()
        try:
            connection.execute(
                """
                UPDATE source_page_cache
                SET checked_at = ?,
                    etag = CASE WHEN ? <> '' THEN ? ELSE etag END,
                    last_modified = CASE WHEN ? <> '' THEN ? ELSE last_modified END
                WHERE normalized_url = ?
                """,
                (_utc_now(), etag, etag, last_modified, last_modified, key),
            )
            connection.commit()
        finally:
            connection.close()


class PersistentSourcePageCache:
    """Persistent cache for product-detail HTML with conditional validation."""

    def __init__(
        self,
        repository: PersistentSourcePageRepository,
        *,
        ttl_seconds: int = 86400,
        defer_writes: bool = False,
    ) -> None:
        if int(ttl_seconds) < 0:
            raise ValueError("ttl_seconds no puede ser negativo.")
        self.repository = repository
        self.ttl_seconds = int(ttl_seconds)
        self.defer_writes = bool(defer_writes)
        self._pending_lock = Lock()
        self._pending_entries: dict[str, CachedSourcePage] = {}
        self._metrics_lock = Lock()
        self._metrics: dict[str, int] = {
            "fresh_hits": 0,
            "network_validations": 0,
            "not_modified_304": 0,
            "updated_200": 0,
            "stale_fallbacks": 0,
            "empty_response_fallbacks": 0,
            "request_errors": 0,
        }

    def _get_entry(self, normalized_url: str) -> CachedSourcePage | None:
        if self.defer_writes:
            with self._pending_lock:
                pending = self._pending_entries.get(normalized_url)
            if pending is not None:
                return pending
        return self.repository.get(normalized_url)

    def _queue_entry(self, entry: CachedSourcePage) -> None:
        with self._pending_lock:
            self._pending_entries[entry.normalized_url] = entry

    def flush_pending(self) -> int:
        """Write deferred cache entries after the catalog transaction finishes."""
        if not self.defer_writes:
            return 0
        with self._pending_lock:
            pending = list(self._pending_entries.values())
            self._pending_entries.clear()
        for index, entry in enumerate(pending):
            try:
                self.repository.save_entry(entry)
            except Exception:
                with self._pending_lock:
                    for remaining in pending[index:]:
                        self._pending_entries.setdefault(
                            remaining.normalized_url,
                            remaining,
                        )
                raise
        return len(pending)

    @staticmethod
    def is_cacheable_url(url: str) -> bool:
        return "/producto/" in urlsplit(str(url or "")).path.casefold()

    def _increment(self, name: str) -> None:
        with self._metrics_lock:
            self._metrics[name] = self._metrics.get(name, 0) + 1

    def get_metrics(self) -> dict[str, int]:
        with self._metrics_lock:
            return dict(self._metrics)

    def reset_metrics(self) -> None:
        with self._metrics_lock:
            for key in self._metrics:
                self._metrics[key] = 0

    def _is_fresh(self, entry: CachedSourcePage) -> bool:
        if self.ttl_seconds <= 0:
            return False
        try:
            checked = datetime.fromisoformat(
                entry.checked_at.replace("Z", "+00:00")
            )
        except ValueError:
            return False
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        age = (
            datetime.now(timezone.utc) - checked.astimezone(timezone.utc)
        ).total_seconds()
        return 0 <= age < self.ttl_seconds

    def _fresh_cached_html(
        self,
        entry: CachedSourcePage | None,
        force: bool,
    ) -> str | None:
        if entry is None or force or not self._is_fresh(entry):
            return None
        self._increment("fresh_hits")
        return entry.html

    @staticmethod
    def _conditional_headers(
        entry: CachedSourcePage | None,
        normalized_url: str,
    ) -> dict[str, str]:
        headers: dict[str, str] = {}
        if entry is None or entry.effective_url != normalized_url:
            return headers
        if entry.etag:
            headers["If-None-Match"] = entry.etag
        if entry.last_modified:
            headers["If-Modified-Since"] = entry.last_modified
        return headers

    def get_html(
        self,
        url: str,
        fetcher: Callable[[Mapping[str, str]], Any],
        *,
        force: bool = False,
        allow_stale_fallback: bool = True,
    ) -> str:
        normalized_url = normalize_source_url(url)
        entry = self._get_entry(normalized_url)
        cached_html = self._fresh_cached_html(entry, force)
        if cached_html is not None:
            return cached_html
        request_headers = self._conditional_headers(entry, normalized_url)
        self._increment("network_validations")
        try:
            response = fetcher(request_headers)
        except requests.exceptions.RequestException:
            self._increment("request_errors")
            if entry is not None and allow_stale_fallback:
                self._increment("stale_fallbacks")
                return entry.html
            raise
        return self._process_response(
            url,
            normalized_url,
            entry,
            response,
            allow_stale_fallback=allow_stale_fallback,
        )

    def _process_response(
        self,
        url: str,
        normalized_url: str,
        entry: CachedSourcePage | None,
        response: Any,
        *,
        allow_stale_fallback: bool = True,
    ) -> str:
        status_code = int(getattr(response, "status_code", 200) or 200)
        response_headers = getattr(response, "headers", {}) or {}
        if status_code == 304 and entry is not None:
            if self.defer_writes:
                checked_entry = replace(
                    entry,
                    etag=_header_value(response_headers, "ETag") or entry.etag,
                    last_modified=(
                        _header_value(response_headers, "Last-Modified")
                        or entry.last_modified
                    ),
                    checked_at=_utc_now(),
                )
                self._queue_entry(checked_entry)
            else:
                self.repository.mark_checked(normalized_url, response_headers)
            self._increment("not_modified_304")
            return entry.html
        if status_code >= 400:
            return self._handle_http_error(
                url,
                entry,
                response,
                allow_stale_fallback=allow_stale_fallback,
            )
        html_value = getattr(response, "text", "")
        if not isinstance(html_value, str):
            html_value = str(html_value or "")
        if not html_value.strip():
            if entry is not None:
                self._increment("empty_response_fallbacks")
                return entry.html
            return html_value
        if self.defer_writes:
            self._queue_entry(self.repository.make_entry(url, html_value, response))
        else:
            self.repository.store(url, html_value, response)
        self._increment("updated_200")
        return html_value

    def _handle_http_error(
        self,
        url: str,
        entry: CachedSourcePage | None,
        response: Any,
        *,
        allow_stale_fallback: bool = True,
    ) -> str:
        raise_for_status = getattr(response, "raise_for_status", None)
        if callable(raise_for_status):
            try:
                raise_for_status()
            except requests.exceptions.RequestException:
                self._increment("request_errors")
                if entry is not None and allow_stale_fallback:
                    self._increment("stale_fallbacks")
                    return entry.html
                raise
        if entry is not None and allow_stale_fallback:
            self._increment("stale_fallbacks")
            return entry.html
        raise requests.exceptions.HTTPError(f"HTTP error al consultar {url}")
