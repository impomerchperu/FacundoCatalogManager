from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from config.scraping_config import SCRAPING_CATEGORY_WORKERS
from models.scraping.sync_result import SyncResult
from services.scraping.category_name_normalizer import (
    canonical_category_name,
    normalize_category_name,
    split_category_names,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TIMING_LOG = PROJECT_ROOT / "data" / "scraping_timing.log"


def _log_timing(message, *args):
    TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
    formatted = message % args if args else message
    with TIMING_LOG.open("a", encoding="utf-8") as file:
        file.write(f"{formatted}\n")


class CategoryProductSyncService:
    """Coordina extracción, enriquecimiento y sincronización de productos."""

    def __init__(
        self,
        scraper_service,
        persistence_service,
        mapper=None,
        catalog_sync_service=None,
        image_sync_adapter=None,
    ):
        self.scraper_service = scraper_service
        self.persistence_service = persistence_service
        self.mapper = mapper
        self.catalog_sync_service = catalog_sync_service
        self.image_sync_adapter = image_sync_adapter
        self.last_sync_result = SyncResult()

    def reset_sync_result(self):
        self.last_sync_result = SyncResult()

    @staticmethod
    def _split_categories(value: object) -> list[str]:
        """Mantiene la API histórica delegando en el normalizador canónico."""
        return split_category_names(value)

    def sync_category(self, category_url, category=""):
        started = time.perf_counter()
        result = self.scraper_service.scrape_category(category_url, category)
        _log_timing(
            "SCRAPING TIMING | stage=category_sync | category=%s | products=%d | seconds=%.3f",
            category,
            len(result),
            time.perf_counter() - started,
        )
        self.sync_products(result, full_sync=False, allow_prune=False)
        return result

    def sync_categories(self, categories, progress_callback=None):
        self._reset_scraping_metrics()
        total_started = time.perf_counter()
        categories = list(categories or [])
        expected_category_occurrences = sum(
            max(int(getattr(category, "expected_count", 0) or 0), 0)
            for category in categories
        )
        self.last_sync_result = SyncResult()
        self.last_sync_result.products_expected = 0
        self.last_sync_result.expected_category_occurrences = (
            expected_category_occurrences
        )

        collected_by_index = [None] * len(categories)
        started = time.perf_counter()
        self._enable_thread_sessions()
        if categories:
            worker_count = min(SCRAPING_CATEGORY_WORKERS, len(categories))
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(self._collect_category, index, category): index
                    for index, category in enumerate(categories)
                }
                for future, index in futures.items():
                    collected_by_index[index] = future.result()
                    if progress_callback:
                        progress_callback(index + 1, len(categories))
        _log_timing(
            "SCRAPING TIMING | stage=category_listing | categories=%d | products=%d | "
            "expected_category_occurrences=%d | seconds=%.3f",
            len(categories),
            sum(len(items or []) for items in collected_by_index),
            expected_category_occurrences,
            time.perf_counter() - started,
        )

        started = time.perf_counter()
        products = []
        for index, category in enumerate(categories):
            collected = collected_by_index[index] or []
            products.extend(self._enrich_category(index, category, collected))
        _log_timing(
            "SCRAPING TIMING | stage=category_extraction | categories=%d | products=%d | "
            "expected_category_occurrences=%d | seconds=%.3f",
            len(categories),
            len(products),
            expected_category_occurrences,
            time.perf_counter() - started,
        )
        self._log_detail_metrics()
        self._log_http_metrics()

        raw_products = list(products)
        coverage_products = self._consolidate_for_coverage(raw_products)
        self._attach_category_coverage(raw_products, coverage_products, categories)

        full_mode = getattr(self, "_scraping_mode", "directed") == "full"
        complete, reason = self._full_sync_prune_guard(
            raw_products,
            len(categories),
            expected_category_occurrences=expected_category_occurrences,
            expected_products=len(coverage_products) if full_mode else 0,
        )
        if not full_mode:
            reason = "directed_mode"
            complete = False
        _log_timing(
            "SCRAPING TIMING | stage=coverage_incomplete | reason=%s | products=%d | "
            "categories=%d | expected_category_occurrences=%d",
            reason,
            len(raw_products),
            len(categories),
            expected_category_occurrences,
        )

        synced_products = self.sync_products(
            raw_products,
            full_sync=full_mode,
            allow_prune=complete,
            expected_products=len(coverage_products) if full_mode else 0,
            expected_category_occurrences=expected_category_occurrences,
        )
        self._propagate_synced_fields(raw_products, synced_products)
        self._attach_category_coverage(
            raw_products,
            self._consolidate_for_coverage(raw_products),
            categories,
        )
        self.last_sync_result.errors = list(
            dict.fromkeys(self.last_sync_result.errors)
        )
        self.last_sync_result.finish()
        self._write_final_result_artifact(raw_products)
        _log_timing(
            "SCRAPING TIMING | stage=sync_categories_total | categories=%d | "
            "products=%d | seconds=%.3f",
            len(categories),
            len(raw_products),
            time.perf_counter() - total_started,
        )
        return raw_products

    def sync_products(
        self,
        products,
        full_sync=False,
        allow_prune=False,
        expected_products=0,
        expected_category_occurrences=0,
    ):
        total_started = time.perf_counter()
        if self.mapper and self.catalog_sync_service:
            started = time.perf_counter()
            consolidate = getattr(
                self.catalog_sync_service, "consolidate_products", None
            )
            if callable(consolidate):
                products = cast(list[Any], consolidate(deepcopy(products)))
            _log_timing(
                "SCRAPING TIMING | stage=consolidation | products=%d | seconds=%.3f",
                len(products),
                time.perf_counter() - started,
            )
            if self.image_sync_adapter:
                started = time.perf_counter()
                products = cast(
                    list[Any], self.image_sync_adapter.sync_products(products)
                )
                _log_timing(
                    "SCRAPING TIMING | stage=images | products=%d | seconds=%.3f",
                    len(products),
                    time.perf_counter() - started,
                )
            started = time.perf_counter()
            mapped_products = [self.mapper.map(product) for product in products]
            _log_timing(
                "SCRAPING TIMING | stage=mapping | products=%d | seconds=%.3f",
                len(mapped_products),
                time.perf_counter() - started,
            )
            started = time.perf_counter()
            use_prune = bool(full_sync and allow_prune and expected_products)
            sync_full = getattr(self.catalog_sync_service, "sync_full_catalog", None)
            if use_prune and callable(sync_full):
                result = cast(
                    SyncResult,
                    sync_full(
                        mapped_products,
                        expected_products=expected_products,
                        expected_category_occurrences=expected_category_occurrences,
                    ),
                )
            else:
                result = cast(
                    SyncResult,
                    self.catalog_sync_service.sync(
                        mapped_products,
                        prune_missing=False,
                        expected_products=expected_products,
                        expected_category_occurrences=expected_category_occurrences,
                    ),
                )
            _log_timing(
                "SCRAPING TIMING | stage=catalog_sync | products=%d | seconds=%.3f | "
                "prune=%s | expected_unique=%s | expected_category_occurrences=%s | "
                "unique=%d | gap=%d",
                len(mapped_products),
                time.perf_counter() - started,
                str(use_prune).lower(),
                expected_products if expected_products else "unknown",
                expected_category_occurrences
                if expected_category_occurrences
                else "unknown",
                result.products_unique,
                result.coverage_gap,
            )
            _log_timing(
                "SCRAPING TIMING | stage=sync_total | products=%d | seconds=%.3f",
                len(mapped_products),
                time.perf_counter() - total_started,
            )
            self._accumulate_sync_result(result)
            return mapped_products

        started = time.perf_counter()
        result = self.persistence_service.save_products(products)
        _log_timing(
            "SCRAPING TIMING | stage=persistence | products=%d | seconds=%.3f",
            len(products),
            time.perf_counter() - started,
        )
        _log_timing(
            "SCRAPING TIMING | stage=sync_total | products=%d | seconds=%.3f",
            len(products),
            time.perf_counter() - total_started,
        )
        return result

    @staticmethod
    def _propagate_synced_fields(raw_products, synced_products):
        """Devuelve al objeto scrapeado los campos enriquecidos durante sync."""
        synced_by_code = {}
        for product in synced_products or []:
            code = str(getattr(product, "code", "")).strip()
            if code:
                synced_by_code[code.casefold()] = product

        for raw_product in raw_products or []:
            code = str(getattr(raw_product, "code", "")).strip()
            if not code:
                continue
            synced_product = synced_by_code.get(code.casefold())
            if synced_product is None:
                continue
            for field in ("image_path", "image_hash", "content_hash"):
                value = getattr(synced_product, field, "")
                if value:
                    setattr(raw_product, field, value)

    def _accumulate_sync_result(self, result):
        for field in (
            "processed",
            "created",
            "updated",
            "unchanged",
            "deleted",
            "generated",
            "products_found",
            "products_unique",
            "products_multiple_categories",
            "duplicate_occurrences",
        ):
            setattr(
                self.last_sync_result,
                field,
                getattr(self.last_sync_result, field, 0)
                + getattr(result, field, 0),
            )
        self.last_sync_result.products_expected = max(
            getattr(self.last_sync_result, "products_expected", 0),
            getattr(result, "products_expected", 0),
        )
        self.last_sync_result.expected_category_occurrences = max(
            getattr(self.last_sync_result, "expected_category_occurrences", 0),
            getattr(result, "expected_category_occurrences", 0),
        )
        self.last_sync_result.missing_code = (
            getattr(self.last_sync_result, "missing_code", 0)
            + getattr(result, "missing_code", 0)
        )
        self.last_sync_result.errors.extend(getattr(result, "errors", []))
        self.last_sync_result.changes.extend(getattr(result, "changes", []))
        if getattr(result, "category_summary", None):
            self.last_sync_result.category_summary = list(result.category_summary)
        if getattr(result, "multiple_category_products", None):
            self.last_sync_result.multiple_category_products = list(
                result.multiple_category_products
            )

    def _attach_category_coverage(self, raw_products, products, categories):
        del products
        category_summary = []
        multiple = []
        for category in categories:
            category_name = canonical_category_name(
                str(getattr(category, "name", "")).strip()
            )
            expected = max(int(getattr(category, "expected_count", 0) or 0), 0)
            category_key = normalize_category_name(category_name)
            category_products = [
                product
                for product in raw_products
                if category_key
                and category_key in {
                    normalize_category_name(value)
                    for value in split_category_names(
                        getattr(product, "category", "")
                    )
                }
            ]
            unique = {
                str(getattr(product, "code", "")).strip().casefold()
                for product in category_products
                if str(getattr(product, "code", "")).strip()
            }
            category_summary.append(
                {
                    "category": category_name,
                    "expected": expected,
                    "products": len(category_products),
                    "unique_products": len(unique),
                    "gap": max(expected - len(category_products), 0),
                }
            )
        by_code = {}
        for product in raw_products:
            code = str(getattr(product, "code", "")).strip()
            if code:
                by_code.setdefault(code.casefold(), []).append(product)
        for code, occurrences in by_code.items():
            category_keys = set()
            category_names = []
            for product in occurrences:
                for category_name in split_category_names(
                    getattr(product, "category", "")
                ):
                    normalized = normalize_category_name(category_name)
                    if not normalized or normalized in category_keys:
                        continue
                    category_keys.add(normalized)
                    display_name = canonical_category_name(category_name)
                    if display_name and display_name not in category_names:
                        category_names.append(display_name)
            if len(category_keys) > 1:
                multiple.append(
                    {
                        "code": str(getattr(occurrences[0], "code", code)).strip(),
                        "name": str(getattr(occurrences[0], "name", "")).strip(),
                        "categories": category_names,
                    }
                )
        self.last_sync_result.category_summary = category_summary
        self.last_sync_result.multiple_category_products = multiple
        self.last_sync_result.products_multiple_categories = len(multiple)
        self.last_sync_result.products_found = len(raw_products)
        self.last_sync_result.products_unique = len(
            {
                str(getattr(product, "code", "")).strip()
                for product in raw_products
                if str(getattr(product, "code", "")).strip()
            }
        )
        self.last_sync_result.duplicate_occurrences = max(
            self.last_sync_result.products_found
            - self.last_sync_result.products_unique,
            0,
        )
        for row in self.last_sync_result.category_summary:
            _log_timing(
                "SCRAPING TIMING | stage=category_coverage | "
                "category=%s | products=%d | unique=%d",
                row["category"],
                row["products"],
                row["unique_products"],
            )
        _log_timing(
            "SCRAPING TIMING | stage=multi_category_coverage | "
            "products=%d | categories=%d",
            len(multiple),
            len(self.last_sync_result.category_summary),
        )

    def _write_final_result_artifact(self, raw_products):
        writer = getattr(self.catalog_sync_service, "result_writer", None)
        if writer is None:
            return
        self.last_sync_result.finish()
        codes = {
            str(getattr(product, "code", "")).strip().upper().casefold()
            for product in raw_products
            if str(getattr(product, "code", "")).strip()
        }
        writer.write(self.last_sync_result, codes)

    def _consolidate_for_coverage(self, products) -> list[Any]:
        if self.catalog_sync_service:
            consolidate = getattr(
                self.catalog_sync_service, "consolidate_products", None
            )
            if callable(consolidate):
                return cast(list[Any], consolidate(deepcopy(products)))
        return list(products)

    def _collect_category(self, index, category):
        del index
        scraper = getattr(self.scraper_service, "scraper", None)
        collect = getattr(scraper, "collect_category", None)
        if callable(collect):
            return collect(category)
        return self.scraper_service.scrape_category(
            category.url,
            category.name,
            expected_count=max(int(getattr(category, "expected_count", 0) or 0), 0),
        )

    def _enrich_category(self, index, category, collected):
        del index
        scraper = getattr(self.scraper_service, "scraper", None)
        enrich = getattr(scraper, "enrich_category_products", None)
        if callable(enrich):
            return enrich(collected, category.name)
        return self.scraper_service.scrape_category(
            category.url,
            category.name,
            expected_count=max(int(getattr(category, "expected_count", 0) or 0), 0),
        )

    def _enable_thread_sessions(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        if scraper is None:
            return
        browser = getattr(scraper, "browser", None)
        if browser is None:
            category_scraper = getattr(scraper, "category_scraper", None)
            browser = getattr(category_scraper, "browser", None)
        enable = getattr(browser, "enable_thread_sessions", None)
        if callable(enable):
            enable()

    def _reset_scraping_metrics(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        reset = getattr(scraper, "reset_metrics", None)
        if callable(reset):
            reset()

    def _log_detail_metrics(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        metrics = getattr(scraper, "get_detail_metrics", None)
        if not callable(metrics):
            return
        values = metrics() or {}
        _log_timing(
            "SCRAPING TIMING | stage=detail_cache | requests=%d | cache_hits=%d | cache_size=%d",
            int(values.get("requests", 0) or 0),
            int(values.get("cache_hits", 0) or 0),
            int(values.get("cache_size", 0) or 0),
        )

    def _log_http_metrics(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        metrics = getattr(scraper, "get_http_metrics", None)
        if not callable(metrics):
            return
        values = metrics() or {}
        _log_timing(
            "SCRAPING TIMING | stage=http | requests=%d | retries=%d | "
            "errors=%d | empty=%d | other=%d",
            int(values.get("requests", 0) or 0),
            int(values.get("retries", 0) or 0),
            int(values.get("errors", 0) or 0),
            int(values.get("empty_responses", 0) or 0),
            int(values.get("other_requests", 0) or 0),
        )

    @staticmethod
    def _full_sync_prune_guard(
        products,
        category_count,
        *,
        expected_category_occurrences=0,
        expected_products=0,
    ):
        if not products:
            return False, "no_products"
        if category_count <= 0:
            return False, "no_categories"
        actual_occurrences = len(products)
        expected_occurrences = max(int(expected_category_occurrences or 0), 0)
        if expected_occurrences > 0 and actual_occurrences < expected_occurrences:
            return (
                False,
                f"category_coverage {actual_occurrences}/{expected_occurrences}",
            )
        if expected_products > 0:
            unique_codes = {
                str(getattr(product, "code", "")).strip().casefold()
                for product in products
                if str(getattr(product, "code", "")).strip()
            }
            if len(unique_codes) < expected_products:
                return (
                    False,
                    f"unique_coverage {len(unique_codes)}/{expected_products}",
                )
        return True, "complete"
