from types import SimpleNamespace

from scrapers.collectors.product_collection_scraper import ProductCollectionScraper


def test_detail_cache_reuses_completed_future_without_second_request():
    collection = ProductCollectionScraper(
        category_scraper=object(),
        card_extractor=object(),
        product_extractor=object(),
        detail_extractor=object(),
        max_workers=1,
    )
    payload = SimpleNamespace(code="FB-1600", name="Producto")
    calls = []

    def fetch(detail_url, category_name):
        calls.append((detail_url, category_name))
        return payload

    collection._fetch_detail_product = fetch

    try:
        first = collection._get_detailed_product(
            "code:fb-1600",
            "https://example.com/producto/fb-1600/",
            "Categoria A",
        )
        second = collection._get_detailed_product(
            "code:fb-1600",
            "https://example.com/producto/fb-1600/",
            "Categoria B",
        )

        assert first is payload
        assert second is payload
        assert calls == [
            (
                "https://example.com/producto/fb-1600/",
                "Categoria A",
            )
        ]
        metrics = collection.get_detail_metrics()
        assert metrics["detail_requests"] == 1
        assert metrics["detail_cache_size"] == 1
    finally:
        collection.close()
