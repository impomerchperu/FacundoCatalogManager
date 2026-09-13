"""Legacy import compatibility for retired product-code monkey patches."""

# ruff: noqa: I001
# isort: skip_file

from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.code_utils import (
    find_code_in_json,
    normalize_code,
    normalize_code_token,
)
from scrapers.extractors.product_extractor import ProductExtractor


_ORIGINAL_ENRICH_FROM_DETAIL_PAGE = ProductCollectionScraper._enrich_from_detail_page
_extract_code = ProductExtractor.extract_code


def _normalize(value: object) -> str:
    return normalize_code(value)


def _normalize_category_code(cls, text: str) -> str:
    return normalize_code_token(text)


def _from_json(value: object) -> str:
    return find_code_in_json(value)


def _enrich_with_authoritative_code(
    self: ProductCollectionScraper,
    card,
    page_url: str,
    product,
    category_name: str,
):
    """Preserve the historical compatibility helper without monkey-patching core."""
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
    """Keep the historical activation API without modifying runtime classes."""
    return None


__all__ = [
    "CategoryProductExtractor",
    "ProductCollectionScraper",
    "ProductExtractor",
    "activate",
]
