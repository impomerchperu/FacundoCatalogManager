from database.db_manager import DBManager
from models.scraping.category import Category
from repositories.scraping.scraped_product_repository import (
    ScrapedProductRepository,
)
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import (
    ProductCollectionScraper,
)
from services.scraping.scraped_product_persistence_service import (
    ScrapedProductPersistenceService,
)


BASE_URL = "https://stock.importacionesfacundo.com"


db = DBManager()

repository = ScrapedProductRepository(db)


category_scraper = CategoryScraper(
    BASE_URL
)


collection_scraper = ProductCollectionScraper(category_scraper)


persistence = ScrapedProductPersistenceService(repository)


category = Category(
    name="Jarros Mug",
    url=("https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"),
)


print("=" * 80)
print("EXTRAYENDO PRODUCTOS")
print("=" * 80)


products = collection_scraper.scrape_category(category)


print("Productos encontrados:", len(products))


print("=" * 80)
print("GUARDANDO EN SQLITE")
print("=" * 80)


saved = persistence.save_products(products)


print("Productos guardados:", len(saved))


print("=" * 80)
print("DATOS EN BASE")
print("=" * 80)


rows = db.fetch_all(
    """
    SELECT
        code,
        name,
        category
    FROM scraped_products
    """
)


for row in rows:
    print(row["code"], "|", row["name"], "|", row["category"])


print("=" * 80)
print("TOTAL BD:", len(rows))
