"""Helpers for extracting color/stock pairs from the site's variant nodes."""

from __future__ import annotations

import re


def extract_variant_color_stock(soup) -> dict[str, int]:
    """Extract stock from variant nodes where color and stock share one node."""
    color_stock: dict[str, int] = {}

    for element in soup.select(".variaciones-producto"):
        color = (
            element.get("data-color")
            or element.get("data-value")
            or element.get("title")
        )
        if not isinstance(color, str) or not color.strip():
            continue

        stock = _extract_variant_stock(element)
        if stock is None:
            continue

        normalized = re.sub(r"\s+", " ", color).strip(" .:-|")
        if not normalized:
            continue

        color_stock[normalized] = max(stock, 0)

    return color_stock


def _extract_variant_stock(element) -> int | None:
    for attribute in (
        "data-stock",
        "data-quantity",
        "data-max-qty",
        "data-max_quantity",
    ):
        value = element.get(attribute)
        if value is not None:
            parsed = _parse_stock(value)
            if parsed is not None:
                return parsed

    values: list[int] = []
    for paragraph in element.select("p"):
        parsed = _parse_stock(paragraph.get_text(" ", strip=True))
        if parsed is not None:
            values.append(parsed)

    if len(values) == 1:
        return values[0]

    text = element.get_text(" ", strip=True)
    match = re.search(r"(?:stock\s*[:\-]?\s*)?(\d[\d,.]*)$", text, re.IGNORECASE)
    if match is not None:
        return _parse_stock(match.group(1))

    return None


def _parse_stock(value: object) -> int | None:
    text = str(value or "").strip()
    match = re.fullmatch(r"(\d[\d,.]*)", text)
    if match is None:
        return None

    try:
        return int(float(match.group(1).replace(",", "")))
    except ValueError:
        return None
