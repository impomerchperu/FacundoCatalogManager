from models.scraping.category import Category


class CategoryService:
    """
    Servicio encargado de obtener categorías
    disponibles para scraping.

    Responsabilidades:

    - Coordinar CategoryScraper.
    - Obtener categorías desde la tienda.
    - Mantener la lógica de negocio fuera del scraper.
    """

    def __init__(
        self,
        category_scraper,
        catalog_url: str,
    ):
        self.category_scraper = category_scraper
        self.catalog_url = catalog_url

    def scrape_all(self) -> list[Category]:
        """
        Obtiene todas las categorías disponibles.
        """

        categories = self.category_scraper.scrape(
            self.catalog_url
        )

        if not categories:
            return []

        return [
            category
            for category in categories
            if isinstance(
                category,
                Category,
            )
        ]
