from __future__ import annotations

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
