from __future__ import annotations

import pytest
import requests

from services.scraping.source_page_cache import (
    PersistentSourcePageCache,
    PersistentSourcePageRepository,
)


class FakeResponse:
    def __init__(
        self,
        text: str,
        status_code: int = 200,
        headers=None,
        url: str = "",
    ) -> None:
        self.text = text
        self.status_code = status_code
        self.headers = dict(headers or {})
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


def test_fresh_page_cache_skips_network_request(tmp_path):
    repository = PersistentSourcePageRepository(tmp_path / "catalog.db")
    cache = PersistentSourcePageCache(repository, ttl_seconds=3600)
    url = "https://example.test/producto/item/"
    calls = []

    def fetcher(headers):
        calls.append(dict(headers))
        return FakeResponse(
            "<html>primera versión</html>",
            headers={"ETag": '"v1"'},
            url=url,
        )

    expected_html = "<html>primera versión</html>"
    assert cache.get_html(url, fetcher) == expected_html
    assert cache.get_html(url, fetcher) == expected_html
    assert len(calls) == 1
    assert cache.get_metrics()["fresh_hits"] == 1


def test_304_reuses_html_and_updates_checked_time(tmp_path):
    repository = PersistentSourcePageRepository(tmp_path / "catalog.db")
    cache = PersistentSourcePageCache(repository, ttl_seconds=0)
    url = "https://example.test/producto/item/"
    expected_html = "<html>vigente</html>"

    assert cache.get_html(
        url,
        lambda headers: FakeResponse(
            expected_html,
            headers={"ETag": '"v1"'},
            url=url,
        ),
    ) == expected_html

    sent_headers = []

    def not_modified(headers):
        sent_headers.append(dict(headers))
        return FakeResponse(
            "",
            status_code=304,
            headers={"ETag": '"v1"'},
            url=url,
        )

    assert cache.get_html(url, not_modified) == expected_html
    assert sent_headers == [{"If-None-Match": '"v1"'}]
    assert cache.get_metrics()["not_modified_304"] == 1


def test_200_replaces_cached_html_when_source_changes(tmp_path):
    repository = PersistentSourcePageRepository(tmp_path / "catalog.db")
    cache = PersistentSourcePageCache(repository, ttl_seconds=0)
    url = "https://example.test/producto/item/"
    cache.get_html(
        url,
        lambda headers: FakeResponse(
            "<html>v1</html>",
            headers={"ETag": '"v1"'},
            url=url,
        ),
    )

    expected_html = "<html>v2</html>"
    assert cache.get_html(
        url,
        lambda headers: FakeResponse(
            expected_html,
            headers={"ETag": '"v2"'},
            url=url,
        ),
    ) == expected_html
    saved = repository.get(url)
    assert saved is not None
    assert saved.html == expected_html
    assert saved.etag == '"v2"'


def test_failed_revalidation_uses_last_good_html(tmp_path):
    repository = PersistentSourcePageRepository(tmp_path / "catalog.db")
    cache = PersistentSourcePageCache(repository, ttl_seconds=0)
    url = "https://example.test/producto/item/"
    expected_html = "<html>última versión válida</html>"
    cache.get_html(
        url,
        lambda headers: FakeResponse(expected_html, url=url),
    )

    def failed_fetch(headers):
        raise requests.exceptions.Timeout("fallo temporal")

    assert cache.get_html(url, failed_fetch) == expected_html
    assert cache.get_metrics()["stale_fallbacks"] == 1


def test_only_product_detail_urls_are_cacheable():
    assert PersistentSourcePageCache.is_cacheable_url(
        "https://example.test/producto/item/"
    )
    assert not PersistentSourcePageCache.is_cacheable_url(
        "https://example.test/categoria/item/"
    )


def test_deferred_cache_writes_do_not_conflict_with_catalog_transaction(tmp_path):
    import sqlite3

    database_path = tmp_path / "catalog.db"
    catalog_connection = sqlite3.connect(database_path, timeout=2)
    catalog_connection.execute("PRAGMA journal_mode=WAL")
    catalog_connection.execute(
        "CREATE TABLE catalog_transaction_probe (id INTEGER PRIMARY KEY)"
    )
    catalog_connection.commit()

    repository = PersistentSourcePageRepository(database_path)
    cache = PersistentSourcePageCache(
        repository,
        ttl_seconds=3600,
        defer_writes=True,
    )
    url = "https://example.test/producto/deferred-write/"
    fetch_calls = []

    def fetcher(headers):
        fetch_calls.append(dict(headers))
        return FakeResponse(
            "<html>deferred page</html>",
            headers={"ETag": '"deferred-v1"'},
            url=url,
        )

    try:
        catalog_connection.execute("BEGIN")
        catalog_connection.execute(
            "SELECT normalized_url FROM source_page_cache"
        ).fetchall()

        assert cache.get_html(url, fetcher) == "<html>deferred page</html>"
        assert repository.get(url) is None

        # The catalog connection can still commit after a cache miss, because
        # the fetched HTML has only been queued in memory at this point.
        catalog_connection.execute(
            "INSERT INTO catalog_transaction_probe DEFAULT VALUES"
        )
        catalog_connection.commit()

        # The same URL can be served from the in-memory pending entry without
        # another HTTP request, before the entry is flushed to SQLite.
        assert cache.get_html(url, fetcher) == "<html>deferred page</html>"
        assert len(fetch_calls) == 1

        assert cache.flush_pending() == 1
        saved = repository.get(url)
        assert saved is not None
        assert saved.html == "<html>deferred page</html>"
    finally:
        if catalog_connection.in_transaction:
            catalog_connection.rollback()
        catalog_connection.close()

def test_forced_revalidation_does_not_use_stale_html_after_request_failure(tmp_path):
    repository = PersistentSourcePageRepository(tmp_path / "catalog.db")
    cache = PersistentSourcePageCache(repository, ttl_seconds=3600)
    url = "https://example.test/producto/foco-antiestres/"
    expected_html = "<html>copia anterior</html>"
    cache.get_html(
        url,
        lambda headers: FakeResponse(expected_html, url=url),
    )

    def failed_fetch(headers):
        raise requests.exceptions.Timeout("no se pudo validar la página actual")

    with pytest.raises(requests.exceptions.Timeout):
        cache.get_html(
            url,
            failed_fetch,
            force=True,
            allow_stale_fallback=False,
        )

    assert cache.get_metrics()["stale_fallbacks"] == 0
    saved = repository.get(url)
    assert saved is not None
    assert saved.html == expected_html

def test_forced_revalidation_rejects_empty_response_instead_of_using_cached_html(
    tmp_path,
):
    repository = PersistentSourcePageRepository(tmp_path / "catalog.db")
    cache = PersistentSourcePageCache(repository, ttl_seconds=3600)
    url = "https://example.test/producto/foco-antiestres/"
    cached_html = "<html>copia anterior</html>"
    cache.get_html(
        url,
        lambda headers: FakeResponse(cached_html, url=url),
    )

    with pytest.raises(RuntimeError, match="HTML vacío"):
        cache.get_html(
            url,
            lambda headers: FakeResponse("", status_code=200, url=url),
            force=True,
            allow_stale_fallback=False,
        )

    saved = repository.get(url)
    assert saved is not None
    assert saved.html == cached_html
    assert cache.get_metrics()["empty_response_fallbacks"] == 1
