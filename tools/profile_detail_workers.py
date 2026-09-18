from __future__ import annotations

import copy
import os
import sys
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.scraping_config import SCRAPING_HTTP_WORKERS, STORE_URL

from scrapers.browser import Browser
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.collectors.resilient_category_scraper import ResilientCategoryScraper
from scrapers.extractors.category_extractor import CategoryExtractor
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.category_service import CategoryService


DEFAULT_CATEGORY_SLUG = "papeles-fotograficos"
DEFAULT_WORKERS = (24, 28)


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{name} debe ser mayor que cero.")
    return value


def _worker_values() -> tuple[int, ...]:
    raw = os.getenv("FCM_PROFILE_DETAIL_WORKERS", "").strip()
    if not raw:
        return DEFAULT_WORKERS
    values = tuple(
        int(value.strip())
        for value in raw.split(",")
        if value.strip()
    )
    if not values or any(value <= 0 for value in values):
        raise ValueError(
            "FCM_PROFILE_DETAIL_WORKERS debe contener enteros positivos."
        )
    return values


def _select_category(categories):
    slug = (
        os.getenv(
            "FCM_PROFILE_DETAIL_CATEGORY",
            DEFAULT_CATEGORY_SLUG,
        )
        .strip()
        .strip("/")
        .casefold()
    )
    for category in categories:
        url = str(getattr(category, "url", "")).strip().rstrip("/").casefold()
        if url.endswith(f"/{slug}"):
            return category
    available = ", ".join(
        str(getattr(category, "url", "")).strip()
        for category in categories
    )
    raise RuntimeError(
        f"No se encontró la categoría '{slug}'. URLs disponibles: {available}"
    )


def _clone_collected(collected):
    return [
        (card, page_url, copy.copy(product))
        for card, page_url, product in collected
    ]


def _build_collection(category_scraper, max_workers):
    return ProductCollectionScraper(
        category_scraper,
        ProductCardExtractor(),
        CategoryProductExtractor(),
        ProductExtractor(),
        max_workers=max_workers,
    )


def _run_enrichment(browser, category_scraper, category, collected, max_workers):
    collection = _build_collection(category_scraper, max_workers)
    browser.reset_http_metrics()
    started = perf_counter()
    try:
        products = collection.enrich_category_products(
            _clone_collected(collected),
            category.name,
        )
        elapsed = perf_counter() - started
        metrics = collection.get_enrichment_metrics(category.name)
        http_metrics = browser.get_http_metrics()
        return products, elapsed, metrics, http_metrics
    finally:
        collection.close()


def main() -> int:
    browser = Browser(
        http_workers=_positive_int(
            "FCM_PROFILE_HTTP_WORKERS",
            SCRAPING_HTTP_WORKERS,
        )
    )
    browser.enable_thread_sessions()

    category_scraper = ResilientCategoryScraper(
        browser=browser,
        category_extractor=CategoryExtractor(),
    )
    category_service = CategoryService(category_scraper, STORE_URL)

    categories = category_service.scrape_all()
    category = _select_category(categories)

    print("=" * 80)
    print("CONTROLLED DETAIL WORKER BENCHMARK")
    print("CATEGORY:", category.name)
    print("EXPECTED:", category.expected_count)

    discovery_started = perf_counter()
    collection = _build_collection(category_scraper, max(DEFAULT_WORKERS))
    try:
        collected = collection.collect_category(category)
    finally:
        collection.close()
    discovery_seconds = perf_counter() - discovery_started

    print("COLLECTED:", len(collected))
    print("DISCOVERY:", f"{discovery_seconds:.2f}s")

    if len(collected) != int(category.expected_count or 0):
        raise RuntimeError(
            "La colección de referencia no coincide con expected_count: "
            f"{len(collected)} != {category.expected_count}"
        )

    results = []
    for max_workers in _worker_values():
        (
            products,
            elapsed,
            metrics,
            http_metrics,
        ) = _run_enrichment(
            browser,
            category_scraper,
            category,
            collected,
            max_workers,
        )
        results.append((max_workers, elapsed))
        print("-" * 80)
        print("DETAIL WORKERS:", max_workers)
        print("PRODUCTS:", len(products))
        print("ENRICHMENT WALL:", f"{elapsed:.2f}s")
        print("REQUESTED:", metrics.get("requested", 0))
        print("SKIPPED:", metrics.get("skipped", 0))
        print("SUBMIT:", f'{float(metrics.get("submit_seconds", 0.0) or 0.0):.3f}s')
        print("WAIT:", f'{float(metrics.get("wait_seconds", 0.0) or 0.0):.3f}s')
        print(
            "HTTP:",
            f'requests={http_metrics.get("http_requests", 0)}',
            f'errors={http_metrics.get("http_errors", 0)}',
            f'retries={http_metrics.get("http_retries", 0)}',
            f'max_in_flight={http_metrics.get("http_max_in_flight", 0)}',
        )
        print(
            "DETAIL HTTP:",
            f'total={float(http_metrics.get("detail_http_total_seconds", 0.0) or 0.0):.2f}s',
            f'max={float(http_metrics.get("detail_http_max_seconds", 0.0) or 0.0):.2f}s',
            f'semaphore_wait={float(http_metrics.get("detail_semaphore_wait_seconds", 0.0) or 0.0):.3f}s',
        )

    print("=" * 80)
    print("RESULTS:", results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
