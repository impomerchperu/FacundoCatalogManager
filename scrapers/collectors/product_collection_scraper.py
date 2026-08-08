from bs4 import BeautifulSoup

from models.scraping.category import Category


class ProductCollectionScraper:
    """
    Recorre todas las páginas de una categoría y extrae
    los productos encontrados.

    Flujo:

        Category
            |
            v
        páginas de categoría
            |
            v
        tarjetas de producto
            |
            v
        ScrapedProduct
    """

    def __init__(
        self,
        category_scraper,
        card_extractor,
        product_extractor,
    ):
        self.category_scraper = category_scraper
        self.card_extractor = card_extractor
        self.product_extractor = product_extractor

    def scrape_category(
        self,
        category,
    ):
        """
        Extrae todos los productos de una categoría.

        Acepta Category o compatibilidad
        con url + nombre.
        """

        if isinstance(
            category,
            Category,
        ):
            category_url = category.url
            category_name = category.name

        else:
            category_url = category
            category_name = ""

        products = []

        pages = self.category_scraper.get_category_pages(
            category_url,
        )

        for page in pages:

            html = self.category_scraper.get_html(
                page,
            )

            if not html:
                continue

            soup = BeautifulSoup(
                html,
                "html.parser",
            )

            cards = self.card_extractor.extract(
                soup,
            )

            for card in cards:

                product = self.product_extractor.extract(
                    card,
                    url="",
                    category=category_name,
                )

                products.append(
                    product,
                )

        return products
