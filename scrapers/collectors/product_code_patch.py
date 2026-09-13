"""Legacy import compatibility for retired product-code monkey patches."""

from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.code_utils import (
    extract_code_from_soup,
    find_code_in_json,
    normalize_code,
    normalize_code_token,
)
from scrapers.extractors.product_extractor import ProductExtractor


def _normalize(value: object) -> str:
    return normalize_code(value)


def _normalize_category_code(cls, text: str) -> str:
    return normalize_code_token(text)


def _from_json(value: object) -> str:
    return find_code_in_json(value)


def _extract_code(self: ProductExtractor, soup) -> str:
    """Compatibility alias for the core extractor implementation."""
    return extract_code_from_soup(
        soup,
        fallback=ProductExtractor._extract_code_from_marked_text,
        extractor=self,
    )


def _enrich_with_authoritative_code(
    self: ProductCollectionScraper,
    card,
    page_url: str,
    product,
    category_name: str,
):
    """Compatibility alias for the core detail-enrichment implementation."""
    return ProductCollectionScraper._enrich_from_detail_page(
        self,
        card,
        page_url,
        product,
        category_name,
    )


def activate() -> None:
    """Keep the historical activation API without modifying runtime classes."""
    return None


__all__ = [
    "CategoryProductExtractor",
    "ProductCollectionScraper",
    "ProductExtractor",
    "activate",
]
