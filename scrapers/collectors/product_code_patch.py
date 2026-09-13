"""Compatibility layer for WooCommerce SKU/code extraction."""

from __future__ import annotations

from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.extractors.code_utils import normalize_code
from scrapers.extractors.product_extractor import ProductExtractor

_PATCHED = False
_ORIGINAL_ENRICH_FROM_DETAIL_PAGE = ProductCollectionScraper._enrich_from_detail_page

# Kept as a compatibility reference for older tests/importers. ProductExtractor
# now owns the expanded SKU extraction directly; no runtime patch is needed.
_extract_code = ProductExtractor.extract_code


def _normalize(value: object) -> str:
    return normalize_code(value)


def _enrich_with_authoritative_code(
    self: ProductCollectionScraper,
    card,
    page_url: str,
    product,
    category_name: str,
):
    """Use the product detail SKU as the authoritative catalog code."""
    result = _ORIGINAL_ENRICH_FROM_DETAIL_PAGE(
        self,
        card,
        page_url,
        product,
        category_name,
    )
    if self.detail_extractor is None:
        return result

    detail_url = self._card_detail_url(card, page_url, result)
    if not detail_url:
        return result

    detailed_product = self._get_detailed_product(
        self._detail_cache_key(card, result, detail_url),
        detail_url,
        category_name,
    )
    if detailed_product is None:
        return result

    detail_code = _normalize(getattr(detailed_product, "code", ""))
    if detail_code:
        result.code = detail_code
        result.url = detail_url
    return result


def activate() -> None:
    """Install only the remaining authoritative detail-code compatibility hook."""
    global _PATCHED
    if _PATCHED:
        return
    ProductCollectionScraper._enrich_from_detail_page = _enrich_with_authoritative_code
    _PATCHED = True


activate()

__all__ = ["ProductCollectionScraper", "ProductExtractor", "activate"]
