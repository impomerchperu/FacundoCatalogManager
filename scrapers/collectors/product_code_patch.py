"""Compatibility layer for WooCommerce SKU/code extraction."""

from __future__ import annotations

from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.code_utils import (
    extract_code_from_soup,
    normalize_code,
    normalize_code_token,
)
from scrapers.extractors.product_extractor import ProductExtractor

_PATCHED = False
_ORIGINAL_ENRICH_FROM_DETAIL_PAGE = ProductCollectionScraper._enrich_from_detail_page
_ORIGINAL_EXTRACT_CODE = ProductExtractor.extract_code


def _normalize(value: object) -> str:
    return normalize_code(value)


def _normalize_category_code(cls, text: str) -> str:
    return normalize_code_token(text)


def _from_json(value: object) -> str:
    from scrapers.extractors.code_utils import find_code_in_json

    return find_code_in_json(value)


def _extract_code(self: ProductExtractor, soup) -> str:
    return extract_code_from_soup(soup, fallback=_ORIGINAL_EXTRACT_CODE, extractor=self)


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
    """Patch SKU extraction and authoritative detail-page code handling once."""
    global _PATCHED
    if _PATCHED:
        return

    ProductExtractor._legacy_extract_code = _ORIGINAL_EXTRACT_CODE  # pyright: ignore[reportAttributeAccessIssue]
    ProductExtractor.extract_code = _extract_code
    ProductCollectionScraper._enrich_from_detail_page = _enrich_with_authoritative_code
    CategoryProductExtractor._normalize_code = classmethod(_normalize_category_code)  # pyright: ignore[reportAttributeAccessIssue]
    _PATCHED = True


activate()

__all__ = ["CategoryProductExtractor", "ProductCollectionScraper", "ProductExtractor", "activate"]
