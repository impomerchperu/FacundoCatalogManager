from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter

import pytest

from config.scraping_config import (
    SCRAPING_CATEGORY_WORKERS,
    SCRAPING_HTTP_WORKERS,
    SCRAPING_MAX_WORKERS,
    STORE_URL,
)
from scrapers.browser import Browser
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.collectors.resilient_category_scraper import ResilientCategoryScraper
from scrapers.extractors.category_extractor import CategoryExtractor
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.category_service import CategoryService

EXPECTED_CATEGORIES = 24
EXPECTED_CATEGORY_OCCURRENCES = 534
EXPECTED_UNIQUE_PRODUCTS = 530
EXPECTED_MULTI_CATEGORY_PRODUCTS = 4


@pytest.mark.real_site
def test_full_catalog_production_concurrency_real_site():
    """Benchmark del mismo patrón de concurrencia usado por el servicio productivo."""
    started = perf_counter()
    browser = Browser(http_workers=SCRAPING_HTTP_WORKERS)
    category_scraper = ResilientCategoryScraper(
        browser=browser,
        category_extractor=CategoryExtractor(),
    )
    category_service = CategoryService(category_scraper, STORE_URL)
    collection = ProductCollectionScraper(
        category_scraper,
        ProductCardExtractor(),
        CategoryProductExtractor(),
        ProductExtractor(),
        max_workers=SCRAPING_MAX_WORKERS,
    )

    categories = category_service.scrape_all()
    assert len(categories) == EXPECTED_CATEGORIES, categories
    expected_occurrences = sum(
        max(int(category.expected_count or 0), 0)
        for category in categories
    )
    assert expected_occurrences == EXPECTED_CATEGORY_OCCURRENCES

    collected_by_index: list[list[tuple[object, str, object]]] = [
        [] for _ in categories
    ]
    collection_errors: list[str] = []
    collection_started = perf_counter()
    with ThreadPoolExecutor(
        max_workers=min(SCRAPING_CATEGORY_WORKERS, len(categories))
    ) as executor:
        futures = {
            executor.submit(collection.collect_category, category): index
            for index, category in enumerate(categories)
        }
        for future in as_completed(futures):
            index = futures[future]
            category = categories[index]
            try:
                collected_by_index[index] = future.result()
            except Exception as error:  # noqa: BLE001
                collection_errors.append(
                    f"{category.name}: {type(error).__name__}: {error}"
                )
    collection_seconds = perf_counter() - collection_started
    assert not collection_errors, collection_errors

    enriched_by_index: list[list[object] | None] = [None] * len(categories)
    enrichment_errors: list[str] = []
    enrichment_started = perf_counter()
    with ThreadPoolExecutor(
        max_workers=min(SCRAPING_CATEGORY_WORKERS, len(categories))
    ) as executor:
        futures = {
            executor.submit(
                collection.enrich_category_products,
                collected_by_index[index],
                category.name,
            ): index
            for index, category in enumerate(categories)
        }
        for future in as_completed(futures):
            index = futures[future]
            category = categories[index]
            try:
                enriched_by_index[index] = future.result()
            except Exception as error:  # noqa: BLE001
                enrichment_errors.append(
                    f"{category.name}: {type(error).__name__}: {error}"
                )
    enrichment_seconds = perf_counter() - enrichment_started
    assert not enrichment_errors, enrichment_errors

    products = [
        product
        for enriched in enriched_by_index
        for product in (enriched or [])
    ]
    codes = [str(product.code).strip().upper() for product in products if product.code]
    code_counts = Counter(codes)
    duplicate_codes = sorted(
        code for code, count in code_counts.items() if count > 1
    )

    http_metrics = browser.get_http_metrics()
    print("=" * 80)
    print("FULL PRODUCCIÓN - BENCHMARK DE CONCURRENCIA")
    print("CATEGORÍAS:", len(categories))
    print("APARICIONES ESPERADAS:", expected_occurrences)
    print("APARICIONES ENCONTRADAS:", len(products))
    print("PRODUCTOS ÚNICOS:", len(code_counts))
    print("PRODUCTOS MULTI-CATEGORÍA:", len(duplicate_codes))
    print("COLLECTION WALL:", f"{collection_seconds:.2f}s")
    print("ENRICHMENT WALL:", f"{enrichment_seconds:.2f}s")
    print("TOTAL PIPELINE:", f"{perf_counter() - started:.2f}s")
    print("CATEGORY WORKERS:", SCRAPING_CATEGORY_WORKERS)
    print("DETAIL WORKERS:", SCRAPING_MAX_WORKERS)
    print("HTTP WORKERS:", SCRAPING_HTTP_WORKERS)
    print("HTTP REQUESTS:", http_metrics["http_requests"])
    print("HTTP MAX IN FLIGHT:", http_metrics["http_max_in_flight"])
    print("HTTP RETRIES:", http_metrics["http_retries"])
    print("CATEGORY HTTP REQUESTS:", http_metrics["category_http_requests"])
    print("JSF HTTP REQUESTS:", http_metrics["jsf_http_requests"])
    print("DETAIL HTTP REQUESTS:", http_metrics["detail_http_requests"])
    print("DETAIL SEMAPHORE WAIT:", f"{http_metrics['detail_semaphore_wait_seconds']:.2f}s")
    print("TOP SLOW REQUESTS:", http_metrics["slowest_requests"])
    print("=" * 80)

    assert len(products) == EXPECTED_CATEGORY_OCCURRENCES
    assert len(code_counts) == EXPECTED_UNIQUE_PRODUCTS
    assert len(duplicate_codes) == EXPECTED_MULTI_CATEGORY_PRODUCTS
    assert http_metrics["http_terminal_errors"] == 0
