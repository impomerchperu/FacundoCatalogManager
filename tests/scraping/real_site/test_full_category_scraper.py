from collections import Counter

import pytest

from models.scraping.category import Category
from scrapers.browser import Browser
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor

CATEGORY_URL = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"


@pytest.mark.real_site
def test_full_category_scraper_real_site():
    """Validación manual contra el sitio real; excluida de la suite normal."""
    category = Category(
        name="Jarros Mug",
        url=CATEGORY_URL,
    )

    browser = Browser()
    category_scraper = CategoryScraper(browser=browser)
    collection = ProductCollectionScraper(
        category_scraper,
        ProductCardExtractor(),
        CategoryProductExtractor(),
        ProductExtractor(),
    )

    products = collection.scrape_category(category)

    assert products

    codes = [p.code for p in products if p.code]
    duplicates = [code for code, count in Counter(codes).items() if count > 1]
    without_prices = [
        p.code
        for p in products
        if p.price_sample == 0
        and p.price_hundred == 0
        and p.price_thousand == 0
    ]
    without_images = [p.code for p in products if not p.image_url]

    print("TOTAL PRODUCTOS:", len(products))
    print("DUPLICADOS POR CODIGO:", duplicates)
    print("PRODUCTOS SIN PRECIO:", without_prices)
    print("PRODUCTOS SIN IMAGEN:", without_images)

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
