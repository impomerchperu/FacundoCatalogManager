from models.scraping.category import Category
from scrapers.collectors.category_scraper import CategoryScraper


class CatalogScraper:
    """
    Orquesta el recorrido completo del catálogo.

    Flujo:

        tienda
            ↓
        categorías
            ↓
        páginas de cada categoría
            ↓
        productos
    """

    def __init__(
        self,
        category_scraper: CategoryScraper,
    ):
        self.category_scraper = category_scraper

    def scrape_catalog(
        self,
        catalog_url: str,
    ) -> list[tuple[Category, str]]:
        """
        Recorre el catálogo completo.

        Devuelve una lista de tuplas:

            (Category, page_url)

        donde page_url corresponde a cada página encontrada
        dentro de una categoría.
        """

        categories = self.category_scraper.scrape(catalog_url)
        pages: list[tuple[Category, str]] = []

        for category in categories:
            category_pages = self.category_scraper.get_category_pages(
                category.url,
                expected_count=getattr(category, "expected_count", 0),
            )

            if not category_pages:
                pages.append((category, category.url))
                continue

            for page in category_pages:
                pages.append((category, page))

        return pages
