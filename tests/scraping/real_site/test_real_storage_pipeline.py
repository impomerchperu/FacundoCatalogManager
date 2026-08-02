from scrapers.browser import Browser
from scrapers.parser import Parser

from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper

from scrapers.storage.product_storage import ProductStorage

from models.scraping.category import Category


CATEGORY_URL = (
    "https://stock.importacionesfacundo.com/"
    "categoria-producto/jarros-mug/"
)


category = Category(
    name="Jarros Mug",
    url=CATEGORY_URL
)


browser = Browser()

parser = Parser()


category_scraper = CategoryScraper(
    browser=browser,
    parser=parser
)


collection = ProductCollectionScraper(
    category_scraper=category_scraper
)


print("=" * 80)
print("SCRAPING")
print("=" * 80)


products = collection.scrape_category(
    category
)


print(
    "Productos obtenidos:",
    len(products)
)



storage = ProductStorage()


storage.save(
    products
)



print("=" * 80)
print("LECTURA STORAGE")
print("=" * 80)


saved = storage.load()


print(
    "Productos guardados:",
    len(saved)
)


print()


print(
    saved[0]
)