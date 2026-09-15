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


def _profile_category(service: Any, index: int, category: Any) -> dict[str, Any]:
    category_name = str(getattr(category, "name", "") or "").strip() or "(sin nombre)"
    expected = max(int(getattr(category, "expected_count", 0) or 0), 0)

    listing_started = time.perf_counter()
    collected = service._collect_category(index, category)
    listing_seconds = time.perf_counter() - listing_started

    enrichment_started = time.perf_counter()
    enriched = service._enrich_category(index, category, collected)
    enrichment_seconds = time.perf_counter() - enrichment_started

    unique_codes = {
        str(getattr(product, "code", "") or "").strip().casefold()
        for product in enriched
        if str(getattr(product, "code", "") or "").strip()
    }

    return {
        "category": category_name,
        "expected": expected,
        "collected": len(collected),
        "enriched": len(enriched),
        "unique_codes": len(unique_codes),
        "listing_seconds": round(listing_seconds, 3),
        "enrichment_seconds": round(enrichment_seconds, 3),
        "total_seconds": round(listing_seconds + enrichment_seconds, 3),
    }


def main() -> int:
    config = ScrapingConfig(download_images=False)
    runner = ScrapingFactory.create_runner(config)

    started = time.perf_counter()
    categories = list(runner.category_service.scrape_all() or [])
    discovery_seconds = time.perf_counter() - started

    service = runner.scraping_service
    worker_count = min(config.category_workers, len(categories))
    rows: list[dict[str, Any]] = []

    profile_started = time.perf_counter()
    if categories:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(service._collect_category, index, category): (index, category)
                for index, category in enumerate(categories)
            }
            collected_by_index: list[list[Any]] = [[] for _ in categories]
            listing_started: dict[int, float] = {}
            listing_seconds: dict[int, float] = {}
            for future, (index, category) in futures.items():
                del category
                listing_started[index] = time.perf_counter()
                collected_by_index[index] = future.result()
                listing_seconds[index] = time.perf_counter() - listing_started[index]

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    service._enrich_category,
                    index,
                    categories[index],
                    collected_by_index[index],
                ): index
                for index in range(len(categories))
            }
            enrichment_started: dict[int, float] = {}
            enriched_by_index: list[list[Any]] = [[] for _ in categories]
            for future, index in futures.items():
                enrichment_started[index] = time.perf_counter()
                enriched_by_index[index] = future.result()
                enrichment_seconds = time.perf_counter() - enrichment_started[index]
                category = categories[index]
                enriched = enriched_by_index[index]
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
                        "enrichment_seconds": round(enrichment_seconds, 3),
                        "total_seconds": round(
                            listing_seconds[index] + enrichment_seconds,
                            3,
                        ),
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
