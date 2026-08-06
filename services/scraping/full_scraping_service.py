from typing import Any

from models.scraping.category import Category


class FullScrapingService:
    """
    Orquestador principal del scraping completo.

    Soporta dos flujos:

    Flujo antiguo:
    - category_scraper
    - category_pagination_service
    - product_scraper
    - product_service

    Flujo moderno:
    - category_service
    - product_scraper
    - image_manager
    - image_sync_service
    """

    def __init__(
        self,
        category_scraper: Any = None,
        category_pagination_service: Any = None,
        product_scraper: Any = None,
        product_service: Any = None,
        category_service: Any = None,
        image_manager: Any = None,
        downloader: Any = None,
        image_sync_service: Any = None,
        category_product_sync_service: Any = None,
    ):

        self.category_scraper = category_scraper
        self.category_pagination_service = category_pagination_service
        self.product_scraper = product_scraper
        self.product_service = product_service

        self.category_service = category_service

        self.image_manager = image_manager
        self.downloader = downloader
        self.image_sync_service = image_sync_service

        self.category_product_sync_service = (
            category_product_sync_service
        )

    # ======================================================
    # Flujo por categoría
    # ======================================================

    def scrape_category(
        self,
        category,
    ):

        # Nuevo flujo usando CategoryProductSyncService
        if self.category_product_sync_service:

            if isinstance(category, Category):

                return (
                    self.category_product_sync_service.sync_category(
                        category.url,
                        category.name,
                    )
                )

            return (
                self.category_product_sync_service.sync_category(
                    category,
                )
            )

        # Compatibilidad con flujo anterior
        if not self.category_pagination_service:
            return []

        if not self.category_scraper:
            return []

        if not self.product_service:
            return []

        pages = (
            self.category_pagination_service.get_pages(
                category
            )
        )

        products = []

        for page in pages:

            urls = (
                self.category_scraper.get_product_urls(
                    page
                )
            )

            for url in urls:

                saved = (
                    self.product_service.scrape_and_save(
                        url
                    )
                )

                products.append(saved)

        return products


    # ======================================================
    # Ejecución completa moderna
    # ======================================================

    def run(self):

        # Nuevo flujo
        if self.category_service:

            categories = (
                self.category_service.scrape_all()
            )

            products = []

            if self.product_scraper:

                products = (
                    self.product_scraper.scrape_products(
                        categories
                    )
                )

            images = []

            if self.image_manager:

                images = (
                    self.image_manager.download_all(
                        products,
                        self.downloader,
                    )
                )

            if self.image_sync_service:

                products = (
                    self.image_sync_service.sync_products(
                        products
                    )
                )

            return {
                "products": products,
                "images": images,
            }


        # Sin configuración
        return {
            "products": [],
            "images": [],
        }
