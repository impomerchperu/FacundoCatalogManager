import sys
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from models.scraping.category import Category
from scrapers.browser import Browser
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import (
    ProductCollectionScraper,
)
from scrapers.parser import Parser

CATEGORY_URL = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"


def main():

    print("=" * 80)
    print("SCRAPING REAL - DIAGNOSTICO")
    print("=" * 80)

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

    products = collection.scrape_category(
        category,
    )

    print()
    print(f"Productos encontrados: {len(products)}")

    print()
    print("-" * 80)

    print("DUPLICADOS POR CODIGO")

    codes = [p.code for p in products if p.code]

    duplicates = [code for code, count in Counter(codes).items() if count > 1]

    print(duplicates)

    print()
    print("-" * 80)

    print("PRODUCTOS")

    for product in products:
        print()

        print(f"Código: {product.code}")

        print(f"Nombre: {product.name}")

        print(f"Stock: {product.stock}")

        print(f"Precio muestra: {product.price_sample}")

        print(f"Precio ciento: {product.price_hundred}")

        print(f"Precio millar: {product.price_thousand}")

        print(f"Imagen: {product.image_url}")


if __name__ == "__main__":
    main()
