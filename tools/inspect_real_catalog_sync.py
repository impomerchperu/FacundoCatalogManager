from database.db_manager import DBManager
from models.scraping.category import Category
from repositories.product_repository import ProductRepository
from scrapers.browser import Browser
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import (
    ProductCollectionScraper,
)
from scrapers.parser import Parser
from services.scraping.scraped_product_mapper import (
    ScrapedProductMapper,
)


CATEGORY_URL = (
    "https://stock.importacionesfacundo.com/"
    "categoria-producto/jarros-mug/"
)


def main():

    print("=" * 80)
    print("SINCRONIZACION REAL CATALOGO")
    print("=" * 80)

    db = DBManager()

    repository = ProductRepository(db)

    browser = Browser()

    parser = Parser()

    category_scraper = CategoryScraper(
        browser=browser,
        parser=parser,
    )

    collection = ProductCollectionScraper(
        category_scraper=category_scraper,
    )

    category = Category(
        name="Jarros Mug",
        url=CATEGORY_URL,
    )

    scraped_products = collection.scrape_category(
        category,
    )

    mapper = ScrapedProductMapper()

    print()
    print(
        f"Productos scrapeados: {len(scraped_products)}"
    )

    print()

    created = 0

    for scraped in scraped_products:

        product = mapper.to_product(
            scraped,
        )

        repository.create(
            product,
        )

        created += 1

        print(
            product.code,
            "-",
            product.name,
        )

    print()
    print("=" * 80)
    print("RESULTADO")
    print("=" * 80)

    print(
        "Productos guardados:",
        created,
    )


if __name__ == "__main__":
    main()