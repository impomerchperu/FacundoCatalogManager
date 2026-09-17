from collections import Counter
from time import perf_counter

import pytest

from config.scraping_config import STORE_URL
from scrapers.browser import Browser
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.collectors.resilient_category_scraper import ResilientCategoryScraper
from scrapers.extractors.category_extractor import CategoryExtractor
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.category_service import CategoryService

EXPECTED_CATEGORIES = 24
# Live catalog snapshot verified during the current full-site coverage run.
EXPECTED_CATEGORY_OCCURRENCES = 534
EXPECTED_UNIQUE_PRODUCTS = 530
EXPECTED_MULTI_CATEGORY_PRODUCTS = 4
PRODUCTS_PER_PAGE = 25


@pytest.mark.real_site
def test_full_catalog_scraper_real_site():
    """Recorre todo el catálogo con el scraper resiliente usado en producción."""
    started = perf_counter()
    browser = Browser()
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
    )

    categories = category_service.scrape_all()
    assert len(categories) == EXPECTED_CATEGORIES, categories

    expected_total = sum(
        max(int(category.expected_count or 0), 0)
        for category in categories
    )
    if expected_total != EXPECTED_CATEGORY_OCCURRENCES:
        print("=" * 80)
        print("DESVIACIÓN DEL BASELINE DE APARICIONES")
        print("ESPERADO:", EXPECTED_CATEGORY_OCCURRENCES)
        print("OBTENIDO:", expected_total)
        print("DIFERENCIA:", expected_total - EXPECTED_CATEGORY_OCCURRENCES)
        for index, category in enumerate(categories, start=1):
            print(
                f"[{index:02d}/{len(categories):02d}] "
                f"{category.name}: expected={category.expected_count}"
            )
        print("DURACIÓN DESCUBRIMIENTO:", f"{perf_counter() - started:.2f}s")
        print("=" * 80)
    assert expected_total == EXPECTED_CATEGORY_OCCURRENCES

    products = []
    category_results = []
    errors = []
    profiling_totals = {
        "category_wall_seconds": 0.0,
        "discovery_seconds": 0.0,
        "page_load_seconds": 0.0,
        "enrichment_seconds": 0.0,
        "enrichment_submit_seconds": 0.0,
        "enrichment_wait_seconds": 0.0,
        "detail_requests": 0,
        "detail_skipped": 0,
    }
    for index, category in enumerate(categories, start=1):
        category_started = perf_counter()
        try:
            category_products = collection.scrape_category(category)
        except Exception as error:  # noqa: BLE001
            category_products = []
            errors.append(
                f"{category.name}: {type(error).__name__}: {error}"
            )
        category_seconds = perf_counter() - category_started
        products.extend(category_products)
        found = len(category_products)

        metrics = collection.get_page_metrics().get(category.url, {})
        enrichment = collection.get_enrichment_metrics(category.name)
        expected = max(int(category.expected_count or 0), 0)
        required_pages = max(
            (expected + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE,
            1,
        )
        pages_requested = int(metrics.get("pages_requested", 0) or 0)
        pages_loaded = int(metrics.get("pages_loaded", 0) or 0)
        cards_found = int(metrics.get("cards_found", 0) or 0)
        discovery_seconds = float(metrics.get("discovery_seconds", 0.0) or 0.0)
        page_load_seconds = float(metrics.get("page_load_seconds", 0.0) or 0.0)
        enrichment_seconds = float(enrichment.get("total_seconds", 0.0) or 0.0)
        enrichment_submit_seconds = float(
            enrichment.get("submit_seconds", 0.0) or 0.0
        )
        enrichment_wait_seconds = float(
            enrichment.get("wait_seconds", 0.0) or 0.0
        )
        detail_requests = int(enrichment.get("requested", 0) or 0)
        detail_skipped = int(enrichment.get("skipped", 0) or 0)
        page_error = None
        if pages_requested < required_pages:
            page_error = (
                f"pages_requested={pages_requested} < "
                f"required_pages={required_pages}"
            )
        elif pages_loaded != pages_requested:
            page_error = (
                f"pages_loaded={pages_loaded} != "
                f"pages_requested={pages_requested}"
            )

        category_results.append(
            {
                "category": category.name,
                "expected": expected,
                "found": found,
                "gap": max(expected - found, 0),
                "pages_expected": required_pages,
                "pages_requested": pages_requested,
                "pages_loaded": pages_loaded,
                "cards_found": cards_found,
                "discovery_seconds": discovery_seconds,
                "page_load_seconds": page_load_seconds,
                "enrichment_seconds": enrichment_seconds,
                "enrichment_submit_seconds": enrichment_submit_seconds,
                "enrichment_wait_seconds": enrichment_wait_seconds,
                "detail_requests": detail_requests,
                "detail_skipped": detail_skipped,
                "category_wall_seconds": category_seconds,
                "page_error": page_error,
            }
        )
        profiling_totals["category_wall_seconds"] += category_seconds
        profiling_totals["discovery_seconds"] += discovery_seconds
        profiling_totals["page_load_seconds"] += page_load_seconds
        profiling_totals["enrichment_seconds"] += enrichment_seconds
        profiling_totals["enrichment_submit_seconds"] += enrichment_submit_seconds
        profiling_totals["enrichment_wait_seconds"] += enrichment_wait_seconds
        profiling_totals["detail_requests"] += detail_requests
        profiling_totals["detail_skipped"] += detail_skipped
        print(
            f"[{index:02d}/{len(categories):02d}] "
            f"{category.name}: expected={expected} "
            f"found={found} "
            f"pages={pages_loaded}/{required_pages} "
            f"cards={cards_found} "
            f"wall={category_seconds:.2f}s "
            f"discovery={discovery_seconds:.2f}s "
            f"page_load={page_load_seconds:.2f}s "
            f"enrichment={enrichment_seconds:.2f}s "
            f"detail_requests={detail_requests}"
        )

    codes = [str(product.code).strip().upper() for product in products if product.code]
    missing_codes = [
        index
        for index, product in enumerate(products, start=1)
        if not str(product.code).strip()
    ]
    code_counts = Counter(codes)
    duplicate_codes = sorted(
        code for code, count in code_counts.items() if count > 1
    )
    multi_category_codes = [
        code for code in duplicate_codes if code_counts[code] >= 2
    ]
    without_prices = [
        product.code
        for product in products
        if product.price_sample <= 0
        and product.price_hundred <= 0
        and product.price_thousand <= 0
    ]
    without_images = [
        product.code
        for product in products
        if not product.image_url
    ]

    print("=" * 80)
    print("CATEGORÍAS:", len(categories))
    print("APARICIONES ESPERADAS:", expected_total)
    print("APARICIONES ENCONTRADAS:", len(products))
    print("PRODUCTOS ÚNICOS:", len(code_counts))
    print("PRODUCTOS MULTI-CATEGORÍA:", len(multi_category_codes))
    print("CÓDIGOS SIN CÓDIGO:", len(missing_codes))
    print("DUPLICADOS POR CÓDIGO:", duplicate_codes)
    print("PRODUCTOS SIN PRECIO:", without_prices)
    print("PRODUCTOS SIN IMAGEN:", without_images)
    print("ERRORES DE CATEGORÍA:", errors)
    print("ERRORES DE COBERTURA DE PÁGINAS:", [
        row for row in category_results if row["page_error"]
    ])
    print("=" * 80)
    print("PROFILING FULL POR CATEGORÍA")
    print("WALL TOTAL CATEGORÍAS:", f'{profiling_totals["category_wall_seconds"]:.2f}s')
    print("DISCOVERY ACUMULADO:", f'{profiling_totals["discovery_seconds"]:.2f}s')
    print("PAGE LOAD ACUMULADO:", f'{profiling_totals["page_load_seconds"]:.2f}s')
    print("ENRICHMENT ACUMULADO:", f'{profiling_totals["enrichment_seconds"]:.2f}s')
    print(
        "ENRICHMENT SUBMIT ACUMULADO:",
        f'{profiling_totals["enrichment_submit_seconds"]:.2f}s',
    )
    print(
        "ENRICHMENT WAIT ACUMULADO:",
        f'{profiling_totals["enrichment_wait_seconds"]:.2f}s',
    )
    print("DETAIL REQUESTS:", profiling_totals["detail_requests"])
    print("DETAIL SKIPPED:", profiling_totals["detail_skipped"])
    print(
        "TOP CATEGORÍAS POR WALL:",
        sorted(
            (
                (row["category"], row["category_wall_seconds"])
                for row in category_results
            ),
            key=lambda item: item[1],
            reverse=True,
        )[:5],
    )
    print(
        "TOP CATEGORÍAS POR ENRICHMENT:",
        sorted(
            (
                (row["category"], row["enrichment_seconds"])
                for row in category_results
            ),
            key=lambda item: item[1],
            reverse=True,
        )[:5],
    )
    http_metrics = browser.get_http_metrics()
    print("=" * 80)
    print("PROFILING HTTP FULL")
    print("HTTP REQUESTS:", http_metrics["http_requests"])
    print("HTTP SUCCESSES:", http_metrics["http_successes"])
    print("HTTP ERRORS:", http_metrics["http_errors"])
    print("HTTP RETRIES:", http_metrics["http_retries"])
    print(
        "HTTP RETRY SLEEP:",
        f'{http_metrics["http_retry_sleep_seconds"]:.2f}s',
    )
    print("HTTP MAX IN FLIGHT:", http_metrics["http_max_in_flight"])
    print("HTTP CONCURRENCY LIMIT:", http_metrics["http_concurrency_limit"])
    print("CATEGORY HTTP REQUESTS:", http_metrics["category_http_requests"])
    print(
        "CATEGORY HTTP TOTAL:",
        f'{http_metrics["category_http_total_seconds"]:.2f}s',
    )
    print(
        "CATEGORY SEMAPHORE WAIT:",
        f'{http_metrics["category_semaphore_wait_seconds"]:.2f}s',
    )
    print("JSF HTTP REQUESTS:", http_metrics["jsf_http_requests"])
    print("JSF HTTP TOTAL:", f'{http_metrics["jsf_http_total_seconds"]:.2f}s')
    print(
        "JSF SEMAPHORE WAIT:",
        f'{http_metrics["jsf_semaphore_wait_seconds"]:.2f}s',
    )
    print("DETAIL HTTP REQUESTS:", http_metrics["detail_http_requests"])
    print(
        "DETAIL HTTP TOTAL:",
        f'{http_metrics["detail_http_total_seconds"]:.2f}s',
    )
    print(
        "DETAIL SEMAPHORE WAIT:",
        f'{http_metrics["detail_semaphore_wait_seconds"]:.2f}s',
    )
    print(
        "TOP SLOW REQUESTS:",
        http_metrics["slowest_requests"],
    )
    print("DURACIÓN TOTAL:", f"{perf_counter() - started:.2f}s")
    print("=" * 80)

    gaps = [row for row in category_results if row["gap"]]
    page_errors = [row for row in category_results if row["page_error"]]
    assert not errors, errors
    assert not missing_codes, missing_codes[:20]
    assert not gaps, gaps
    assert not page_errors, page_errors
    assert len(products) == EXPECTED_CATEGORY_OCCURRENCES
    assert len(code_counts) == EXPECTED_UNIQUE_PRODUCTS
    assert len(multi_category_codes) == EXPECTED_MULTI_CATEGORY_PRODUCTS
