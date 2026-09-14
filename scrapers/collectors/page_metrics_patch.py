"""Compatibility facade for the native page metrics audit."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.scraping.page_metrics_audit import record_page_metrics
from services.scraping.page_metrics_audit import TIMING_LOG as _AUDIT_TIMING_LOG

_PATCHED = False
TIMING_LOG = _AUDIT_TIMING_LOG


def _store_page_metrics_with_audit(
    self: Any,
    *,
    category_url: str,
    category_name: str,
    expected_count: int,
    pages: list[dict[str, Any]],
    unique_products: int,
) -> None:
    """Preserve the historical helper while using the native metrics storage."""
    store = getattr(self, "_store_page_metrics", None)
    if callable(store):
        store(
            category_url=category_url,
            category_name=category_name,
            expected_count=expected_count,
            pages=pages,
            unique_products=unique_products,
        )

    expected_pages = (
        (int(expected_count) + 24) // 25
        if int(expected_count or 0) > 0
        else len(pages)
    )
    loaded_pages = sum(1 for page in pages if page.get("html_available"))
    total_cards = sum(int(page.get("cards", 0) or 0) for page in pages)

    path = Path(TIMING_LOG)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(
            "SCRAPING TIMING | stage=category_page_summary | "
            f"category={category_name} | pages_expected={expected_pages} | "
            f"pages_requested={len(pages)} | pages_loaded={loaded_pages} | "
            f"cards={total_cards} | unique={int(unique_products)} | "
            f"expected_products={int(expected_count or 0)}\n"
        )
        for page in pages:
            file.write(
                "SCRAPING TIMING | stage=category_page_coverage | "
                f"category={category_name} | page={int(page.get('page', 0) or 0)} | "
                f"cards={int(page.get('cards', 0) or 0)} | "
                f"unique={int(page.get('unique_products', 0) or 0)} | "
                f"html={str(bool(page.get('html_available'))).lower()} | "
                f"url={page.get('url', '')}\n"
            )


def activate() -> None:
    """Preserve the historical activation API without monkey-patching runtime code."""
    return None


# Keep the canonical audit import available to historical callers.
_record_page_metrics = record_page_metrics

__all__ = [
    "TIMING_LOG",
    "_store_page_metrics_with_audit",
    "activate",
    "record_page_metrics",
]
