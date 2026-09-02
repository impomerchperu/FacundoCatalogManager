"""Audit layer for per-page category product counts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .product_collection_scraper import ProductCollectionScraper

_PATCHED = False
_ORIGINAL_STORE_PAGE_METRICS = ProductCollectionScraper._store_page_metrics
PROJECT_ROOT = Path(__file__).resolve().parents[2]
TIMING_LOG = PROJECT_ROOT / "data" / "scraping_timing.log"
logger = logging.getLogger("FCM")


def _log_timing(message: str, *args: Any) -> None:
    logger.info(message, *args)
    TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
    formatted = message % args if args else message
    with TIMING_LOG.open("a", encoding="utf-8") as file:
        file.write(f"{formatted}\n")


def _store_page_metrics_with_audit(
    self: ProductCollectionScraper,
    *,
    category_url: str,
    category_name: str,
    expected_count: int,
    pages: list[dict[str, Any]],
    unique_products: int,
) -> None:
    _ORIGINAL_STORE_PAGE_METRICS(
        self,
        category_url=category_url,
        category_name=category_name,
        expected_count=expected_count,
        pages=pages,
        unique_products=unique_products,
    )
    expected_pages = (int(expected_count) + 24) // 25 if expected_count else len(pages)
    total_cards = sum(int(page.get("cards", 0) or 0) for page in pages)
    loaded_pages = sum(1 for page in pages if page.get("html_available"))
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
        int(expected_count or 0),
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


def activate() -> None:
    """Install the page-level audit once."""
    global _PATCHED
    if _PATCHED:
        return
    ProductCollectionScraper._store_page_metrics = _store_page_metrics_with_audit
    _PATCHED = True


activate()

__all__ = ["ProductCollectionScraper", "activate"]
