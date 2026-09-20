from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# The profiler deliberately mirrors the existing collect -> enrich orchestration.
from services.scraping.scraping_config import ScrapingConfig
from services.scraping.scraping_factory import ScrapingFactory

OUTPUT_PATH = PROJECT_ROOT / "data" / "scraping_detail_profile.json"


def _positive_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} debe ser mayor que cero.")
    return parsed


def _timed_collect(service: Any, index: int, category: Any) -> tuple[int, list[Any]]:
    return index, service._collect_category(index, category)


def _timed_enrich(
    service: Any,
    index: int,
    category: Any,
    collected: list[Any],
) -> tuple[int, list[Any]]:
    return index, service._enrich_category(index, category, collected)


def _coverage_metrics(
    categories: list[Any],
    enriched: list[list[Any]],
) -> dict[str, Any]:
    code_categories: dict[str, set[str]] = defaultdict(set)
    occurrences = 0
    missing_codes = 0
    expected_occurrences = 0

    for index, category in enumerate(categories):
        category_name = str(getattr(category, "name", "") or "").strip() or "(sin nombre)"
        expected_occurrences += max(
            int(getattr(category, "expected_count", 0) or 0),
            0,
        )
        for product in enriched[index]:
            occurrences += 1
            code = str(getattr(product, "code", "") or "").strip().casefold()
            if not code:
                missing_codes += 1
                continue
            code_categories[code].add(category_name)

    return {
        "expected_occurrences": expected_occurrences,
        "occurrences": occurrences,
        "occurrence_gap": max(expected_occurrences - occurrences, 0),
        "unique_products": len(code_categories),
        "multi_category_products": sum(
            1 for categories_for_code in code_categories.values()
            if len(categories_for_code) >= 2
        ),
        "missing_codes": missing_codes,
    }


# ruff: noqa: PLR0912
# The profiler main() intentionally keeps the orchestration flow together so
# its collect/enrich phase boundaries remain identical to the production flow.
def main() -> int:
    config = ScrapingConfig(download_images=False)
    http_workers = _positive_int("FCM_PROFILE_HTTP_WORKERS")
    detail_workers = _positive_int("FCM_PROFILE_DETAIL_WORKERS")
    jsf_concurrency = _positive_int("FCM_PROFILE_JSF_HTTP_CONCURRENCY")
    if http_workers is not None:
        config.http_workers = http_workers
    if detail_workers is not None:
        config.detail_workers = detail_workers
    if jsf_concurrency is not None:
        config.jsf_http_concurrency = jsf_concurrency
    if (
        http_workers is not None
        or detail_workers is not None
        or jsf_concurrency is not None
    ):
        config.__post_init__()

    runner = ScrapingFactory.create_runner(config)
    category_service = runner.category_service
    if category_service is None:
        raise RuntimeError("ScrapingRunner no tiene CategoryService configurado.")

    service = runner.scraping_service
    scraper = getattr(getattr(service, "scraper_service", None), "scraper", None)
    if scraper is None:
        raise RuntimeError("ScrapingService no tiene scraper configurado.")

    category_scraper = getattr(scraper, "category_scraper", None)
    browser = getattr(category_scraper, "browser", None)
    started = time.perf_counter()
    categories = list(category_service.scrape_all() or [])

    worker_count = min(config.category_workers, len(categories))
    collected: list[list[Any]] = [[] for _ in categories]
    enriched: list[list[Any]] = [[] for _ in categories]

    # Keep the same phase barrier as tools/profile_scraping_categories.py:
    # complete collection for every category before starting enrichment.
    if categories:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_timed_collect, service, index, category): index
                for index, category in enumerate(categories)
            }
            for future in as_completed(futures):
                index, products = future.result()
                collected[index] = products

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    _timed_enrich,
                    service,
                    index,
                    categories[index],
                    collected[index],
                ): index
                for index in range(len(categories))
            }
            for future in as_completed(futures):
                index, products = future.result()
                enriched[index] = products

    detail_metrics: dict[str, Any] = {}
    get_detail_metrics = getattr(scraper, "get_detail_metrics", None)
    if callable(get_detail_metrics):
        detail_metrics = dict(get_detail_metrics() or {})

    http_metrics: dict[str, Any] = {}
    if browser is not None:
        get_http_metrics = getattr(browser, "get_http_metrics", None)
        if callable(get_http_metrics):
            http_metrics = dict(get_http_metrics() or {})

    category_rows: list[dict[str, Any]] = []
    get_enrichment_metrics = getattr(scraper, "get_enrichment_metrics", None)
    for index, category in enumerate(categories):
        category_name = str(getattr(category, "name", "") or "").strip() or "(sin nombre)"
        enrichment = (
            dict(get_enrichment_metrics(category_name) or {})
            if callable(get_enrichment_metrics)
            else {}
        )
        category_rows.append(
            {
                "category": category_name,
                "expected": max(int(getattr(category, "expected_count", 0) or 0), 0),
                "collected": len(collected[index]),
                "enriched": len(enriched[index]),
                "detail_requested": int(enrichment.get("requested", 0) or 0),
                "detail_skipped": int(enrichment.get("skipped", 0) or 0),
                "enrichment_seconds": float(enrichment.get("total_seconds", 0.0) or 0.0),
            }
        )
    category_rows.sort(key=lambda row: row["detail_requested"], reverse=True)

    detail_http_requests = int(http_metrics.get("detail_http_requests", 0) or 0)
    detail_http_total = float(http_metrics.get("detail_http_total_seconds", 0.0) or 0.0)
    coverage = _coverage_metrics(categories, enriched)
    payload = {
        "categories": len(categories),
        "http_workers": config.http_workers,
        "detail_workers": config.detail_workers,
        "jsf_http_concurrency": config.jsf_http_concurrency,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "coverage": coverage,
        "detail": detail_metrics,
        "http": {
            "requests": int(http_metrics.get("http_requests", 0) or 0),
            "detail_requests": detail_http_requests,
            "detail_total_seconds": detail_http_total,
            "detail_avg_seconds": detail_http_total / detail_http_requests
            if detail_http_requests
            else 0.0,
            "max_concurrency": int(http_metrics.get("http_max_in_flight", 0) or 0),
            "errors": int(http_metrics.get("http_errors", 0) or 0),
            "retries": int(http_metrics.get("http_retries", 0) or 0),
        },
        "categories_detail": category_rows,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"categories={len(categories)}")
    print(f"elapsed_seconds={payload['elapsed_seconds']:.3f}")
    print(f"http_workers={config.http_workers}")
    print(f"detail_workers={config.detail_workers}")
    print(f"jsf_http_concurrency={config.jsf_http_concurrency}")
    print(
        "coverage="
        f"expected_occurrences:{coverage['expected_occurrences']} "
        f"occurrences:{coverage['occurrences']} "
        f"gap:{coverage['occurrence_gap']} "
        f"unique:{coverage['unique_products']} "
        f"multi_category:{coverage['multi_category_products']} "
        f"missing_codes:{coverage['missing_codes']}"
    )
    print(f"detail_requests={detail_metrics.get('detail_requests', 0)}")
    print(f"detail_cache_hits={detail_metrics.get('detail_cache_hits', 0)}")
    print(f"detail_skipped={detail_metrics.get('detail_skipped', 0)}")
    print(f"detail_cache_size={detail_metrics.get('detail_cache_size', 0)}")
    print(f"detail_reason_counts={detail_metrics.get('detail_reason_counts', {})}")
    print(f"detail_http_requests={detail_http_requests}")
    print(f"detail_http_total_seconds={detail_http_total:.3f}")
    print(f"detail_http_avg_seconds={payload['http']['detail_avg_seconds']:.3f}")
    print(f"http_errors={payload['http']['errors']} retries={payload['http']['retries']}")
    print(f"output={OUTPUT_PATH}")
    print("category\texpected\tcollected\tenriched\tdetail_req\tdetail_skip\tenrichment_s")
    for row in category_rows:
        print(
            f"{row['category']}\t{row['expected']}\t{row['collected']}\t"
            f"{row['enriched']}\t{row['detail_requested']}\t"
            f"{row['detail_skipped']}\t{row['enrichment_seconds']:.3f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
