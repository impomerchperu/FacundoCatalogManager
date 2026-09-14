from typing import Any, cast

from models.scraping.category import Category
from services.scraping.page_metrics_audit import record_page_metrics


class CategoryProductScrapingService:
    """
    Servicio encargado de obtener productos
    desde una categoría.

    Normaliza la entrada recibida:

    Puede recibir:

        scrape_category(url, "Jarros Mug")

    o:

        scrape_category(url, Category(...))
    """

    def __init__(
        self,
        scraper: Any,
    ) -> None:
        self.scraper = scraper

    def scrape_category(
        self,
        category_url: str,
        category_name: Any,
        expected_count: int = 0,
    ) -> Any:
        """
        Ejecuta extracción de productos
        para una categoría, conservando su conteo esperado.
        """

        if isinstance(
            category_name,
            Category,
        ):
            category = category_name

        else:
            category = Category(
                name=category_name,
                url=category_url,
                expected_count=max(int(expected_count or 0), 0),
            )

        products = self.scraper.scrape_category(
            category,
        )
        get_page_metrics = getattr(self.scraper, "get_page_metrics", None)
        if callable(get_page_metrics):
            metrics = cast(dict[str, dict[str, Any]], get_page_metrics())
            record_page_metrics(
                metrics,
                category_url=category.url,
            )
        return products

    def close(self) -> None:
        """Cierra los recursos internos del scraper de productos."""
        close_scraper = getattr(self.scraper, "close", None)
        if callable(close_scraper):
            close_scraper()
