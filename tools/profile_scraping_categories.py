from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from services.scraping.scraping_config import ScrapingConfig
from services.scraping.scraping_factory import ScrapingFactory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "scraping_category_profile.json"


def _timed_collect(service: Any, index: int, category: Any) -> tuple[int, float, list[Any]]:
    started = time.perf_counter()
    products = service._collect_category(index, category)
    return index, time.perf_counter() - started, products


def _timed_enrich(
    service: Any,
    index: int,
    category: Any,
    products: list[Any],
) -> tuple[int, float, list[Any]]:
    started = time.perf_counter()
    enriched = service._enrich_category(index, category, products)
    return index, time.perf_counter() - started, enriched


def main() -> int:
    config = ScrapingConfig(download_images=False)
    runner = ScrapingFactory.create_runner(config)
    category_service = runner.category_service
    if category_service is None:
        raise RuntimeError("ScrapingRunner no tiene CategoryService configurado.")

    started = time.perf_counter()
    categories = list(category_service.scrape_all() or [])
    discovery_seconds = time.perf_counter() - started

    service = runner.scraping_service
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
                unique_codes = {
                    str(getattr(product, "code", "") or "").strip().casefold()
                    for product in enriched
                    if str(getattr(product, "code", "") or "").strip()
                }
                rows.append(
                    {
                        "category": str(getattr(category, "name", "") or "").strip() or "(sin nombre)",
                        "expected": max(int(getattr(category, "expected_count", 0) or 0), 0),
                        "collected": len(collected_by_index[index]),
                        "enriched": len(enriched),
                        "unique_codes": len(unique_codes),
                        "listing_seconds": round(listing_seconds[index], 3),
                        "enrichment_seconds": round(seconds, 3),
                        "total_seconds": round(listing_seconds[index] + seconds, 3),
                    }
                )

    rows.sort(key=lambda row: row["total_seconds"], reverse=True)
    payload = {
        "categories": len(categories),
        "category_workers": config.category_workers,
        "http_workers": config.http_workers,
        "detail_workers": config.detail_workers,
        "request_timeout": config.request_timeout,
        "download_images": config.download_images,
        "discovery_seconds": round(discovery_seconds, 3),
        "profile_seconds": round(time.perf_counter() - profile_started, 3),
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
    print(f"output={OUTPUT_PATH}")
    print("category\texpected\tcollected\tenriched\tunique\tlisting_s\tenrichment_s\ttotal_s")
    for row in rows:
        print(
            f"{row['category']}\t{row['expected']}\t{row['collected']}\t"
            f"{row['enriched']}\t{row['unique_codes']}\t{row['listing_seconds']:.3f}\t"
            f"{row['enrichment_seconds']:.3f}\t{row['total_seconds']:.3f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
