from __future__ import annotations

import os
import random
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# The imports follow the direct-execution sys.path bootstrap; keep the main
# orchestration together because its stage boundaries are the benchmark.
# ruff: noqa: I001
from config.runtime_paths import DATA_DIR
from config.scraping_config import (
    MAX_RETRIES,
    REQUEST_TIMEOUT,
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
from scrapers.collectors.resilient_category_scraper import (
    ResilientCategoryScraper,
)
from scrapers.extractors.category_extractor import CategoryExtractor
from scrapers.extractors.category_product_extractor import (
    CategoryProductExtractor,
)
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_paths import IMAGE_PRODUCTS_DIR
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping import product_gallery_sync_service as gallery_module
from services.scraping.category_service import CategoryService

EXPECTED_CATEGORIES = 24
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class _CountingImageDownloader(ImageDownloader):
    """Counts completed gallery downloads without storing run data."""

    def __init__(
        self,
        output_dir: str | Path,
        request_timeout: int,
        max_retries: int,
    ) -> None:
        super().__init__(
            output_dir=output_dir,
            request_timeout=request_timeout,
            max_retries=max_retries,
        )
        self.gallery_downloads = 0
        self.gallery_failures = 0

    def download_gallery(
        self,
        code: str,
        url: str,
        position: int,
        output_dir: str | Path,
    ) -> str:
        try:
            result = super().download_gallery(code, url, position, output_dir)
        except Exception:
            self.gallery_failures += 1
            raise
        self.gallery_downloads += 1
        return result


class _MemoryGalleryRepository:
    """Read-only stand-in for saved gallery rows; never connects to SQLite."""

    def __init__(self, products: list[Any]) -> None:
        self.products = {
            str(getattr(product, "code", "") or "").strip().casefold(): product
            for product in products
            if str(getattr(product, "code", "") or "").strip()
        }

    def get_by_codes(self, codes: list[str]) -> dict[str, Any]:
        return {
            str(code).strip().casefold(): self.products[
                str(code).strip().casefold()
            ]
            for code in codes
            if str(code).strip().casefold() in self.products
        }


class _MemoryGalleryReviewService:
    """Accepts benchmark review callbacks in memory without persisting them."""

    def __init__(self, products: list[Any]) -> None:
        self.repository = _MemoryGalleryRepository(products)
        self.registered_candidates = 0

    def register_candidate(self, **kwargs: Any) -> dict[str, Any]:
        self.registered_candidates += 1
        return kwargs


def _positive_limit() -> int:
    raw = os.getenv("FCM_GALLERY_BENCH_LIMIT", str(DEFAULT_LIMIT)).strip()
    value = int(raw)
    if not 1 <= value <= MAX_LIMIT:
        raise ValueError(
            f"FCM_GALLERY_BENCH_LIMIT debe estar entre 1 y {MAX_LIMIT}."
        )
    return value


def _isolated_path_resolver(storage_root: Path):
    data_root = DATA_DIR.resolve()

    def resolve(path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            absolute = candidate.resolve()
            try:
                relative = absolute.relative_to(storage_root.resolve())
            except ValueError:
                try:
                    relative = absolute.relative_to(data_root)
                except ValueError as error:
                    raise ValueError(
                        f"Ruta fuera del almacenamiento aislado: {candidate}"
                    ) from error
        else:
            relative = candidate
        return storage_root / relative

    return resolve


def _metric_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    key: str,
) -> float:
    return max(
        float(after.get(key, 0.0) or 0.0)
        - float(before.get(key, 0.0) or 0.0),
        0.0,
    )


def _gallery_counts(products: list[Any]) -> tuple[int, int]:
    with_gallery = sum(
        bool(list(getattr(product, "gallery_images", []) or []))
        for product in products
    )
    images = sum(
        len(list(getattr(product, "gallery_images", []) or []))
        for product in products
    )
    return with_gallery, images


def _collect_and_enrich(
    collection: ProductCollectionScraper,
    categories: list[Any],
) -> tuple[list[Any], int, int, float, float]:
    category_workers = min(SCRAPING_CATEGORY_WORKERS, len(categories))
    collected_by_index: list[list[Any]] = [[] for _ in categories]

    collection_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=category_workers) as executor:
        futures = {
            executor.submit(collection.collect_category, category): index
            for index, category in enumerate(categories)
        }
        for future in as_completed(futures):
            collected_by_index[futures[future]] = future.result()
    collection_seconds = time.perf_counter() - collection_started

    expected_occurrences = sum(
        max(int(getattr(category, "expected_count", 0) or 0), 0)
        for category in categories
    )
    found_occurrences = sum(len(products) for products in collected_by_index)
    if found_occurrences != expected_occurrences:
        raise RuntimeError(
            "Cobertura de tarjetas incompleta: "
            f"esperadas={expected_occurrences}, encontradas={found_occurrences}."
        )

    enriched_by_index: list[list[Any] | None] = [None] * len(categories)
    enrichment_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=category_workers) as executor:
        futures = {
            executor.submit(
                collection.enrich_category_products,
                collected_by_index[index],
                str(getattr(category, "name", "") or ""),
            ): index
            for index, category in enumerate(categories)
        }
        for future in as_completed(futures):
            enriched_by_index[futures[future]] = future.result()
    enrichment_seconds = time.perf_counter() - enrichment_started

    products = [
        product
        for enriched in enriched_by_index
        for product in (enriched or [])
    ]
    consolidated = CatalogSyncService.consolidate_products(deepcopy(products))
    return (
        consolidated,
        expected_occurrences,
        found_occurrences,
        collection_seconds,
        enrichment_seconds,
    )


def main() -> int:
    limit = _positive_limit()
    browser = Browser(
        request_timeout=REQUEST_TIMEOUT,
        max_retries=MAX_RETRIES,
        http_workers=SCRAPING_HTTP_WORKERS,
    )
    browser.enable_thread_sessions()

    category_scraper = ResilientCategoryScraper(
        browser=browser,
        category_extractor=CategoryExtractor(),
        jsf_http_concurrency=SCRAPING_JSF_HTTP_CONCURRENCY,
        jsf_page_workers=SCRAPING_JSF_PAGE_WORKERS,
    )
    category_service = CategoryService(category_scraper, STORE_URL)
    collection = ProductCollectionScraper(
        category_scraper,
        ProductCardExtractor(),
        CategoryProductExtractor(),
        ProductExtractor(),
        max_workers=SCRAPING_MAX_WORKERS,
        category_page_workers=SCRAPING_CATEGORY_PAGE_WORKERS,
    )

    try:
        discovery_started = time.perf_counter()
        categories = list(category_service.scrape_all() or [])
        discovery_seconds = time.perf_counter() - discovery_started
        if len(categories) != EXPECTED_CATEGORIES:
            raise RuntimeError(
                f"Se esperaban {EXPECTED_CATEGORIES} categorías; "
                f"se encontraron {len(categories)}."
            )

        (
            consolidated,
            expected_occurrences,
            found_occurrences,
            collection_seconds,
            enrichment_seconds,
        ) = _collect_and_enrich(collection, categories)

        products_with_code = [
            product
            for product in consolidated
            if str(getattr(product, "code", "") or "").strip()
        ]
        products_with_code.sort(
            key=lambda product: str(product.code).strip().casefold()
        )
        selected = random.Random(20261017).sample(
            products_with_code,
            k=min(limit, len(products_with_code)),
        )
        selected.sort(
            key=lambda product: str(product.code).strip().casefold()
        )
        if not selected:
            raise RuntimeError("No se encontraron productos para el perfilado.")

        with tempfile.TemporaryDirectory(
            prefix="fcm-gallery-benchmark-"
        ) as temporary_directory:
            storage_root = Path(temporary_directory)
            gallery_module.resolve_data_path = _isolated_path_resolver(
                storage_root
            )
            gallery_root = gallery_module.resolve_data_path(IMAGE_PRODUCTS_DIR)
            downloader = _CountingImageDownloader(
                output_dir=storage_root / "data" / "images" / "products",
                request_timeout=REQUEST_TIMEOUT,
                max_retries=MAX_RETRIES,
            )

            clean_input = deepcopy(selected)
            clean_service = gallery_module.ProductGallerySyncService(
                browser=browser,
                product_extractor=ProductExtractor(),
                image_downloader=downloader,
                review_service=None,
                max_workers=4,
                max_candidates=6,
                refresh_existing=True,
            )
            clean_downloads_before = downloader.gallery_downloads
            clean_failures_before = downloader.gallery_failures
            before_clean = browser.get_http_metrics()
            clean_started = time.perf_counter()
            clean_products = clean_service.sync_products(clean_input)
            clean_seconds = time.perf_counter() - clean_started
            after_clean = browser.get_http_metrics()
            clean_with_gallery, clean_gallery_images = _gallery_counts(
                clean_products
            )
            clean_file_count = sum(
                1 for path in gallery_root.rglob("*") if path.is_file()
            )
            clean_downloads = downloader.gallery_downloads - clean_downloads_before
            clean_failures = downloader.gallery_failures - clean_failures_before

            warm_input = deepcopy(selected)
            memory_review = _MemoryGalleryReviewService(clean_products)
            warm_service = gallery_module.ProductGallerySyncService(
                browser=browser,
                product_extractor=ProductExtractor(),
                image_downloader=downloader,
                review_service=memory_review,
                max_workers=4,
                max_candidates=6,
                refresh_existing=False,
            )
            warm_downloads_before = downloader.gallery_downloads
            warm_failures_before = downloader.gallery_failures
            before_warm = browser.get_http_metrics()
            warm_started = time.perf_counter()
            warm_products = warm_service.sync_products(warm_input)
            warm_seconds = time.perf_counter() - warm_started
            after_warm = browser.get_http_metrics()
            warm_with_gallery, warm_gallery_images = _gallery_counts(warm_products)
            final_file_count = sum(
                1 for path in gallery_root.rglob("*") if path.is_file()
            )
            warm_downloads = downloader.gallery_downloads - warm_downloads_before
            warm_failures = downloader.gallery_failures - warm_failures_before

            print("=" * 80)
            print("PERFIL DE GALERÍAS REALES - ALMACENAMIENTO AISLADO")
            print("BASE DE DATOS DE PRODUCCIÓN:", "NO UTILIZADA")
            print("ALMACENAMIENTO DE IMÁGENES:", "TEMPORAL")
            print("CATEGORÍAS:", len(categories))
            print("APARICIONES ESPERADAS / ENCONTRADAS:", expected_occurrences, "/", found_occurrences)
            print("PRODUCTOS ÚNICOS CONSOLIDADOS:", len(products_with_code))
            print("PRODUCTOS EN LA MUESTRA:", len(selected))
            print(
                "CÓDIGOS DE LA MUESTRA:",
                ", ".join(str(product.code).strip() for product in selected),
            )
            print("DESCUBRIMIENTO:", f"{discovery_seconds:.2f}s")
            print("COLLECTION:", f"{collection_seconds:.2f}s")
            print("ENRICHMENT:", f"{enrichment_seconds:.2f}s")
            print("-" * 80)
            print("RECONSTRUCCIÓN DE GALERÍAS (SIN GALERÍA PREVIA)")
            print("GALLERY WALL:", f"{clean_seconds:.2f}s")
            print(
                "DETAIL HTTP REQUESTS:",
                int(_metric_delta(before_clean, after_clean, "detail_http_requests")),
            )
            print(
                "DETAIL HTTP TOTAL:",
                f"{_metric_delta(before_clean, after_clean, 'detail_http_total_seconds'):.2f}s",
            )
            print("PRODUCTOS CON GALERÍA:", clean_with_gallery)
            print("ENTRADAS DE GALERÍA:", clean_gallery_images)
            print("ARCHIVOS CREADOS:", clean_file_count)
            print("DESCARGAS DE GALERÍA EXITOSAS:", clean_downloads)
            print("DESCARGAS DE GALERÍA FALLIDAS:", clean_failures)
            print(
                "PAGE HTTP RETRIES:",
                int(_metric_delta(before_clean, after_clean, "http_retries")),
            )
            print("-" * 80)
            print("MODO INCREMENTAL (GALERÍAS PREEXISTENTES SIMULADAS EN MEMORIA)")
            print("GALLERY WALL:", f"{warm_seconds:.2f}s")
            print(
                "DETAIL HTTP REQUESTS:",
                int(_metric_delta(before_warm, after_warm, "detail_http_requests")),
            )
            print(
                "DETAIL HTTP TOTAL:",
                f"{_metric_delta(before_warm, after_warm, 'detail_http_total_seconds'):.2f}s",
            )
            print("PRODUCTOS CON GALERÍA:", warm_with_gallery)
            print("ENTRADAS DE GALERÍA:", warm_gallery_images)
            print("ARCHIVOS AL FINAL:", final_file_count)
            print("DESCARGAS DE GALERÍA EXITOSAS:", warm_downloads)
            print("DESCARGAS DE GALERÍA FALLIDAS:", warm_failures)
            print(
                "CANDIDATOS DE REVISIÓN EN MEMORIA:",
                memory_review.registered_candidates,
            )
            print(
                "PAGE HTTP RETRIES:",
                int(_metric_delta(before_warm, after_warm, "http_retries")),
            )
            print("-" * 80)
            total_http = browser.get_http_metrics()
            print("HTTP RETRIES ACUMULADOS:", total_http.get("http_retries", 0))
            print("HTTP ERRORES TERMINALES:", total_http.get("http_terminal_errors", 0))
            print("=" * 80)
            print(
                "NOTA: el benchmark reutiliza respuestas de extracción ya obtenidas "
                "para la misma muestra; el modo incremental simula galerías "
                "persistidas con archivos locales válidos."
            )
    finally:
        collection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
