from typing import Any

from models.scraping.category import Category


class FullScrapingService:
    """
    Orquestador principal del scraping completo.

    Flujo moderno:

    - category_service
    - category_product_sync_service
    - image_sync_adapter

    Mantiene compatibilidad temporal con
    componentes antiguos.
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
        image_sync_adapter: Any = None,
    ):
        self.category_scraper = category_scraper
        self.category_pagination_service = category_pagination_service
        self.product_scraper = product_scraper
        self.product_service = product_service
        self.category_service = category_service

        # Compatibilidad legacy
        self.image_manager = image_manager
        self.downloader = downloader

        # Arquitectura nueva
        self.image_sync_adapter = image_sync_adapter or image_sync_service
        self.category_product_sync_service = category_product_sync_service

    def scrape_category(self, category):
        if self.category_product_sync_service:
            if isinstance(category, Category):
                return self.category_product_sync_service.sync_category(
                    category.url,
                    category.name,
                )

            return self.category_product_sync_service.sync_category(
                category,
            )

        if not self.category_pagination_service:
            return []
        if not self.category_scraper:
            return []
        if not self.product_service:
            return []

        pages = self.category_pagination_service.get_pages(category)
        products = []

        for page in pages:
            urls = self.category_scraper.get_product_urls(page)
            for url in urls:
                saved = self.product_service.scrape_and_save(url)
                products.append(saved)

        return products

    def run(self):
        if not self.category_service:
            return {
                "products": [],
                "images": [],
            }

        categories = self.category_service.scrape_all()
        products = []

        if self.category_product_sync_service:
            # La sincronización moderna ya consolida productos y sincroniza
            # sus imágenes dentro de sync_products(). No volver a ejecutar
            # image_sync_adapter aquí: hacerlo duplicaba la búsqueda y el
            # cálculo de hash de cada imagen en cada ejecución.
            sync_categories = getattr(
                self.category_product_sync_service,
                "sync_categories",
                None,
            )
            if callable(sync_categories):
                products = sync_categories(categories)
            else:
                for category in categories:
                    products.extend(
                        self.category_product_sync_service.sync_category(
                            category.url,
                            category.name,
                        )
                    )

        elif self.product_scraper:
            products = self.product_scraper.scrape_products(categories)

            # En el flujo legacy/modular, el adaptador es el responsable de
            # sincronizar las imágenes porque no existe un
            # category_product_sync_service que lo haga.
            if self.image_sync_adapter:
                products = self.image_sync_adapter.sync_products(products)

        images = []

        # ----------------------------------------------
        # Compatibilidad legacy
        # ----------------------------------------------
        if not self.category_product_sync_service and not self.product_scraper:
            if self.image_manager:
                images = self.image_manager.download_all(
                    products,
                    self.downloader,
                )

        return {
            "products": products,
            "images": images,
        }
