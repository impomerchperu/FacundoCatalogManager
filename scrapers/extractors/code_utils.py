"""Shared helpers for WooCommerce product-code extraction."""

from __future__ import annotations

import json
import re

CODE_PATTERN = re.compile(
    r"^[A-Z0-9]{1,32}(?:[-_./][A-Z0-9]+)*$",
    re.IGNORECASE,
)
CODE_SEPARATORS = frozenset("-_./")


def normalize_code(value: object) -> str:
    """Normalize a SKU/code candidate without assuming a fixed prefix."""
    candidate = str(value or "").strip().strip(".,:;()[]{}")
    candidate = re.sub(
        r"^(?:sku|c[oó]digo|cod)\s*[:#-]?\s*",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    if not CODE_PATTERN.fullmatch(candidate):
        return ""
    if not any(char.isalpha() for char in candidate):
        return ""
    if not any(char.isdigit() or char in CODE_SEPARATORS for char in candidate):
        return ""
    return candidate.upper()


def normalize_code_token(text: object) -> str:
    """Find the first valid code token in a whitespace-separated string."""
    for token in re.split(r"\s+", str(text or "").strip()):
        code = normalize_code(token)
        if code:
            return code
    return ""


def find_code_in_json(value: object) -> str:
    """Recursively find the first valid SKU value in JSON-like data."""
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() == "sku":
                code = normalize_code(item)
                if code:
                    return code
            code = find_code_in_json(item)
            if code:
                return code
    elif isinstance(value, list):
        for item in value:
            code = find_code_in_json(item)
            if code:
                return code
    return ""


def extract_code_from_soup(soup, *, fallback, extractor=None) -> str:
    """Extract an authoritative WooCommerce SKU before using the legacy fallback."""
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
                code = normalize_code(value)
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
        code = find_code_in_json(payload)
        if code:
            return code

    if extractor is None:
        return fallback(soup)
    return fallback(extractor, soup)


__all__ = [
    "CODE_PATTERN",
    "CODE_SEPARATORS",
    "extract_code_from_soup",
    "find_code_in_json",
    "normalize_code",
    "normalize_code_token",
]
