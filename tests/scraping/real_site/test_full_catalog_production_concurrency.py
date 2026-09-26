import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter

import pytest

from config.scraping_config import (
    SCRAPING_CATEGORY_PAGE_WORKERS,
    SCRAPING_CATEGORY_WORKERS,
    SCRAPING_HTTP_WORKERS,
    SCRAPING_JSF_HTTP_CONCURRENCY,
    SCRAPING_JSF_PAGE_WORKERS,
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
from services.scraping.category_name_normalizer import split_category_names
from tools.benchmark_report import write_benchmark_report
from services.scraping.category_service import CategoryService

EXPECTED_CATEGORIES = 24
# Historical snapshot retained for diagnostics only; live category totals
# remain the source of truth for this benchmark.
REFERENCE_CATEGORY_OCCURRENCES = 534
REFERENCE_UNIQUE_PRODUCTS = 530
REFERENCE_MULTI_CATEGORY_PRODUCTS = 4


def _worker_count(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = int(raw)
    if value < 1:
        raise ValueError(f"{name} must be >= 1, got {value}")
    return value


@pytest.mark.real_site
def test_full_catalog_production_concurrency_real_site():
    """Benchmarka el patrón productivo con workers configurables por entorno."""
    category_workers = _worker_count(
        "FCM_BENCH_CATEGORY_WORKERS", SCRAPING_CATEGORY_WORKERS
    )
    detail_workers = _worker_count("FCM_BENCH_DETAIL_WORKERS", SCRAPING_MAX_WORKERS)
    http_workers = _worker_count("FCM_BENCH_HTTP_WORKERS", SCRAPING_HTTP_WORKERS)
    jsf_http_concurrency = _worker_count(
        "FCM_BENCH_JSF_HTTP_CONCURRENCY",
        SCRAPING_JSF_HTTP_CONCURRENCY,
    )
    jsf_page_workers = _worker_count(
        "FCM_BENCH_JSF_PAGE_WORKERS",
        SCRAPING_JSF_PAGE_WORKERS,
    )
    category_page_workers = _worker_count(
        "FCM_BENCH_CATEGORY_PAGE_WORKERS",
        SCRAPING_CATEGORY_PAGE_WORKERS,
    )
    collection_only = os.getenv("FCM_BENCH_COLLECTION_ONLY") == "1"
    thread_sessions = os.getenv("FCM_BENCH_THREAD_SESSIONS") == "1"
    benchmark_output = os.getenv("FCM_BENCH_OUTPUT_JSON", "").strip() or None

    started = perf_counter()
    browser = Browser(http_workers=http_workers)
    if thread_sessions:
        browser.enable_thread_sessions()
    category_scraper = ResilientCategoryScraper(
        browser=browser,
        category_extractor=CategoryExtractor(),
        jsf_http_concurrency=jsf_http_concurrency,
        jsf_page_workers=jsf_page_workers,
    )
    category_service = CategoryService(category_scraper, STORE_URL)
    collection = ProductCollectionScraper(
        category_scraper,
        ProductCardExtractor(),
        CategoryProductExtractor(),
        ProductExtractor(),
        max_workers=detail_workers,
        category_page_workers=category_page_workers,
    )

    categories = category_service.scrape_all()
    assert len(categories) == EXPECTED_CATEGORIES, categories
    expected_occurrences = sum(
        max(int(category.expected_count or 0), 0)
        for category in categories
    )
    if expected_occurrences != REFERENCE_CATEGORY_OCCURRENCES:
        print(
            "BASELINE HISTÓRICO DE APARICIONES:",
            REFERENCE_CATEGORY_OCCURRENCES,
            "ACTUAL:",
            expected_occurrences,
        )

    collected_by_index: list[list[tuple[object, str, object]]] = [
        [] for _ in categories
    ]
    collection_errors: list[str] = []
    collection_started = perf_counter()
    with ThreadPoolExecutor(
        max_workers=min(category_workers, len(categories))
    ) as executor:
        futures = {
            executor.submit(collection.collect_category, category): index
            for index, category in enumerate(categories)
        }
        for future in as_completed(futures):
            index = futures[future]
            category = categories[index]
            try:
                collected = future.result()
                collected_by_index[index] = collected
                print(
                    "COLLECTION CATEGORY:",
                    category.name,
                    "PRODUCTS:",
                    len(collected),
                    "ELAPSED:",
                    f"{perf_counter() - collection_started:.2f}s",
                )
            except Exception as error:  # noqa: BLE001
                collection_errors.append(
                    f"{category.name}: {type(error).__name__}: {error}"
                )
                print(
                    "COLLECTION ERROR:",
                    category.name,
                    type(error).__name__,
                    str(error),
                )
    collection_seconds = perf_counter() - collection_started
    assert not collection_errors, collection_errors

    collection_coverage_errors = [
        (
            categories[index].name,
            max(int(categories[index].expected_count or 0), 0),
            len(collected_by_index[index]),
        )
        for index in range(len(categories))
        if len(collected_by_index[index])
        != max(int(categories[index].expected_count or 0), 0)
    ]
    assert not collection_coverage_errors, collection_coverage_errors

    if collection_only:
        collection_elapsed = perf_counter() - collection_started
        collection_metrics = browser.get_http_metrics()
        print("COLLECTION-ONLY:", True)
        print("THREAD SESSIONS:", thread_sessions)
        print("CATEGORY PAGE WORKERS:", category_page_workers)
        print("COLLECTION WALL:", f"{collection_elapsed:.2f}s")
        print(
            "COLLECTION HTTP REQUESTS:",
            collection_metrics["category_http_requests"],
        )
        print(
            "COLLECTION JSF HTTP REQUESTS:",
            collection_metrics["jsf_http_requests"],
        )
        print(
            "COLLECTION HTTP MAX IN FLIGHT BY CLASS:",
            collection_metrics["http_max_in_flight_by_class"],
        )
        print(
            "COLLECTION HTTP LATENCY P50/P95/P99:",
            {
                request_class: values
                for request_class, values in collection_metrics[
                    "http_latency_percentiles"
                ].items()
                if request_class in {"category", "jsf"}
            },
        )
        print(
            "COLLECTION HTTP STAGE TOTALS:",
            {
                "category": collection_metrics["category_http_total_seconds"],
                "jsf": collection_metrics["jsf_http_total_seconds"],
            },
        )
        assert collection_metrics["http_terminal_errors"] == 0
        write_benchmark_report(
            benchmark_output,
            {
                "schema_version": 1,
                "mode": "collection_only",
                "configuration": {
                    "category_workers": category_workers,
                    "detail_workers": detail_workers,
                    "http_workers": http_workers,
                    "jsf_http_concurrency": jsf_http_concurrency,
                    "jsf_page_workers": jsf_page_workers,
                    "category_page_workers": category_page_workers,
                    "thread_sessions": thread_sessions,
                },
                "coverage": {
                    "categories": len(categories),
                    "expected_occurrences": expected_occurrences,
                    "found_occurrences": sum(
                        len(products)
                        for products in collected_by_index
                    ),
                    "category_coverage_errors": collection_coverage_errors,
                },
                "timing": {
                    "collection_seconds": collection_elapsed,
                },
                "http": collection_metrics,
            },
        )
        browser.close()
        return

    enriched_by_index: list[list[object] | None] = [None] * len(categories)
    enrichment_errors: list[str] = []
    enrichment_started = perf_counter()
    with ThreadPoolExecutor(
        max_workers=min(category_workers, len(categories))
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
                enriched = future.result()
                enriched_by_index[index] = enriched
                print(
                    "ENRICHMENT CATEGORY:",
                    category.name,
                    "PRODUCTS:",
                    len(enriched),
                    "ELAPSED:",
                    f"{perf_counter() - enrichment_started:.2f}s",
                )
            except Exception as error:  # noqa: BLE001
                enrichment_errors.append(
                    f"{category.name}: {type(error).__name__}: {error}"
                )
                print(
                    "ENRICHMENT ERROR:",
                    category.name,
                    type(error).__name__,
                    str(error),
                )
    enrichment_seconds = perf_counter() - enrichment_started
    assert not enrichment_errors, enrichment_errors

    enrichment_coverage_errors = [
        (
            categories[index].name,
            max(int(categories[index].expected_count or 0), 0),
            len(enriched_by_index[index] or []),
        )
        for index in range(len(categories))
        if len(enriched_by_index[index] or [])
        != max(int(categories[index].expected_count or 0), 0)
    ]
    assert not enrichment_coverage_errors, enrichment_coverage_errors

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
    without_color_stock = [
        product.code
        for product in products
        if not (getattr(product, "color_stock", {}) or {})
    ]
    invalid_color_stock_totals = [
        (
            product.code,
            product.stock,
            sum(
                int(stock)
                for stock in (getattr(product, "color_stock", {}) or {}).values()
            ),
        )
        for product in products
        if (getattr(product, "color_stock", {}) or {})
        and product.stock
        != sum(
            int(stock)
            for stock in (getattr(product, "color_stock", {}) or {}).values()
        )
    ]
    color_stock_categories = {
        category_name
        for product in products
        if getattr(product, "color_stock", {}) or {}
        for category_name in split_category_names(
            getattr(product, "category", "")
        )
    }

    http_metrics = browser.get_http_metrics()
    detail_metrics = collection.get_detail_metrics()
    pipeline_seconds = perf_counter() - started
    print("=" * 80)
    print("FULL PRODUCCIÓN - BENCHMARK DE CONCURRENCIA")
    print("CATEGORÍAS:", len(categories))
    print("APARICIONES ESPERADAS:", expected_occurrences)
    print("APARICIONES ENCONTRADAS:", len(products))
    print("PRODUCTOS ÚNICOS:", len(code_counts))
    print("PRODUCTOS MULTI-CATEGORÍA:", len(duplicate_codes))
    print("COLLECTION WALL:", f"{collection_seconds:.2f}s")
    print("ENRICHMENT WALL:", f"{enrichment_seconds:.2f}s")
    print("TOTAL PIPELINE:", f"{pipeline_seconds:.2f}s")
    print("CATEGORY WORKERS:", category_workers)
    print("DETAIL WORKERS:", detail_workers)
    print("HTTP WORKERS:", http_workers)
    print("JSF HTTP CONCURRENCY:", jsf_http_concurrency)
    print("JSF PAGE WORKERS:", jsf_page_workers)
    print("THREAD SESSIONS:", thread_sessions)
    print("CATEGORY PAGE WORKERS:", category_page_workers)
    print("HTTP REQUESTS:", http_metrics["http_requests"])
    print("HTTP MAX IN FLIGHT:", http_metrics["http_max_in_flight"])
    print(
        "HTTP MAX IN FLIGHT BY CLASS:",
        http_metrics["http_max_in_flight_by_class"],
    )
    print(
        "HTTP LATENCY P50/P95/P99:",
        http_metrics["http_latency_percentiles"],
    )
    print(
        "HTTP STAGE TOTALS:",
        {
            "category": http_metrics["category_http_total_seconds"],
            "jsf": http_metrics["jsf_http_total_seconds"],
            "detail": http_metrics["detail_http_total_seconds"],
            "other": http_metrics["other_http_total_seconds"],
        },
    )
    print("HTTP RETRIES:", http_metrics["http_retries"])
    print("CATEGORY HTTP REQUESTS:", http_metrics["category_http_requests"])
    print("JSF HTTP REQUESTS:", http_metrics["jsf_http_requests"])
    print("DETAIL HTTP REQUESTS:", http_metrics["detail_http_requests"])
    print("DETAIL CACHE HITS:", detail_metrics["detail_cache_hits"])
    print("DETAIL CACHE SIZE:", detail_metrics["detail_cache_size"])
    print("DETAIL SKIPPED:", detail_metrics["detail_skipped"])
    print("PRODUCTOS SIN STOCK POR COLOR:", len(without_color_stock))
    print("INCONSISTENCIAS STOCK/COLOR_STOCK:", invalid_color_stock_totals)
    print("CATEGORÍAS CON STOCK POR COLOR:", len(color_stock_categories))
    print("DETAIL SEMAPHORE WAIT:", f"{http_metrics['detail_semaphore_wait_seconds']:.2f}s")
    print("TOP SLOW REQUESTS:", http_metrics["slowest_requests"])
    print("=" * 80)

    assert len(products) == expected_occurrences
    assert len(code_counts) > 0
    assert len(code_counts) <= len(products)
    assert not without_color_stock
    assert not invalid_color_stock_totals
    assert len(color_stock_categories) == len(categories)
    assert http_metrics["http_terminal_errors"] == 0

    if len(code_counts) != REFERENCE_UNIQUE_PRODUCTS:
        print(
            "BASELINE HISTÓRICO DE PRODUCTOS ÚNICOS:",
            REFERENCE_UNIQUE_PRODUCTS,
            "ACTUAL:",
            len(code_counts),
        )
    if len(duplicate_codes) != REFERENCE_MULTI_CATEGORY_PRODUCTS:
        print(
            "BASELINE HISTÓRICO MULTI-CATEGORÍA:",
            REFERENCE_MULTI_CATEGORY_PRODUCTS,
            "ACTUAL:",
            len(duplicate_codes),
        )

    write_benchmark_report(
        benchmark_output,
        {
            "schema_version": 1,
            "mode": "full",
            "configuration": {
                "category_workers": category_workers,
                "detail_workers": detail_workers,
                "http_workers": http_workers,
                "jsf_http_concurrency": jsf_http_concurrency,
                "jsf_page_workers": jsf_page_workers,
                "category_page_workers": category_page_workers,
                "thread_sessions": thread_sessions,
            },
            "coverage": {
                "categories": len(categories),
                "expected_occurrences": expected_occurrences,
                "found_occurrences": len(products),
                "unique_products": len(code_counts),
                "multi_category_products": len(duplicate_codes),
                "color_stock_categories": len(color_stock_categories),
                "products_without_color_stock": len(without_color_stock),
                "invalid_color_stock_totals": invalid_color_stock_totals,
            },
            "timing": {
                "collection_seconds": collection_seconds,
                "enrichment_seconds": enrichment_seconds,
                "pipeline_seconds": pipeline_seconds,
            },
            "http": http_metrics,
            "detail": detail_metrics,
        },
    )
