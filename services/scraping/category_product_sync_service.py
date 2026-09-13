from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import requests

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
        self._occurrence_categories = []
        self._scraping_mode: str = "directed"

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
        self._occurrence_categories = []
        expected_category_occurrences = sum(
            max(int(getattr(category, "expected_count", 0) or 0), 0)
            for category in categories
        )
        self.last_sync_result = SyncResult()
        self.last_sync_result.products_expected = 0
        self.last_sync_result.expected_category_occurrences = expected_category_occurrences

        collected_by_index: list[list[Any]] = [[] for _ in categories]
        failed_category_errors: dict[int, str] = {}
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
                    category = categories[index]
                    try:
                        collected_by_index[index] = cast(list[Any], future.result())
                    except requests.exceptions.RequestException as error:
                        collected_by_index[index] = []
                        category_name = str(
                            getattr(category, "name", "")
                        ).strip() or "(sin nombre)"
                        message = (
                            f"Error de red en categoría '{category_name}': "
                            f"{error}"
                        )
                        failed_category_errors[index] = message
                        self.last_sync_result.errors.append(message)
                        _log_timing(
                            "SCRAPING TIMING | stage=category_error | category=%s | "
                            "error_type=%s | error=%s",
                            category_name,
                            type(error).__name__,
                            str(error),
                        )
                    if progress_callback:
                        progress_callback(index + 1, len(categories))

        if failed_category_errors:
            recovery_started = time.perf_counter()
            recovered = 0
            recovery_worker_count = min(
                SCRAPING_CATEGORY_WORKERS,
                len(failed_category_errors),
            )
            with ThreadPoolExecutor(max_workers=recovery_worker_count) as executor:
                futures = {
                    executor.submit(
                        self._collect_category,
                        index,
                        categories[index],
                    ): index
                    for index in failed_category_errors
                }
                for future, index in futures.items():
                    category = categories[index]
                    original_error = failed_category_errors[index]
                    category_name = str(getattr(category, "name", "")).strip() or "(sin nombre)"
                    try:
                        collected_by_index[index] = cast(list[Any], future.result())
                    except requests.exceptions.RequestException as error:
                        _log_timing(
                            "SCRAPING TIMING | stage=category_recovery_error | category=%s | "
                            "error_type=%s | error=%s",
                            category_name,
                            type(error).__name__,
                            str(error),
                        )
                        self.last_sync_result.errors.append(
                            f"Reintento fallido en categoría '{category_name}': {error}"
                        )
                    else:
                        recovered += 1
                        self.last_sync_result.errors = [
                            message
                            for message in self.last_sync_result.errors
                            if message != original_error
                        ]
                        _log_timing(
                            "SCRAPING TIMING | stage=category_recovered | category=%s | products=%d",
                            category_name,
                            len(collected_by_index[index]),
                        )
            _log_timing(
                "SCRAPING TIMING | stage=category_recovery | attempted=%d | recovered=%d | seconds=%.3f",
                len(failed_category_errors),
                recovered,
                time.perf_counter() - recovery_started,
            )

        _log_timing(
            "SCRAPING TIMING | stage=category_listing | categories=%d | products=%d | expected_category_occurrences=%d | seconds=%.3f",
            len(categories),
            sum(len(items) for items in collected_by_index),
            expected_category_occurrences,
            time.perf_counter() - started,
        )

        started = time.perf_counter()
        enriched_by_index: list[list[Any] | None] = [None] * len(categories)
        if categories:
            worker_count = min(SCRAPING_CATEGORY_WORKERS, len(categories))
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(
                        self._enrich_category,
                        index,
                        category,
                        collected_by_index[index],
                    ): index
                    for index, category in enumerate(categories)
                }
                for future, index in futures.items():
                    enriched_by_index[index] = cast(list[Any], future.result())

        products = []
        for index, category in enumerate(categories):
            enriched = enriched_by_index[index] or []
            for product in enriched:
                self._record_category_occurrence(product, category.name)
            products.extend(enriched)
        _log_timing(
            "SCRAPING TIMING | stage=category_extraction | categories=%d | products=%d | expected_category_occurrences=%d | seconds=%.3f",
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
            "SCRAPING TIMING | stage=coverage_incomplete | reason=%s | products=%d | categories=%d | expected_category_occurrences=%d",
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
        self.last_sync_result.errors = list(dict.fromkeys(self.last_sync_result.errors))
        self.last_sync_result.finish()
        self._write_final_result_artifact(raw_products)
        _log_timing(
            "SCRAPING TIMING | stage=sync_categories_total | categories=%d | products=%d | seconds=%.3f",
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
            consolidate = getattr(self.catalog_sync_service, "consolidate_products", None)
            if callable(consolidate):
                products = cast(list[Any], consolidate(deepcopy(products)))
            _log_timing(
                "SCRAPING TIMING | stage=consolidation | products=%d | seconds=%.3f",
                len(products),
                time.perf_counter() - started,
            )
            if self.image_sync_adapter:
                started = time.perf_counter()
                products = cast(list[Any], self.image_sync_adapter.sync_products(products))
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
                "SCRAPING TIMING | stage=catalog_sync | products=%d | seconds=%.3f | prune=%s | expected_unique=%s | expected_category_occurrences=%s | unique=%d | gap=%d",
                len(mapped_products),
                time.perf_counter() - started,
                str(use_prune).lower(),
                expected_products if expected_products else "unknown",
                expected_category_occurrences if expected_category_occurrences else "unknown",
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
            "processed", "created", "updated", "unchanged", "deleted", "generated",
            "products_found", "products_unique", "products_multiple_categories",
            "duplicate_occurrences",
        ):
            setattr(
                self.last_sync_result,
                field,
                getattr(self.last_sync_result, field, 0) + getattr(result, field, 0),
            )
        self.last_sync_result.products_expected = max(
            getattr(self.last_sync_result, "products_expected", 0),
            getattr(result, "products_expected", 0),
        )
        self.last_sync_result.expected_category_occurrences = max(
            getattr(self.last_sync_result, "expected_category_occurrences", 0),
            getattr(result, "expected_category_occurrences", 0),
        )
        self.last_sync_result.missing_code += getattr(result, "missing_code", 0)
        self.last_sync_result.errors.extend(getattr(result, "errors", []))
        self.last_sync_result.changes.extend(getattr(result, "changes", []))
        if getattr(result, "category_summary", None):
            self.last_sync_result.category_summary = list(result.category_summary)
        if getattr(result, "multiple_category_products", None):
            self.last_sync_result.multiple_category_products = list(result.multiple_category_products)

    def _record_category_occurrence(self, product, category_name):
        code = str(getattr(product, "code", "")).strip()
        if not code:
            return
        canonical_name = canonical_category_name(str(category_name or "").strip())
        normalized = normalize_category_name(canonical_name)
        if not normalized:
            return
        self._occurrence_categories.append(
            {
                "code": code,
                "code_key": code.casefold(),
                "category": canonical_name,
                "category_key": normalized,
            }
        )

    def _category_summary(self, raw_products, categories, legacy_call):
        has_occurrences = bool(self._occurrence_categories)
        return [
            self._build_category_summary_row(
                raw_products,
                category,
                legacy_call,
                has_occurrences,
            )
            for category in categories
        ]

    def _build_category_summary_row(
        self,
        raw_products,
        category,
        legacy_call,
        has_occurrences,
    ):
        category_name = canonical_category_name(str(getattr(category, "name", "")).strip())
        expected = max(int(getattr(category, "expected_count", 0) or 0), 0)
        category_key = normalize_category_name(category_name)