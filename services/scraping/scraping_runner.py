from models.scraping.category import Category


class ScrapingRunner:
    """
    Ejecuta el proceso de scraping.

    Puede trabajar con:
    - servicios de scraping simples
    - servicios de sincronización completos
    """

    def __init__(
        self,
        scraping_service,
    ):
        self.scraping_service = scraping_service

    def run(
        self,
        categories: list[Category],
        progress_callback=None,
    ):

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
