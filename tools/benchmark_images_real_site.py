import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from threading import Lock
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
from scrapers.collectors import category_pagination_engine
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.collectors.resilient_category_scraper import ResilientCategoryScraper
from scrapers.extractors.category_extractor import CategoryExtractor
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_repository import ImageRepository
from scrapers.images.safe_image_manager import SafeImageManager
from scrapers.sync.image_sync import ImageSync
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.category_name_normalizer import split_category_names
from services.scraping.category_service import CategoryService
from tools.benchmark_report import write_benchmark_report

EXPECTED_CATEGORIES = 24


class _ProgressImageManager:
    """Añade progreso visible sin alterar la implementación productiva."""

    def __init__(self, manager, total: int):
        self._manager = manager
        self._total = total
        self._completed = 0
        self._lock = Lock()

    def process(self, code, url, force=False):
        result = self._manager.process(code, url, force=force)
        with self._lock:
            self._completed += 1
            completed = self._completed
        if completed == 1 or completed % 10 == 0 or completed == self._total:
            print("IMAGE PROGRESS:", f"{completed}/{self._total}")
        return result


def _worker_count(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = int(raw)
    if value < 1:
        raise ValueError(f"{name} must be >= 1, got {value}")
    return value


def _skip_boundary_probe(
    scraper: object,
    category_url: str,
    category_id: int,
    page: int,
    seen_product_keys: set[str],
) -> tuple[bool, set[str], int, int]:
    del scraper, category_url, category_id, page, seen_product_keys
    return False, set(), 0, 0


@pytest.mark.real_site
def test_full_catalog_production_image_benchmark(tmp_path, monkeypatch):
    """Mide el costo real de sincronizar las imágenes del catálogo FULL."""
    image_workers = _worker_count("FCM_IMAGE_BENCH_WORKERS", 8)
    raw_image_limit = os.getenv("FCM_IMAGE_BENCH_LIMIT", "").strip()
    image_limit = int(raw_image_limit) if raw_image_limit else 0
    if image_limit < 0:
        raise ValueError("FCM_IMAGE_BENCH_LIMIT must be >= 0")
    if image_workers == 1 and image_limit == 0:
        raise ValueError(
            "FCM_IMAGE_BENCH_LIMIT es obligatorio cuando "
            "FCM_IMAGE_BENCH_WORKERS=1; no se permite un benchmark "
            "secuencial FULL no acotado."
        )
    category_workers = SCRAPING_CATEGORY_WORKERS
    detail_workers = SCRAPING_MAX_WORKERS
    http_workers = SCRAPING_HTTP_WORKERS
    jsf_http_concurrency = _worker_count(
        "FCM_JSF_HTTP_BENCH_CONCURRENCY",
        SCRAPING_JSF_HTTP_CONCURRENCY,
    )
    jsf_page_workers = _worker_count(
        "FCM_JSF_PAGE_BENCH_WORKERS",
        SCRAPING_JSF_PAGE_WORKERS,
    )
    category_page_workers = _worker_count(
        "FCM_CATEGORY_PAGE_BENCH_WORKERS",
        SCRAPING_CATEGORY_PAGE_WORKERS,
    )
    skip_boundary_probe = os.getenv(
        "FCM_JSF_BENCH_SKIP_BOUNDARY_PROBE",
        "",
    ).strip().casefold() in {"1", "true", "yes"}

    if skip_boundary_probe:
        monkeypatch.setattr(
            category_pagination_engine,
            "_probe_boundary_page",
            _skip_boundary_probe,
        )

    started = perf_counter()
    browser = Browser(http_workers=http_workers)
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

    try:
        categories = category_service.scrape_all()
        assert len(categories) == EXPECTED_CATEGORIES, categories

        collected_by_index: list[list[tuple[object, str, object]]] = [
            [] for _ in categories
        ]
        collection_workers = min(category_workers, len(categories))
        collection_started = perf_counter()
        with ThreadPoolExecutor(max_workers=collection_workers) as executor:
            futures = {
                executor.submit(collection.collect_category, category): index
                for index, category in enumerate(categories)
            }
            for future in as_completed(futures):
                collected_by_index[futures[future]] = future.result()
        collection_seconds = perf_counter() - collection_started

        expected_occurrences = sum(
            max(int(category.expected_count or 0), 0)
            for category in categories
        )
        collected_count = sum(len(items) for items in collected_by_index)
        assert collected_count == expected_occurrences

        pre_enrichment_by_index = deepcopy(collected_by_index)
        enriched_by_index: list[list[object] | None] = [None] * len(categories)
        enrichment_started = perf_counter()
        with ThreadPoolExecutor(max_workers=collection_workers) as executor:
            futures = {
                executor.submit(
                    collection.enrich_category_products,
                    collected_by_index[index],
                    category.name,
                ): index
                for index, category in enumerate(categories)
            }
            for future in as_completed(futures):
                enriched_by_index[futures[future]] = future.result()
        enrichment_seconds = perf_counter() - enrichment_started

        products = [
            product
            for enriched in enriched_by_index
            for product in (enriched or [])
        ]

        detail_recovered = Counter()
        detail_missing_before = Counter()
        for index, category_products in enumerate(pre_enrichment_by_index):
            enriched_products = enriched_by_index[index] or []
            for (_, _, before), after in zip(category_products, enriched_products):
                for field in ("sample", "hundred", "thousand", "description", "image"):
                    before_field = (
                        f"price_{field}"
                        if field in {"sample", "hundred", "thousand"}
                        else f"{field}_url" if field == "image" else field
                    )
                    before_value = getattr(before, before_field, 0 if field in {"sample", "hundred", "thousand"} else "")
                    after_value = getattr(after, before_field, 0 if field in {"sample", "hundred", "thousand"} else "")
                    if (
                        float(before_value or 0) <= 0
                        if field in {"sample", "hundred", "thousand"}
                        else not str(before_value or "").strip()
                    ):
                        detail_missing_before[field] += 1
                        recovered = (
                            float(after_value or 0) > 0
                            if field in {"sample", "hundred", "thousand"}
                            else bool(str(after_value or "").strip())
                        )
                        if recovered:
                            detail_recovered[field] += 1

        codes = [
            str(product.code).strip().upper()
            for product in products
            if getattr(product, "code", "")
        ]
        unique_codes = set(codes)
        assert len(products) == expected_occurrences
        assert len(unique_codes) > 0

        consolidated = CatalogSyncService.consolidate_products(
            deepcopy(products)
        )
        assert len(consolidated) == len(unique_codes)

        products_with_images = [
            product
            for product in sorted(
                consolidated,
                key=lambda item: str(getattr(item, "code", "")).strip().casefold(),
            )
            if str(getattr(product, "image_url", "")).strip()
        ]
        assert products_with_images
        if image_limit > 0:
            products_with_images = products_with_images[:image_limit]
        assert products_with_images

        image_output_dir = tmp_path / "images"
        image_downloader = ImageDownloader(
            output_dir=image_output_dir,
            request_timeout=20,
            max_retries=3,
        )
        image_repository = ImageRepository(output_dir=image_output_dir)
        image_manager = SafeImageManager(
            downloader=image_downloader,
            repository=image_repository,
        )
        progress_manager = _ProgressImageManager(
            image_manager,
            len(products_with_images),
        )
        image_sync = ImageSync(
            image_manager=progress_manager,
            image_repository=image_repository,
            max_workers=image_workers,
        )

        image_started = perf_counter()
        synced = image_sync.process(products_with_images)
        image_seconds = perf_counter() - image_started

        assert len(synced) == len(products_with_images)
        missing_images = [
            str(product.code).strip()
            for product in synced
            if not str(getattr(product, "image_path", "")).strip()
        ]
        assert not missing_images, missing_images

        image_files = [
            path
            for path in image_output_dir.iterdir()
            if path.is_file()
        ]
        assert len(image_files) == len(products_with_images)

        page_metrics = collection.get_page_metrics()
        collection_discovery_seconds = sum(
            float(metrics.get("discovery_seconds", 0.0) or 0.0)
            for metrics in page_metrics.values()
        )
        collection_page_load_seconds = sum(
            float(metrics.get("page_load_seconds", 0.0) or 0.0)
            for metrics in page_metrics.values()
        )
        collection_pages_requested = sum(
            int(metrics.get("pages_requested", 0) or 0)
            for metrics in page_metrics.values()
        )
        collection_pages_loaded = sum(
            int(metrics.get("pages_loaded", 0) or 0)
            for metrics in page_metrics.values()
        )
        collection_cards_found = sum(
            int(metrics.get("cards_found", 0) or 0)
            for metrics in page_metrics.values()
        )
        detail_metrics = collection.get_detail_metrics()
        detail_reason_counts = dict(
            detail_metrics.get("detail_reason_counts", {})
        )
        http_metrics = browser.get_http_metrics()
        color_stock_categories = {
            category_name
            for product in products
            if getattr(product, "color_stock", {}) or {}
            for category_name in split_category_names(
                getattr(product, "category", "")
            )
        }
        duplicate_codes = [
            code
            for code, count in Counter(codes).items()
            if count > 1
        ]

        pipeline_seconds = perf_counter() - started
        print("=" * 80)
        print("FULL PRODUCCIÓN - BENCHMARK DE IMÁGENES")
        print("CATEGORÍAS:", len(categories))
        print("APARICIONES ESPERADAS:", expected_occurrences)
        print("APARICIONES ENCONTRADAS:", len(products))
        print("PRODUCTOS ÚNICOS:", len(unique_codes))
        print("MULTI-CATEGORÍA:", len(duplicate_codes))
        print("PRODUCTOS CON IMAGEN:", len(products_with_images))
        print("COLLECTION:", f"{collection_seconds:.2f}s")
        print(
            "  COLLECTION DISCOVERY:",
            f"{collection_discovery_seconds:.2f}s",
        )
        print(
            "  COLLECTION PAGE LOAD:",
            f"{collection_page_load_seconds:.2f}s",
        )
        print("  COLLECTION PAGES:", collection_pages_requested)
        print("  COLLECTION PAGES LOADED:", collection_pages_loaded)
        print("  COLLECTION CARDS:", collection_cards_found)
        print("ENRICHMENT:", f"{enrichment_seconds:.2f}s")
        print("  DETAIL REQUESTS:", detail_metrics["detail_requests"])
        print("  DETAIL SKIPPED:", detail_metrics["detail_skipped"])
        print("  DETAIL CACHE HITS:", detail_metrics["detail_cache_hits"])
        print("  DETAIL REQUEST REASONS:")
        for reason, count in sorted(
            detail_reason_counts.items(),
            key=lambda item: (-item[1], item[0]),
        ):
            print(f"    {reason}: {count}")
        print("  DETAIL MISSING BEFORE / RECOVERED:")
        for field in ("sample", "hundred", "thousand", "description", "image"):
            print(
                f"    {field}: "
                f"{detail_missing_before[field]}/"
                f"{detail_recovered[field]}"
            )
        print(
            "SCRAPING + PREPARACIÓN:",
            f"{pipeline_seconds - image_seconds:.2f}s",
        )
        print("IMAGE SYNC:", f"{image_seconds:.2f}s")
        print("TOTAL:", f"{pipeline_seconds:.2f}s")
        print("IMAGE WORKERS:", image_workers)
        print("IMAGE LIMIT:", image_limit or "FULL")
        print("HTTP REQUESTS:", http_metrics["http_requests"])
        print("  JSF REQUESTS:", http_metrics["jsf_http_requests"])
        print(
            "  JSF MAX IN-FLIGHT:",
            http_metrics["http_max_in_flight_by_class"]["jsf"],
        )
        print("  JSF BOUNDARY PROBE SKIPPED:", skip_boundary_probe)
        print(
            "  JSF HTTP TOTAL:",
            f"{http_metrics["jsf_http_total_seconds"]:.2f}s",
        )
        print(
            "  JSF HTTP MAX:",
            f"{http_metrics["jsf_http_max_seconds"]:.2f}s",
        )
        jsf_percentiles = http_metrics["http_latency_percentiles"]["jsf"]
        detail_percentiles = http_metrics["http_latency_percentiles"]["detail"]
        print(
            "  JSF LATENCY P50/P95/P99:",
            f"{jsf_percentiles["p50"]:.2f}s/"
            f"{jsf_percentiles["p95"]:.2f}s/"
            f"{jsf_percentiles["p99"]:.2f}s",
        )
        print("  DETAIL REQUESTS:", http_metrics["detail_http_requests"])
        print(
            "  DETAIL HTTP TOTAL:",
            f"{http_metrics["detail_http_total_seconds"]:.2f}s",
        )
        print(
            "  DETAIL HTTP MAX:",
            f"{http_metrics["detail_http_max_seconds"]:.2f}s",
        )
        print(
            "  DETAIL LATENCY P50/P95/P99:",
            f"{detail_percentiles["p50"]:.2f}s/"
            f"{detail_percentiles["p95"]:.2f}s/"
            f"{detail_percentiles["p99"]:.2f}s",
        )
        print(
            "  DETAIL SEMAPHORE WAIT:",
            f"{http_metrics["detail_semaphore_wait_seconds"]:.2f}s",
        )
        print(
            "  JSF SEMAPHORE WAIT:",
            f"{http_metrics["jsf_semaphore_wait_seconds"]:.2f}s",
        )
        print("HTTP RETRIES:", http_metrics["http_retries"])
        print("HTTP TERMINAL ERRORS:", http_metrics["http_terminal_errors"])
        print("=" * 80)

        assert len(color_stock_categories) == EXPECTED_CATEGORIES
        assert http_metrics["http_terminal_errors"] == 0

        write_benchmark_report(
            os.getenv("FCM_IMAGE_BENCH_OUTPUT_JSON", "").strip() or None,
            {
                "schema_version": 1,
                "mode": "image_full",
                "configuration": {
                    "category_workers": category_workers,
                    "detail_workers": detail_workers,
                    "http_workers": http_workers,
                    "jsf_http_concurrency": jsf_http_concurrency,
                    "jsf_page_workers": jsf_page_workers,
                    "category_page_workers": category_page_workers,
                    "thread_sessions": True,
                    "skip_boundary_probe": skip_boundary_probe,
                    "image_workers": image_workers,
                },
                "coverage": {
                    "categories": len(categories),
                    "expected_occurrences": expected_occurrences,
                    "found_occurrences": len(products),
                },
                "timing": {
                    "collection_seconds": collection_seconds,
                    "collection_discovery_seconds": collection_discovery_seconds,
                    "collection_page_load_seconds": collection_page_load_seconds,
                    "enrichment_seconds": enrichment_seconds,
                    "image_seconds": image_seconds,
                    "pipeline_seconds": pipeline_seconds,
                },
                "collection": {
                    "pages_requested": collection_pages_requested,
                    "pages_loaded": collection_pages_loaded,
                    "cards_found": collection_cards_found,
                },
                "http": http_metrics,
                "detail": detail_metrics,
            },
        )
    finally:
        collection.close()
        browser.close()
