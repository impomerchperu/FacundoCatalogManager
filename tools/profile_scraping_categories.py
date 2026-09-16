from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

# The project imports intentionally follow the runtime sys.path bootstrap below.
# This script is designed to run directly from the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ruff: noqa: I001, PLR0912
# The profiler main() is intentionally kept as a single orchestration flow.
from services.scraping.scraping_config import ScrapingConfig
from services.scraping.scraping_factory import ScrapingFactory


OUTPUT_PATH = PROJECT_ROOT / "data" / "scraping_category_profile.json"


def _timed_collect(service: Any, index: int, category: Any) -> tuple[int, float, list[Any]]:
    started = time.perf_counter()
    collected = service._collect_category(index, category)
    return index, time.perf_counter() - started, collected


def _timed_enrich(
    service: Any,
    index: int,
    category: Any,
    collected: list[Any],
) -> tuple[int, float, list[Any]]:
    started = time.perf_counter()
    enriched = service._enrich_category(index, category, collected)
    return index, time.perf_counter() - started, enriched


def _env_positive_int(name: str) -> int | None:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return None
    value = int(raw_value)
    if value <= 0:
        raise ValueError(f"{name} debe ser mayor que cero.")
    return value


def _profile_http_workers() -> int | None:
    return _env_positive_int("FCM_PROFILE_HTTP_WORKERS")


def _profile_jsf_http_concurrency() -> int | None:
    return _env_positive_int("FCM_PROFILE_JSF_HTTP_CONCURRENCY")


def _average(total: float, count: int) -> float:
    return total / count if count else 0.0


def _build_http_payload(http_metrics: dict[str, Any]) -> dict[str, Any]:
    buckets = dict(http_metrics.get("latency_buckets", {}) or {})
    retry_events = list(http_metrics.get("retry_events", []) or [])
    slowest_requests = list(http_metrics.get("slowest_requests", []) or [])

    http_counts = {
        "category": int(http_metrics.get("category_http_requests", 0) or 0),
        "jsf": int(http_metrics.get("jsf_http_requests", 0) or 0),
        "detail": int(http_metrics.get("detail_http_requests", 0) or 0),
        "other": int(http_metrics.get("other_http_requests", 0) or 0),
    }
    http_totals = {
        "category": float(http_metrics.get("category_http_total_seconds", 0.0) or 0.0),
        "jsf": float(http_metrics.get("jsf_http_total_seconds", 0.0) or 0.0),
        "detail": float(http_metrics.get("detail_http_total_seconds", 0.0) or 0.0),
        "other": float(http_metrics.get("other_http_total_seconds", 0.0) or 0.0),
    }
    http_maxes = {
        "category": float(http_metrics.get("category_http_max_seconds", 0.0) or 0.0),
        "jsf": float(http_metrics.get("jsf_http_max_seconds", 0.0) or 0.0),
        "detail": float(http_metrics.get("detail_http_max_seconds", 0.0) or 0.0),
        "other": float(http_metrics.get("other_http_max_seconds", 0.0) or 0.0),
    }
    return {
        "requests": int(http_metrics.get("http_requests", 0) or 0),
        "category_requests": http_counts["category"],
        "jsf_requests": http_counts["jsf"],
        "detail_requests": http_counts["detail"],
        "other_requests": http_counts["other"],
        "retries": int(http_metrics.get("http_retries", 0) or 0),
        "errors": int(http_metrics.get("http_errors", 0) or 0),
        "terminal_errors": int(http_metrics.get("http_terminal_errors", 0) or 0),
        "retry_sleep_count": int(http_metrics.get("http_retry_sleep_count", 0) or 0),
        "retry_sleep_seconds": float(http_metrics.get("http_retry_sleep_seconds", 0.0) or 0.0),
        "total_seconds": float(http_metrics.get("http_total_seconds", 0.0) or 0.0),
        "category_total_seconds": http_totals["category"],
        "jsf_total_seconds": http_totals["jsf"],
        "detail_total_seconds": http_totals["detail"],
        "other_total_seconds": http_totals["other"],
        "category_avg_seconds": _average(http_totals["category"], http_counts["category"]),
        "jsf_avg_seconds": _average(http_totals["jsf"], http_counts["jsf"]),
        "detail_avg_seconds": _average(http_totals["detail"], http_counts["detail"]),
        "other_avg_seconds": _average(http_totals["other"], http_counts["other"]),
        "max_seconds": float(http_metrics.get("http_max_seconds", 0.0) or 0.0),
        "category_max_seconds": http_maxes["category"],
        "jsf_max_seconds": http_maxes["jsf"],
        "detail_max_seconds": http_maxes["detail"],
        "other_max_seconds": http_maxes["other"],
        "max_concurrency": int(http_metrics.get("http_max_in_flight", 0) or 0),
        "latency_buckets": {
            key: int(buckets.get(key, 0) or 0)
            for key in ("lt_0_5", "0_5_1", "1_2", "2_5", "5_10", "gte_10")
        },
        "slowest_requests": slowest_requests,
        "retry_events": retry_events,
    }


def main() -> int:
    profile_http_workers = _profile_http_workers()
    profile_jsf_http_concurrency = _profile_jsf_http_concurrency()
    config = ScrapingConfig(download_images=False)
    if profile_http_workers is not None:
        config.http_workers = profile_http_workers
    if profile_jsf_http_concurrency is not None:
        config.jsf_http_concurrency = profile_jsf_http_concurrency
    if profile_http_workers is not None or profile_jsf_http_concurrency is not None:
        config.__post_init__()

    runner = ScrapingFactory.create_runner(config)
    category_service = runner.category_service
    if category_service is None:
        raise RuntimeError("ScrapingRunner no tiene CategoryService configurado.")

    started = time.perf_counter()
    categories = list(category_service.scrape_all() or [])
    discovery_seconds = time.perf_counter() - started

    service = runner.scraping_service
    category_product_service = getattr(service, "scraper_service", None)
    scraper = getattr(category_product_service, "scraper", None)
    category_scraper = getattr(scraper, "category_scraper", None)
    browser = getattr(category_scraper, "browser", None)
    worker_count = min(config.category_workers, len(categories))
    collected_by_index: list[list[Any]] = [[] for _ in categories]
    listing_seconds: dict[int, float] = {}
    rows: list[dict[str, Any]] = []

    profile_started = time.perf_counter()
    if categories:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_timed_collect, service, index, category): index
                for index, category in enumerate(categories)
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
                    index,
                    categories[index],
                    collected_by_index[index],
                ): index
                for index in range(len(categories))
            }
            for future in as_completed(futures):
                index, seconds, enriched = future.result()
                category = categories[index]
                category_name = str(getattr(category, "name", "") or "").strip() or "(sin nombre)"
                enrichment_metrics: dict[str, Any] = {}
                get_enrichment_metrics = getattr(scraper, "get_enrichment_metrics", None)
                if callable(get_enrichment_metrics):
                    enrichment_metrics = dict(get_enrichment_metrics(category_name) or {})
                unique_codes = {
                    str(getattr(product, "code", "") or "").strip().casefold()
                    for product in enriched
                    if str(getattr(product, "code", "") or "").strip()
                }
                rows.append(
                    {
                        "category": category_name,
                        "expected": max(int(getattr(category, "expected_count", 0) or 0), 0),
                        "collected": len(collected_by_index[index]),
                        "enriched": len(enriched),
                        "unique_codes": len(unique_codes),
                        "listing_seconds": round(listing_seconds[index], 3),
                        "enrichment_seconds": round(seconds, 3),
                        "enrichment_submit_seconds": round(
                            float(enrichment_metrics.get("submit_seconds", 0.0) or 0.0),
                            3,
                        ),
                        "enrichment_wait_seconds": round(
                            float(enrichment_metrics.get("wait_seconds", 0.0) or 0.0),
                            3,
                        ),
                        "detail_requested": int(enrichment_metrics.get("requested", 0) or 0),
                        "detail_skipped": int(enrichment_metrics.get("skipped", 0) or 0),
                        "total_seconds": round(listing_seconds[index] + seconds, 3),
                    }
                )

    http_metrics: dict[str, Any] = {}
    if browser is not None:
        get_http_metrics = getattr(browser, "get_http_metrics", None)
        if callable(get_http_metrics):
            http_metrics = dict(get_http_metrics() or {})
    rows.sort(key=lambda row: row["total_seconds"], reverse=True)
    http_payload = _build_http_payload(http_metrics)
    payload = {
        "categories": len(categories),
        "category_workers": config.category_workers,
        "http_workers": config.http_workers,
        "detail_workers": config.detail_workers,
        "jsf_http_concurrency": config.jsf_http_concurrency,
        "request_timeout": config.request_timeout,
        "download_images": config.download_images,
        "discovery_seconds": round(discovery_seconds, 3),
        "profile_seconds": round(time.perf_counter() - profile_started, 3),
        "http": http_payload,
        "rows": rows,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"categories={len(categories)}")
    print(f"discovery_seconds={discovery_seconds:.3f}")
    print(f"profile_seconds={payload['profile_seconds']:.3f}")
    print(f"http_workers={config.http_workers}")
    print(f"jsf_http_concurrency={config.jsf_http_concurrency}")
    print(f"output={OUTPUT_PATH}")
    http = payload["http"]
    print(
        "http="
        f"requests:{http['requests']} "
        f"category:{http['category_requests']} "
        f"jsf:{http['jsf_requests']} "
        f"detail:{http['detail_requests']} "
        f"other:{http['other_requests']} "
        f"retries:{http['retries']} "
        f"errors:{http['errors']} "
        f"terminal:{http['terminal_errors']} "
        f"retry_sleep_count:{http['retry_sleep_count']} "
        f"retry_sleep_s:{http['retry_sleep_seconds']:.3f} "
        f"total_s:{http['total_seconds']:.3f} "
        f"category_total_s:{http['category_total_seconds']:.3f} "
        f"jsf_total_s:{http['jsf_total_seconds']:.3f} "
        f"detail_total_s:{http['detail_total_seconds']:.3f} "
        f"max_s:{http['max_seconds']:.3f} "
        f"max_concurrency:{http['max_concurrency']}"
    )
    print(
        "http_avg="
        f"category:{http['category_avg_seconds']:.3f} "
        f"jsf:{http['jsf_avg_seconds']:.3f} "
        f"detail:{http['detail_avg_seconds']:.3f} "
        f"other:{http['other_avg_seconds']:.3f}"
    )
    print(
        "http_max="
        f"category:{http['category_max_seconds']:.3f} "
        f"jsf:{http['jsf_max_seconds']:.3f} "
        f"detail:{http['detail_max_seconds']:.3f} "
        f"other:{http['other_max_seconds']:.3f}"
    )
    print(f"latency_buckets={http['latency_buckets']}")
    if http["slowest_requests"]:
        print("slowest_requests=")
        for elapsed, url in http["slowest_requests"][:10]:
            print(f"  {float(elapsed):.3f}s {url}")
    if http["retry_events"]:
        print("retry_events=")
        for event in http["retry_events"]:
            print(
                f"  url={event.get('url')} "
                f"error_type={event.get('error_type')} "
                f"status_code={event.get('status_code')} "
                f"elapsed={float(event.get('elapsed', 0.0)):.3f}s "
                f"attempt={event.get('attempt')}"
            )

    print(
        "category\texpected\tcollected\tenriched\tunique\tlisting_s\t"
        "enrichment_s\tsubmit_s\twait_s\tdetail_req\tdetail_skip\ttotal_s"
    )
    for row in rows:
        print(
            f"{row['category']}\t{row['expected']}\t{row['collected']}\t"
            f"{row['enriched']}\t{row['unique_codes']}\t{row['listing_seconds']:.3f}\t"
            f"{row['enrichment_seconds']:.3f}\t{row['enrichment_submit_seconds']:.3f}\t"
            f"{row['enrichment_wait_seconds']:.3f}\t{row['detail_requested']}\t"
            f"{row['detail_skipped']}\t{row['total_seconds']:.3f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
