from scrapers.browser import Browser
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper


class Category:
    name = "Jarros Mug"

    url = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"


browser = Browser()


category_scraper = CategoryScraper(browser)


collection = ProductCollectionScraper(category_scraper)


products = collection.scrape_category(Category())


print("=" * 80)

print("TOTAL PRODUCTOS:", len(products))

print("=" * 80)


for product in products[:5]:
    print(product)
