from models.scraping.category import Category
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.product_collection_scraper import ProductCollectionScraper


BASE_URL = "https://stock.importacionesfacundo.com"


category_scraper = CategoryScraper(
    BASE_URL
)


collection = ProductCollectionScraper(
    category_scraper
)


category = Category(
    name="Jarros Mug",
    url=(
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/jarros-mug/"
    ),
)


products = collection.scrape_category(
    category
)


print("=" * 80)
print("PRODUCTOS EXTRAÍDOS")
print("=" * 80)


for product in products:
    print(
        product.code,
        "|",
        product.name,
        "|",
        product.category,
    )


print("=" * 80)
print("TOTAL:", len(products))