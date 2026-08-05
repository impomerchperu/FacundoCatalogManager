from time import perf_counter

from database.db_manager import DBManager
from repositories.product_repository import ProductRepository
from scrapers.browser import Browser
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import (
    ProductCollectionScraper,
)
from scrapers.extractors.category_extractor import CategoryExtractor
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.product_diff_service import ProductDiffService

STORE_URL = (
    "https://stock.importacionesfacundo.com/"
    "tienda/"
)


def main():

    start = perf_counter()

    print("=" * 80)
    print("SINCRONIZACIÓN COMPLETA REAL DEL CATÁLOGO")
    print("=" * 80)

    db = DBManager()

    repository = ProductRepository(db)

    browser = Browser()

    category_scraper = CategoryScraper(
        browser=browser,
        extractor=CategoryExtractor(),
    )

    collection = ProductCollectionScraper(
        category_scraper=category_scraper,
    )

    sync_service = CatalogSyncService(
        repository=repository,
        diff_service=ProductDiffService(),
    )

    print()
    print("Obteniendo categorías...")
    print()

    categories = category_scraper.scrape(
        STORE_URL,
    )

    print(
        f"Categorías encontradas: {len(categories)}"
    )

    total_products = 0

    total_result = {
        "processed": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "errors": 0,
    }

    print()

    for index, category in enumerate(categories, start=1):

        print("-" * 80)

        print(
            f"[{index}/{len(categories)}] "
            f"{category.name}"
        )

        products = collection.scrape_category(
            category,
        )

        total_products += len(products)

        print(
            f"Productos encontrados: {len(products)}"
        )

        result = sync_service.synchronize(
            products,
        )

        total_result["processed"] += result.processed
        total_result["created"] += result.created
        total_result["updated"] += result.updated
        total_result["unchanged"] += result.unchanged
        total_result["errors"] += result.errors


    elapsed = perf_counter() - start

    print()
    print("=" * 80)
    print("RESULTADO FINAL")
    print("=" * 80)

    print(
        f"Categorías procesadas: {len(categories)}"
    )

    print(
        f"Productos scrapeados: {total_products}"
    )

    print(
        f"Procesados : {total_result['processed']}"
    )

    print(
        f"Creados    : {total_result['created']}"
    )

    print(
        f"Actualizados: {total_result['updated']}"
    )

    print(
        f"Sin cambios: {total_result['unchanged']}"
    )

    print(
        f"Errores    : {total_result['errors']}"
    )

    print()

    print(
        f"Tiempo total: {elapsed:.2f} segundos"
    )


if __name__ == "__main__":
    main()
