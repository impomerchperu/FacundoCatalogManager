from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

from scrapers.collectors.product_collection_scraper import ProductCollectionScraper


def test_detail_cache_coalesces_concurrent_fetches():
    collection = ProductCollectionScraper(
        category_scraper=object(),
        card_extractor=object(),
        product_extractor=object(),
        detail_extractor=object(),
        max_workers=2,
    )
    payload = SimpleNamespace(code="FB-1600", name="Producto")
    fetch_started = Event()
    release_fetch = Event()
    calls = []

    def fetch(detail_url, category_name):
        calls.append((detail_url, category_name))
        fetch_started.set()
        assert release_fetch.wait(timeout=2)
        return payload

    collection._fetch_detail_product = fetch

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(
                collection._get_detailed_product,
                "code:fb-1600",
                "https://example.com/producto/fb-1600/",
                "Categoria A",
            )
            assert fetch_started.wait(timeout=2)
            second_future = executor.submit(
                collection._get_detailed_product,
                "code:fb-1600",
                "https://example.com/producto/fb-1600/",
                "Categoria B",
            )
            release_fetch.set()

            assert first_future.result(timeout=2) is payload
            assert second_future.result(timeout=2) is payload

        metrics = collection.get_detail_metrics()
        assert calls == [
            (
                "https://example.com/producto/fb-1600/",
                "Categoria A",
            )
        ]
        assert metrics["detail_requests"] == 1
        assert metrics["detail_cache_size"] == 1
    finally:
        collection.close()
