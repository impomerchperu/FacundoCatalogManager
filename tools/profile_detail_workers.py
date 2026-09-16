from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.scraping.scraping_config import ScrapingConfig
from services.scraping.scraping_factory import ScrapingFactory


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{name} debe ser mayor que cero.")
    return value


def _timed_collect(service: Any, index: int, category: Any):
    started = time.perf_counter()
    collected = service._collect_category(index, category)
    return index, time.perf_counter() - started, collected


def _timed_enrich(service: Any, index: int, category: Any, collected: list[Any]):
    started = time.perf_counter()
    enriched = service._enrich_category(index, category, collected)
    return index, time.perf_counter() - started, enriched


def main() -> int:
    http_workers = _positive_int("FCM_PROFILE_HTTP_WORKERS", 28)
    jsf_concurrency = _positive_int("FCM_PROFILE_JSF_HTTP_CONCURRENCY", 8)
    detail_workers = _positive_int("FCM_PROFILE_DETAIL_WORKERS", 32)

    config = ScrapingConfig(
        download_images=False,
        http_workers=http_workers,
        jsf_http_concurrency=jsf_concurrency,
        detail_workers=detail_workers,
    )
    runner = ScrapingFactory.create_runner(config)
    category_service = runner.category_service
    if category_service is None:
        raise RuntimeError("ScrapingRunner no tiene CategoryService configurado.")

    service = runner.scraping_service
    scraper = getattr(getattr(service, "scraper_service", None), "scraper", None)
    category_scraper = getattr(scraper, "category_scraper", None)
    browser = getattr(category_scraper, "browser", None)

    started = time.perf_counter()
    categories = list(category_service.scrape_all() or [])
    discovery_seconds = time.perf_counter() - started

    worker_count = min(config.category_workers, len(categories))
    collected_by_index: list[list[Any]] = [[] for _ in categories]
    listing_seconds: dict[int, float] = {}
    enriched_by_index: list[list[Any]] = [[] for _ in categories]
    enrichment_seconds: dict[int, float] = {}

    profile_started = time.perf_counter()
    if categories:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_timed_collect, service, i, category): i
                for i, category in enumerate(categories)
            }
            for future in as_completed(futures):
                index, seconds, collected = future.result()
                collected_by_index[index] = collected
                listing_seconds[index] = seconds

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    _timed_enrich,
                    service,
                    i,
                    categories[i],
                    collected_by_index[i],
                ): i
                for i in range(len(categories))
            }
            for future in as_completed(futures):
                index, seconds, enriched = future.result()
                enriched_by_index[index] = enriched
                enrichment_seconds[index] = seconds

    mismatches: list[str] = []
    total_expected = 0
    total_collected = 0
    total_enriched = 0
    for i, category in enumerate(categories):
        expected = max(int(getattr(category, "expected_count", 0) or 0), 0)
        collected = len(collected_by_index[i])
        enriched = len(enriched_by_index[i])
        total_expected += expected
        total_collected += collected
        total_enriched += enriched
        if collected != expected or enriched != expected:
            mismatches.append(
                f"{getattr(category, 'name', '(sin nombre)')}:"
                f" expected={expected} collected={collected} enriched={enriched}"
            )

    http_metrics = {}
    if browser is not None:
        getter = getattr(browser, "get_http_metrics", None)
        if callable(getter):
            http_metrics = dict(getter() or {})

    print(f"categories={len(categories)}")
    print(f"discovery_seconds={discovery_seconds:.3f}")
    print(f"profile_seconds={time.perf_counter() - profile_started:.3f}")
    print(f"http_workers={http_workers}")
    print(f"jsf_http_concurrency={jsf_concurrency}")
    print(f"detail_workers={detail_workers}")
    print(
        "coverage="
        f"expected:{total_expected} "
        f"collected:{total_collected} "
        f"enriched:{total_enriched} "
        f"complete:{not mismatches}"
    )
    print(
        "http="
        f"requests:{http_metrics.get('http_requests', 0)} "
        f"category:{http_metrics.get('category_http_requests', 0)} "
        f"jsf:{http_metrics.get('jsf_http_requests', 0)} "
        f"detail:{http_metrics.get('detail_http_requests', 0)} "
        f"retries:{http_metrics.get('http_retries', 0)} "
        f"errors:{http_metrics.get('http_errors', 0)} "
        f"max_concurrency:{http_metrics.get('http_max_in_flight', 0)}"
    )
    print(
        "semaphore_wait_by_class="
        f"category:{float(http_metrics.get('category_semaphore_wait_seconds', 0.0) or 0.0):.3f}s "
        f"jsf:{float(http_metrics.get('jsf_semaphore_wait_seconds', 0.0) or 0.0):.3f}s "
        f"detail:{float(http_metrics.get('detail_semaphore_wait_seconds', 0.0) or 0.0):.3f}s"
    )
    if mismatches:
        print("coverage_mismatches=")
        for mismatch in mismatches:
            print(f"  {mismatch}")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
