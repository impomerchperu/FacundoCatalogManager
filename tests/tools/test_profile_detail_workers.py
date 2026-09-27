import pytest

import tools.profile_detail_workers as profiler


class Category:
    def __init__(self, url):
        self.url = url


def test_positive_int_uses_default(monkeypatch):
    monkeypatch.delenv("FCM_PROFILE_DETAIL_WORKERS", raising=False)

    assert profiler._positive_int("FCM_PROFILE_DETAIL_WORKERS", 32) == 32


def test_positive_int_reads_override(monkeypatch):
    monkeypatch.setenv("FCM_PROFILE_DETAIL_WORKERS", "28")

    assert profiler._positive_int("FCM_PROFILE_DETAIL_WORKERS", 32) == 28


def test_positive_int_rejects_non_positive(monkeypatch):
    monkeypatch.setenv("FCM_PROFILE_DETAIL_WORKERS", "0")

    with pytest.raises(ValueError, match="mayor que cero"):
        profiler._positive_int("FCM_PROFILE_DETAIL_WORKERS", 32)


def test_worker_values_default_to_controlled_pair(monkeypatch):
    monkeypatch.delenv("FCM_PROFILE_DETAIL_WORKERS", raising=False)

    assert profiler._worker_values() == (24, 28)


def test_worker_values_accepts_explicit_pair(monkeypatch):
    monkeypatch.setenv("FCM_PROFILE_DETAIL_WORKERS", "16,32")

    assert profiler._worker_values() == (16, 32)


def test_select_category_uses_slug(monkeypatch):
    monkeypatch.delenv("FCM_PROFILE_DETAIL_CATEGORY", raising=False)

    categories = [
        Category(
            "https://stock.importacionesfacundo.com/categoria-producto/otro/"
        ),
        Category(
            "https://stock.importacionesfacundo.com/categoria-producto/"
            "papeles-fotograficos/"
        ),
    ]

    selected = profiler._select_category(categories)

    assert selected.url.endswith("/papeles-fotograficos/")


def test_select_category_accepts_override(monkeypatch):
    monkeypatch.setenv("FCM_PROFILE_DETAIL_CATEGORY", "otro")

    categories = [
        Category(
            "https://stock.importacionesfacundo.com/categoria-producto/otro/"
        ),
    ]

    assert profiler._select_category(categories) is categories[0]

def test_run_enrichment_builds_isolated_transport_for_each_variant(monkeypatch):
    transports = []
    closed_collections = []

    class FakeBrowser:
        def get_http_metrics(self):
            return {"http_requests": 1}

    class FakeCategoryScraper:
        pass

    class FakeCollection:
        def __init__(self):
            self.closed = False

        def enrich_category_products(self, products, category_name):
            assert category_name == "Demo"
            return products

        def get_enrichment_metrics(self, category_name):
            assert category_name == "Demo"
            return {"requested": 1, "skipped": 0}

        def close(self):
            self.closed = True
            closed_collections.append(self)

    def fake_build_transport():
        transport = (FakeBrowser(), FakeCategoryScraper())
        transports.append(transport)
        return transport

    monkeypatch.setattr(profiler, "_build_benchmark_transport", fake_build_transport)
    monkeypatch.setattr(
        profiler,
        "_build_collection",
        lambda category_scraper, max_workers: FakeCollection(),
    )

    category = Category("https://example.test/categoria-producto/demo/")
    category.name = "Demo"
    collected = [("card", "page", object())]

    first = profiler._run_enrichment(category, collected, 16)
    second = profiler._run_enrichment(category, collected, 24)

    assert len(transports) == 2
    assert first[3] == {"http_requests": 1}
    assert second[3] == {"http_requests": 1}
    assert len(closed_collections) == 2
