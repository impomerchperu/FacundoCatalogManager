from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.extractors.product_block_extractor import ProductBlockExtractor
from scrapers.parser.category_product_parser import (
    CategoryProductParser,
)
from services.scraping.category_product_scraping_service import (
    CategoryProductScrapingService,
)

BASE_URL = "https://stock.importacionesfacundo.com"

scraper = CategoryScraper(
    BASE_URL,
    extractor=ProductBlockExtractor(),
)

service = CategoryProductScrapingService(
    scraper,
    CategoryProductParser(),
)

products = service.scrape_category(f"{BASE_URL}/categoria-producto/jarros-mug/")

print(f"Productos encontrados: {len(products)}")

for product in products[:5]:
    print("-" * 60)
    print(product.code)
    print(product.name)
    print(product.price_sample)
    print(product.price_hundred)
    print(product.price_thousand)
    print(product.image_url)
