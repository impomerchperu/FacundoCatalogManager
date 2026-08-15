from models.scraping.category import Category
from repositories.product_repository import ProductRepository
from repositories.scraping.scraping_history_repository import (
    ScrapingHistoryRepository,
)
from services.scraping.category_service import CategoryService


class ScrapingRunner:
    """
    Ejecuta el proceso completo de scraping.

    Modos soportados:

    1. Ejecución controlada:
        runner.run(categories)

    2. Ejecución automática:
        runner.run()

    Responsabilidades:

    - Coordinar servicios.
    - Ejecutar categorías.
    - Mantener configuración activa.
    - Reportar progreso.
    - Exponer los repositorios de historial y catálogo.
    """

    def __init__(
        self,
        scraping_service,
        config=None,
        category_service: CategoryService | None = None,
        history_repository: ScrapingHistoryRepository | None = None,
        catalog_repository: ProductRepository | None = None,
    ):
        self.scraping_service = scraping_service
        self.config = config
        self.category_service = category_service
        self.history_repository = history_repository
        self.catalog_repository = catalog_repository

    def run(
        self,
        categories: list[Category] | None = None,
        progress_callback=None,
    ):
        """
        Ejecuta scraping.

        Si recibe categorías:
            usa las categorías indicadas.

        Si no recibe categorías:
            delega en run_all().
        """

        if categories is None:
            return self.run_all(
                progress_callback,
            )

        reset_sync_result = getattr(
            self.scraping_service,
            "reset_sync_result",
            None,
        )

        if callable(reset_sync_result):
            reset_sync_result()

        sync_categories = getattr(
            self.scraping_service,
            "sync_categories",
            None,
        )

        if callable(sync_categories):
            return sync_categories(
                categories,
                progress_callback,
            )

        results = []

        total = len(categories)

        for index, category in enumerate(
            categories,
            start=1,
        ):
            if hasattr(
                self.scraping_service,
                "sync_category",
            ):
                products = self.scraping_service.sync_category(
                    category.url,
                    category.name,
                )
            else:
                products = self.scraping_service.scrape_category(
                    category,
                )

            results.extend(products)

            if progress_callback:
                progress_callback(
                    index,
                    total,
                )

        return results

    def run_all(
        self,
        progress_callback=None,
    ):
        """
        Ejecuta scraping completo.

        Obtiene categorías automáticamente
        mediante CategoryService.
        """

        if self.category_service is None:
            return []

        categories = self.category_service.scrape_all()

        return self.run(
            categories,
            progress_callback,
        )
