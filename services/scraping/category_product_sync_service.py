from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import requests
from bs4 import BeautifulSoup

from models.scraping.sync_result import SyncResult
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.category_name_normalizer import (
    canonical_category_name,
    normalize_category_name,
    split_category_names,
)
from services.scraping.full_sync_coverage_policy import (
    demonstrates_complete_coverage,
    has_complete_category_coverage,
)
from services.scraping.page_metrics_audit import record_page_metrics

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
        category_workers=16,
    ):
        self.scraper_service = scraper_service
        self.persistence_service = persistence_service
        self.mapper = mapper
        self.catalog_sync_service = catalog_sync_service
        self.image_sync_adapter = image_sync_adapter
        self.category_workers = int(category_workers)
        if self.category_workers <= 0:
            raise ValueError("category_workers debe ser mayor que cero.")
        self.last_sync_result = SyncResult()
        self._occurrence_categories = []
        self._full_sync_coverage_validated = None
        self._full_sync_coverage_reason = ""
        self._scraping_mode = "directed"

    def reset_sync_result(self):
        self.last_sync_result = SyncResult()

    def set_scraping_mode(self, mode: str) -> None:
        """Define el modo de ejecución usando una interfaz pública estable."""
        normalized = str(mode or "directed").strip().casefold()
        if normalized not in {"directed", "full"}:
            raise ValueError("mode debe ser 'directed' o 'full'.")
        self._scraping_mode = normalized

    def scraping_mode(self) -> str:
        """Devuelve el modo de ejecución actual."""
        return self._scraping_mode

    @staticmethod
    def _split_categories(value: object) -> list[str]:
        """Mantiene la API histórica delegando en el normalizador canónico."""
        return split_category_names(value)

    @staticmethod
    def _product_category_keys(product: Any) -> set[str]:
        return {
            normalize_category_name(category)
            for category in split_category_names(str(getattr(product, "category", "")))
            if normalize_category_name(category)
        }

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
        self._full_sync_coverage_validated = None
        self._full_sync_coverage_reason = ""
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
            worker_count = min(self.category_workers, len(categories))
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(self._collect_category, index, category): index
                    for index, category in enumerate(categories)
                }
                for completed_count, future in enumerate(as_completed(futures), start=1):
                    index = futures[future]
                    category = categories[index]
                    try:
                        collected_by_index[index] = cast(list[Any], future.result())
                    except requests.exceptions.RequestException as error:
                        collected_by_index[index] = []
                        category_name = str(getattr(category, "name", "")).strip() or "(sin nombre)"
                        message = f"Error de red en categoría '{category_name}': {error}"
                        failed_category_errors[index] = message
                        self.last_sync_result.errors.append(message)
                        _log_timing(
                            "SCRAPING TIMING | stage=category_error | category=%s | error_type=%s | error=%s",
                            category_name,
                            type(error).__name__,
                            str(error),
                        )
                    if progress_callback:
                        progress_callback(completed_count, len(categories))

        if failed_category_errors:
            recovery_started = time.perf_counter()
            recovered = 0
            recovery_worker_count = min(self.category_workers, len(failed_category_errors))
            with ThreadPoolExecutor(max_workers=recovery_worker_count) as executor:
                futures = {
                    executor.submit(self._collect_category, index, categories[index]): index
                    for index in failed_category_errors
                }
                for future in as_completed(futures):
                    index = futures[future]
                    category = categories[index]
                    original_error = failed_category_errors[index]
                    category_name = str(getattr(category, "name", "")).strip() or "(sin nombre)"
                    try:
                        collected_by_index[index] = cast(list[Any], future.result())
                    except requests.exceptions.RequestException as error:
                        _log_timing(
                            "SCRAPING TIMING | stage=category_recovery_error | category=%s | error_type=%s | error=%s",
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
                            message for message in self.last_sync_result.errors
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
            worker_count = min(self.category_workers, len(categories))
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
                enrichment_completed = 0
                for future in as_completed(futures):
                    index = futures[future]
                    enriched_by_index[index] = cast(list[Any], future.result())
                    enrichment_completed += 1
                    if progress_callback:
                        progress_callback(
                            len(categories) + enrichment_completed,
                            len(categories) * 2,
                        )

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
        started = time.perf_counter()
        coverage_products = self._consolidate_for_coverage(raw_products)
        self._attach_category_coverage(raw_products, coverage_products, categories)
        _log_timing(
            "SCRAPING TIMING | stage=coverage_pre_sync | products=%d | unique=%d | seconds=%.3f",
            len(raw_products),
            len(coverage_products),
            time.perf_counter() - started,
        )

        full_mode = self.scraping_mode() == "full"
        started = time.perf_counter()
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
            "SCRAPING TIMING | stage=coverage_guard | complete=%s | reason=%s | seconds=%.3f",
            str(bool(complete)).lower(),
            reason,
            time.perf_counter() - started,
        )
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

        started = time.perf_counter()
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
            "SCRAPING TIMING | stage=post_sync_finalize | products=%d | synced=%d | seconds=%.3f",
            len(raw_products),
            len(synced_products),
            time.perf_counter() - started,
        )
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
        coverage_validated = self._full_sync_coverage_validated
        if full_sync and coverage_validated is False:
            has_summary = bool(
                getattr(self.last_sync_result, "category_summary", None)
            )
            recovered = has_summary and self._demonstrates_complete_coverage(
                products,
                expected_products=expected_products,
                expected_category_occurrences=expected_category_occurrences,
            )
            if not recovered:
                reason = str(self._full_sync_coverage_reason or "unknown")
                self.last_sync_result.errors.append(
                    "Cobertura del catálogo incompleta: "
                    f"sincronización FULL omitida por seguridad ({reason})."
                )
                return list(products or [])
            allow_prune = True
            self._full_sync_coverage_validated = True
            self._full_sync_coverage_reason = "complete"

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

    def _build_category_summary_row(self, raw_products, category, legacy_call, has_occurrences):
        category_name = canonical_category_name(str(getattr(category, "name", "")).strip())
        expected = max(int(getattr(category, "expected_count", 0) or 0), 0)
        category_key = normalize_category_name(category_name)
        if has_occurrences:
            occurrences = [
                occurrence
                for occurrence in self._occurrence_categories
                if occurrence["category_key"] == category_key
            ]
            products_found = len(occurrences)
            unique = {occurrence["code_key"] for occurrence in occurrences}
        else:
            category_products = [
                product
                for product in raw_products
                if str(getattr(product, "category", "")).strip()
                and category_key in self._product_category_keys(product)
            ]
            products_found = len(category_products)
            unique = {
                str(getattr(product, "code", "")).strip().casefold()
                for product in category_products
                if str(getattr(product, "code", "")).strip()
            }
        if legacy_call:
            return {
                "category": category_name,
                "comparison_key": category_key,
                "products": products_found,
                "unique_products": len(unique),
            }
        return {
            "category": category_name,
            "expected": expected,
            "products": products_found,
            "unique_products": len(unique),
            "gap": max(expected - products_found, 0),
        }

    def _multiple_category_products(self, raw_products, categories=None):
        by_code = {}
        for occurrence in self._occurrence_categories:
            by_code.setdefault(occurrence["code_key"], {}).setdefault(
                occurrence["category_key"], occurrence["category"]
            )
        if not by_code and categories:
            requested = {
                normalize_category_name(canonical_category_name(getattr(category, "name", "")))
                for category in categories
            }
            for product in raw_products or []:
                code_key = str(getattr(product, "code", "")).strip().casefold()
                if not code_key:
                    continue
                raw_category = str(getattr(product, "category", "")).strip()
                category_key = normalize_category_name(canonical_category_name(raw_category))
                if category_key not in requested:
                    continue
                by_code.setdefault(code_key, {}).setdefault(
                    category_key,
                    canonical_category_name(raw_category),
                )

        product_by_code = {
            str(getattr(product, "code", "")).strip().casefold(): product
            for product in raw_products or []
            if str(getattr(product, "code", "")).strip()
        }
        multiple = []
        for code_key, categories_by_key in by_code.items():
            if len(categories_by_key) <= 1:
                continue
            product = product_by_code.get(code_key)
            if product is None:
                continue
            multiple.append(
                {
                    "code": str(getattr(product, "code", "")).strip(),
                    "name": str(getattr(product, "name", "")).strip(),
                    "categories": list(categories_by_key.values()),
                }
            )
        return multiple

    def _attach_category_coverage(self, raw_products, products_or_categories, categories=None):
        legacy_call = categories is None
        categories = list(products_or_categories or []) if legacy_call else list(categories or [])
        del products_or_categories

        self.last_sync_result.categories_processed = len(categories)
        category_summary = self._category_summary(raw_products, categories, legacy_call)
        multiple = self._multiple_category_products(raw_products, None if legacy_call else categories)
        self.last_sync_result.category_summary = category_summary
        self.last_sync_result.multiple_category_products = multiple
        self.last_sync_result.products_multiple_categories = len(multiple)
        self.last_sync_result.products_found = len(raw_products or [])
        self.last_sync_result.products_unique = len({
            str(getattr(product, "code", "")).strip().casefold()
            for product in raw_products or []
            if str(getattr(product, "code", "")).strip()
        })
        self.last_sync_result.duplicate_occurrences = max(
            self.last_sync_result.products_found - self.last_sync_result.products_unique,
            0,
        )
        for row in self.last_sync_result.category_summary:
            _log_timing(
                "SCRAPING TIMING | stage=category_coverage | category=%s | products=%d | unique=%d",
                row["category"], row["products"], row["unique_products"],
            )
        _log_timing(
            "SCRAPING TIMING | stage=multi_category_coverage | products=%d | categories=%d",
            len(multiple), len(self.last_sync_result.category_summary),
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
            consolidate = getattr(self.catalog_sync_service, "consolidate_products", None)
            if callable(consolidate):
                return cast(list[Any], consolidate(deepcopy(products)))
        return list(products)

    def _collect_category(self, index, category):
        del index
        scraper = getattr(self.scraper_service, "scraper", None)
        collect = getattr(scraper, "collect_category", None)
        if callable(collect):
            products = collect(category)
            get_page_metrics = getattr(scraper, "get_page_metrics", None)
            if callable(get_page_metrics):
                metrics = cast(dict[str, dict[str, Any]], get_page_metrics())
                record_page_metrics(metrics, category_url=category.url)
            return products
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
            result = enrich(collected, category.name)
            get_enrichment_metrics = getattr(scraper, "get_enrichment_metrics", None)
            if callable(get_enrichment_metrics):
                metrics = cast(dict[str, Any], get_enrichment_metrics(category.name) or {})
                if metrics:
                    _log_timing(
                        "SCRAPING TIMING | stage=category_enrichment_summary | category=%s | requested=%d | skipped=%d | total_seconds=%.3f | submit_seconds=%.3f | wait_seconds=%.3f",
                        str(category.name).strip() or "(sin nombre)",
                        int(metrics.get("requested", 0) or 0),
                        int(metrics.get("skipped", 0) or 0),
                        float(metrics.get("total_seconds", 0.0) or 0.0),
                        float(metrics.get("submit_seconds", 0.0) or 0.0),
                        float(metrics.get("wait_seconds", 0.0) or 0.0),
                    )
            return result
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
        values = cast(dict[str, Any], metrics() or {})
        _log_timing(
            "SCRAPING TIMING | stage=detail_cache | requests=%d | cache_hits=%d | cache_size=%d | skipped=%d",
            int(values.get("detail_requests", 0) or 0),
            int(values.get("detail_cache_hits", 0) or 0),
            int(values.get("detail_cache_size", 0) or 0),
            int(values.get("detail_skipped", 0) or 0),
        )

    def _log_http_metrics(self):
        browser = self._browser()
        metrics = getattr(browser, "get_http_metrics", None)
        if not callable(metrics):
            return
        values = cast(dict[str, Any], metrics() or {})
        buckets = values.get("latency_buckets", {}) or {}
        slowest = values.get("slowest_requests", []) or []
        slowest_text = ";".join(f"{float(elapsed):.3f}s:{url}" for elapsed, url in slowest)
        _log_timing(
            "SCRAPING TIMING | stage=http | requests=%d | category=%d | jsf=%d | detail=%d | other=%d | retries=%d | errors=%d | terminal=%d | retry_sleep_count=%d | retry_sleep_seconds=%.3f | total_seconds=%.3f | max_seconds=%.3f | max_concurrency=%d | category_total_seconds=%.3f | jsf_total_seconds=%.3f | detail_total_seconds=%.3f | other_total_seconds=%.3f | category_max_seconds=%.3f | jsf_max_seconds=%.3f | detail_max_seconds=%.3f | other_max_seconds=%.3f | lt_0_5=%d | 0_5_1=%d | 1_2=%d | 2_5=%d | 5_10=%d | gte_10=%d | slowest=%s",
            int(values.get("http_requests", 0) or 0),
            int(values.get("category_http_requests", 0) or 0),
            int(values.get("jsf_http_requests", 0) or 0),
            int(values.get("detail_http_requests", 0) or 0),
            int(values.get("other_http_requests", 0) or 0),
            int(values.get("http_retries", 0) or 0),
            int(values.get("http_errors", 0) or 0),
            int(values.get("http_terminal_errors", 0) or 0),
            int(values.get("http_retry_sleep_count", 0) or 0),
            float(values.get("http_retry_sleep_seconds", 0.0) or 0.0),
            float(values.get("http_total_seconds", 0.0) or 0.0),
            float(values.get("http_max_seconds", 0.0) or 0.0),
            int(values.get("http_max_in_flight", 0) or 0),
            float(values.get("category_http_total_seconds", 0.0) or 0.0),
            float(values.get("jsf_http_total_seconds", 0.0) or 0.0),
            float(values.get("detail_http_total_seconds", 0.0) or 0.0),
            float(values.get("other_http_total_seconds", 0.0) or 0.0),
            float(values.get("category_http_max_seconds", 0.0) or 0.0),
            float(values.get("jsf_http_max_seconds", 0.0) or 0.0),
            float(values.get("detail_http_max_seconds", 0.0) or 0.0),
            float(values.get("other_http_max_seconds", 0.0) or 0.0),
            int(buckets.get("lt_0_5", 0) or 0),
            int(buckets.get("0_5_1", 0) or 0),
            int(buckets.get("1_2", 0) or 0),
            int(buckets.get("2_5", 0) or 0),
            int(buckets.get("5_10", 0) or 0),
            int(buckets.get("gte_10", 0) or 0),
            slowest_text,
        )

    def _browser(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        browser = getattr(scraper, "browser", None)
        if browser is not None:
            return browser
        category_scraper = getattr(scraper, "category_scraper", None)
        return getattr(category_scraper, "browser", None)

    def _browser_for_sku_recovery(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        if scraper is None:
            return None
        browser = getattr(scraper, "browser", None)
        if browser is not None:
            return browser
        category_scraper = getattr(scraper, "category_scraper", None)
        return getattr(category_scraper, "browser", None)

    @staticmethod
    def _recover_one_missing_code(product, browser, extractor: ProductExtractor) -> bool:
        code = str(getattr(product, "code", "") or "").strip()
        if code:
            return False
        url = str(getattr(product, "url", "") or "").strip()
        if "/producto/" not in url:
            return False
        try:
            html = browser.get(url)
        except requests.RequestException:
            return False
        if not isinstance(html, str) or not html:
            return False
        soup = BeautifulSoup(html, "lxml")
        recovered_code = str(extractor.extract_code(soup) or "").strip()
        if not recovered_code:
            return False
        product.code = recovered_code.upper()
        return True

    def _recover_missing_codes(self, products) -> int:
        browser = self._browser_for_sku_recovery()
        if browser is None:
            return 0
        missing_products = [
            product for product in products
            if not str(getattr(product, "code", "") or "").strip()
            and "/producto/" in str(getattr(product, "url", "") or "")
        ]
        if not missing_products:
            return 0
        extractor = ProductExtractor()
        recovered = 0
        for product in missing_products:
            if self._recover_one_missing_code(product, browser, extractor):
                recovered += 1
        return recovered

    def _has_complete_category_coverage(self) -> bool:
        return has_complete_category_coverage(self.last_sync_result)

    def _terminal_http_error_reason(self):
        if self._has_complete_category_coverage():
            return None
        browser = self._browser()
        metrics_getter = getattr(browser, "get_http_metrics", None)
        if not callable(metrics_getter):
            return None
        metrics = cast(dict[str, Any], metrics_getter() or {})
        terminal_errors = int(metrics.get("http_terminal_errors", 0) or 0)
        if terminal_errors:
            return f"terminal_http_errors:{terminal_errors}"
        return None

    @staticmethod
    def _category_coverage_gap_reason(category_summary):
        invalid_categories = []
        for row in category_summary:
            expected = max(int(row.get("expected", 0) or 0), 0)
            if expected <= 0:
                continue
            products_found = int(row.get("products", 0) or 0)
            unique_found = int(row.get("unique_products", 0) or 0)
            if products_found < expected or unique_found != products_found:
                invalid_categories.append(str(row.get("category", "(sin nombre)")))
        if not invalid_categories:
            return ""
        return f"category_coverage_gap:{','.join(invalid_categories)}"

    def _full_sync_prune_guard(
        self,
        products,
        category_count,
        *,
        expected_category_occurrences=0,
        expected_products=0,
    ):
        category_summary = getattr(self.last_sync_result, "category_summary", None) or []
        if category_count <= 0:
            self._full_sync_coverage_validated = False
            self._full_sync_coverage_reason = "no_categories"
            return False, self._full_sync_coverage_reason

        self._recover_missing_codes(products)
        raw_products = list(products or [])
        missing_codes = sum(
            1 for product in raw_products
            if not str(getattr(product, "code", "") or "").strip()
        )
        if missing_codes:
            reason = f"missing_codes:{missing_codes}"
            self._full_sync_coverage_validated = False
            self._full_sync_coverage_reason = reason
            return False, reason

        http_reason = self._terminal_http_error_reason()
        if http_reason:
            self._full_sync_coverage_validated = False
            self._full_sync_coverage_reason = http_reason
            return False, http_reason

        gap_reason = self._category_coverage_gap_reason(category_summary)
        if gap_reason:
            self._full_sync_coverage_validated = False
            self._full_sync_coverage_reason = gap_reason
            return False, gap_reason

        if not demonstrates_complete_coverage(
            raw_products,
            expected_products=expected_products,
            expected_category_occurrences=expected_category_occurrences,
            category_summary=category_summary,
        ):
            self._full_sync_coverage_validated = False
            gap = max(expected_category_occurrences - len(raw_products), 0)
            reason = f"category_coverage_gap:{gap}" if gap and not category_summary else "coverage_not_complete"
            self._full_sync_coverage_reason = reason
            return False, reason

        self._full_sync_coverage_validated = True
        self._full_sync_coverage_reason = "complete"
        return True, "complete"

    def _demonstrates_complete_coverage(
        self,
        products,
        *,
        expected_products=0,
        expected_category_occurrences=0,
    ):
        category_summary = getattr(self.last_sync_result, "category_summary", None) or []
        return demonstrates_complete_coverage(
            products,
            expected_products=expected_products,
            expected_category_occurrences=expected_category_occurrences,
            category_summary=category_summary,
        )
