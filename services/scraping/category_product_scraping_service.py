from models.scraping.category import Category


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
        scraper,
    ):
        self.scraper = scraper

    def scrape_category(
        self,
        category_url: str,
        category_name,
        expected_count: int = 0,
    ):
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

        return self.scraper.scrape_category(
            category,
        )
