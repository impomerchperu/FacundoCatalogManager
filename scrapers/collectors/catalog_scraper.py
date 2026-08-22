from concurrent.futures import ThreadPoolExecutor

from config.scraping_config import SCRAPING_CATEGORY_WORKERS
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
        if not categories:
            return []

        self._enable_thread_sessions()
        worker_count = min(SCRAPING_CATEGORY_WORKERS, len(categories))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            category_pages = list(
                executor.map(self._get_category_pages, categories)
            )

        pages: list[tuple[Category, str]] = []
        for category, discovered_pages in zip(
            categories,
            category_pages,
            strict=True,
        ):
            if not discovered_pages:
                pages.append((category, category.url))
                continue

            pages.extend((category, page) for page in discovered_pages)

        return pages

    def _get_category_pages(self, category: Category) -> list[str]:
        return self.category_scraper.get_category_pages(
            category.url,
            expected_count=getattr(category, "expected_count", 0),
        )

    def _enable_thread_sessions(self) -> None:
        browser = getattr(self.category_scraper, "browser", None)
        if browser is not None and hasattr(browser, "enable_thread_sessions"):
            browser.enable_thread_sessions()
