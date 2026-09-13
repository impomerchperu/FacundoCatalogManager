"""Runtime compatibility fixes for the Facundo catalog scraper."""

from bs4 import BeautifulSoup

from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.category_name_normalizer import split_category_names
from services.scraping.category_product_sync_service import CategoryProductSyncService

from .category_scraper import CategoryScraper


def _normalize_code_candidate(cls, text: str) -> str:
    """Accept SKU codes made of letters/digits separated by hyphens."""
    candidate = str(text).strip().strip(".,:;()[]{}")
    if not cls._CODE_PATTERN.fullmatch(candidate):
        return ""
    if not any(char.isalpha() for char in candidate):
        return ""
    return candidate.upper()


def _parse_with_lxml(self: CategoryScraper, html: str):
    """Parse Facundo HTML with lxml so malformed markup preserves product cards."""
    if self.parser and hasattr(self.parser, "parse"):
        return self.parser.parse(html)
    return BeautifulSoup(html, "lxml")


def _split_categories(value: object) -> list[str]:
    """Preserve canonical category names while supporting the legacy helper API."""
    return split_category_names(value)


def activate() -> None:
    """Install compatibility fixes without replacing category pagination."""
    ProductExtractor._normalize_code_candidate = classmethod(_normalize_code_candidate)  # pyright: ignore[reportAttributeAccessIssue]
    CategoryScraper._parse = _parse_with_lxml
    CategoryProductSyncService._split_categories = staticmethod(_split_categories)


activate()

__all__ = ["CategoryScraper", "activate"]
