"""Persist per-page scraping metrics for coverage diagnostics."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TIMING_LOG = PROJECT_ROOT / "data" / "scraping_timing.log"
logger = logging.getLogger("FCM")


def _log_timing(message: str, *args: Any) -> None:
    logger.info(message, *args)
    TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
    formatted = message % args if args else message
    with TIMING_LOG.open("a", encoding="utf-8") as file:
        file.write(f"{formatted}\n")


def record_page_metrics(metrics: dict[str, dict[str, Any]]) -> None:
    """Write the same category/page coverage audit emitted historically."""
    for category_metrics in metrics.values():
        category_name = str(category_metrics.get("category", ""))
        expected_count = int(category_metrics.get("expected_count", 0) or 0)
        pages = list(category_metrics.get("pages", []))
        expected_pages = (
            (expected_count + 24) // 25
            if expected_count
            else len(pages)
        )
        total_cards = sum(int(page.get("cards", 0) or 0) for page in pages)
        loaded_pages = sum(1 for page in pages if page.get("html_available"))
        unique_products = int(category_metrics.get("unique_products", 0) or 0)

        _log_timing(
            "SCRAPING TIMING | stage=category_page_summary | "
            "category=%s | pages_expected=%d | pages_requested=%d | "
            "pages_loaded=%d | cards=%d | unique=%d | expected_products=%d",
            category_name,
            expected_pages,
            len(pages),
            loaded_pages,
            total_cards,
            unique_products,
            expected_count,
        )
        for page in pages:
            _log_timing(
                "SCRAPING TIMING | stage=category_page_coverage | "
                "category=%s | page=%d | cards=%d | unique=%d | "
                "html=%s | url=%s",
                category_name,
                int(page.get("page", 0) or 0),
                int(page.get("cards", 0) or 0),
                int(page.get("unique_products", 0) or 0),
                str(bool(page.get("html_available"))).lower(),
                str(page.get("url", "")),
            )


__all__ = ["TIMING_LOG", "record_page_metrics"]
