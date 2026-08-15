from bs4 import BeautifulSoup


class ProductBlockExtractor:
    """
    Extrae bloques de productos desde una página categoría.
    """

    SELECTOR = ".jsfb-filterable"

    def extract(self, soup: BeautifulSoup):

        if soup is None:
            return []

        return soup.select(self.SELECTOR)
