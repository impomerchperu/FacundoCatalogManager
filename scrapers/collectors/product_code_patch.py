"""Compatibility layer for WooCommerce SKU/code extraction."""

from __future__ import annotations

import json
import re

from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.extractors.product_extractor import ProductExtractor

_PATCHED = False
_CODE_PATTERN = re.compile(r"^[A-Z0-9]{1,32}(?:[-_./][A-Z0-9]+)*$", re.IGNORECASE)
_ORIGINAL_ENRICH_FROM_DETAIL_PAGE = ProductCollectionScraper._enrich_from_detail_page


def _normalize(value: object) -> str:
    candidate = str(value or "").strip().strip(".,:;()[]{}")
    candidate = re.sub(
        r"^(?:sku|c[oó]digo|cod)\s*[:#-]?\s*",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    if not _CODE_PATTERN.fullmatch(candidate):
        return ""
    if not any(char.isalpha() for char in candidate):
        return ""
    if not any(char.isdigit() for char in candidate):
        return ""
    return candidate.upper()


def _from_json(value: object) -> str:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() == "sku":
                code = _normalize(item)
                if code:
                    return code
            code = _from_json(item)
            if code:
                return code
    elif isinstance(value, list):
        for item in value:
            code = _from_json(item)
            if code:
                return code
    return ""


def _extract_code(self: ProductExtractor, soup) -> str:
    selectors = (
        "span.sku",
        ".sku_wrapper .sku",
        ".product_meta .sku",
        "[itemprop='sku']",
        "[data-sku]",
        "[sku]",
    )
    for selector in selectors:
        for element in soup.select(selector):
            values = (
                element.get("sku"),
                element.get("data-sku"),
                element.get("content"),
                element.get_text(" ", strip=True),
            )
            for value in values:
                code = _normalize(value)
                if code:
                    return code

    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        code = _from_json(payload)
        if code:
            return code

    # Preserve the existing extractor as a final compatibility fallback.
    return self._legacy_extract_code(soup)


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
    """Patch ProductExtractor and authoritative detail-page code extraction once."""
    global _PATCHED
    if _PATCHED:
        return
    legacy = ProductExtractor.extract_code
    ProductExtractor._legacy_extract_code = legacy
    ProductExtractor.extract_code = _extract_code
    ProductCollectionScraper._enrich_from_detail_page = _enrich_with_authoritative_code
    _PATCHED = True


activate()

__all__ = ["ProductExtractor", "ProductCollectionScraper", "activate"]
