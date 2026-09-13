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

    PRODUCTS_PER_PAGE = 25

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
        expected_count = max(0, getattr(category, "expected_count", 0))
        pages = self.category_scraper.get_category_pages(
            category.url,
            expected_count=expected_count,
        )
        required_pages = self._required_pages(expected_count)
        if len(pages) >= required_pages or required_pages <= 1:
            return pages
        return self._recover_missing_category_pages(
            category.url,
            pages,
            required_pages,
        )

    @classmethod
    def _required_pages(cls, expected_count: int) -> int:
        if expected_count <= 0:
            return 1
        return (expected_count + cls.PRODUCTS_PER_PAGE - 1) // cls.PRODUCTS_PER_PAGE

    def _recover_missing_category_pages(
        self,
        category_url: str,
        pages: list[str],
        required_pages: int,
    ) -> list[str]:
        """
        Fuerza las páginas faltantes cuando JetSmartFilters reporta menos
        páginas que el conteo publicado por la tienda.

        El conteo de la categoría es la fuente de verdad para cobertura:
        50 productos requieren 2 páginas, 79 requieren 4, etc. La respuesta
        AJAX puede declarar metadata incompleta y no debe truncar el catálogo.
        """

        category_html = self.category_scraper.get_html(category_url)
        category_id = self.category_scraper._category_id(category_html)
        if category_id is None:
            return pages

        recovered = list(pages) or [category_url]
        known = set(recovered)
        for page in range(2, required_pages + 1):
            page_url = self.category_scraper._jsf_page_url(category_url, page)
            if page_url in known:
                continue

            rendered_html = self.category_scraper._fetch_category_page_html(
                category_url,
                category_id,
                page,
                page_url,
            )
            if not rendered_html:
                raise RuntimeError(
                    "No se pudo recuperar la página "
                    f"{page}/{required_pages} de la categoría {category_url}."
                )

            self.category_scraper._cache_category_html(page_url, rendered_html)
            recovered.append(page_url)
            known.add(page_url)

        return recovered

    def _enable_thread_sessions(self) -> None:
        browser = getattr(self.category_scraper, "browser", None)
        if browser is not None and hasattr(browser, "enable_thread_sessions"):
            browser.enable_thread_sessions()
