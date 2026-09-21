from __future__ import annotations

import re

import pytest
from bs4 import BeautifulSoup

from scrapers.browser import Browser
from scrapers.extractors.category_product_extractor import (
    CategoryProductExtractor,
)
from scrapers.extractors.product_extractor import ProductExtractor

CATEGORY_URL = (
    "https://stock.importacionesfacundo.com/"
    "categoria-producto/bolsas-mochilas/"
)


def _expected_variant_color_stock(row) -> dict[str, int]:
    expected: dict[str, int] = {}

    for variant in row.select(".variaciones-producto[title]"):
        color = str(variant.get("title", "")).strip()
        if not color:
            continue

        paragraph = variant.find("p")
        if paragraph is None:
            continue

        stock_text = paragraph.get_text(" ", strip=True)
        match = re.fullmatch(r"(\d[\d,.]*)", stock_text)
        if match is None:
            continue

        stock = int(float(match.group(1).replace(",", "")))
        expected[re.sub(r"\s+", " ", color)] = max(stock, 0)

    return expected


def _product_code(row) -> str:
    element = row.select_one("span.sku")
    return element.get_text(" ", strip=True) if element else ""


@pytest.mark.real_site
def test_real_site_variant_color_stock_matches_each_variant_node() -> None:
    browser = Browser()
    try:
        html = browser.fetch(CATEGORY_URL)
    finally:
        browser.close()

    soup = BeautifulSoup(html, "lxml")
    rows = [
        row
        for row in soup.select("tr.product-list-container")
        if _product_code(row)
        and len(_expected_variant_color_stock(row)) >= 2
    ]

    assert len(rows) >= 3, (
        "La categoría real debe exponer al menos tres productos con "
        "variantes de color y stock asociado."
    )

    category_extractor = CategoryProductExtractor()
    product_extractor = ProductExtractor()

    for row in rows[:3]:
        expected = _expected_variant_color_stock(row)
        code = _product_code(row)

        category_product = category_extractor.extract(row)
        detail_product = product_extractor.extract(
            row,
            url="https://stock.importacionesfacundo.com/",
            category="Bolsas / Mochilas",
        )

        normalized_expected = {
            color.casefold(): stock
            for color, stock in expected.items()
        }
        normalized_category = {
            color.casefold(): stock
            for color, stock in category_product.color_stock.items()
        }
        normalized_detail = {
            color.casefold(): stock
            for color, stock in detail_product.color_stock.items()
        }

        assert normalized_category == normalized_expected, code
        assert normalized_detail == normalized_expected, code
        assert category_product.stock == sum(expected.values()), code
        assert detail_product.stock == sum(expected.values()), code
