from collections import Counter

import pytest

from models.scraping.category import Category
from scrapers.browser import Browser
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.parser import Parser

CATEGORY_URL = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"


@pytest.mark.real_site
def test_full_category_scraper_real_site():
    """
    Test manual contra el sitio real.

    No debe ejecutarse en la suite normal.
    Ejecutar con:

        pytest -m real_site
    """

    category = Category(
        name="Jarros Mug",
        url=CATEGORY_URL,
    )

    browser = Browser()

    parser = Parser()

    category_scraper = CategoryScraper(
        browser=browser,
        parser=parser,
    )

    collection = ProductCollectionScraper(
        category_scraper=category_scraper,
    )

    products = collection.scrape_category(category)

    assert products

    print("=" * 80)
    print("TOTAL PRODUCTOS")
    print("=" * 80)

    print(len(products))

    print()
    print("=" * 80)
    print("DUPLICADOS POR CODIGO")
    print("=" * 80)

    codes = [p.code for p in products if p.code]

    duplicates = [code for code, count in Counter(codes).items() if count > 1]

    print(duplicates)

    print()
    print("=" * 80)
    print("PRODUCTOS SIN PRECIO")
    print("=" * 80)

    without_prices = [
        p.code
        for p in products
        if (p.price_sample == 0 and p.price_hundred == 0 and p.price_thousand == 0)
    ]

    print(without_prices)

    print()
    print("=" * 80)
    print("PRODUCTOS SIN IMAGEN")
    print("=" * 80)

    without_images = [p.code for p in products if not p.image_url]

    print(without_images)

    print()
    print("=" * 80)
    print("MUESTRA")
    print("=" * 80)

    for product in products[:5]:
        print(
            {
                "codigo": product.code,
                "nombre": product.name,
                "stock": product.stock,
                "precio_muestra": product.price_sample,
                "precio_ciento": product.price_hundred,
                "precio_millar": product.price_thousand,
                "imagen": product.image_url,
            }
        )
