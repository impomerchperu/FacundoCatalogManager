from models.scraping.category import Category


class CategoryProductScrapingService:
    """
    Servicio encargado de obtener productos
    desde una categoría.
    """

    def __init__(
        self,
        scraper,
    ):
        self.scraper = scraper

    def scrape_category(
        self,
        category_url: str,
        category_name: str,
    ):

        category = Category(
            name=category_name,
            url=category_url,
        )

        return self.scraper.scrape_category(
            category,
        )
