from bs4 import BeautifulSoup

from .product_parser import ProductParser


class Parser:

    def __init__(self):
        self.product_parser = ProductParser()

    def parse(self, html):
        """
        Convierte HTML en BeautifulSoup.
        """

        if not html:
            return None

        return BeautifulSoup(
            html,
            "html.parser"
        )

    def parse_product(
        self,
        html,
        url="",
        category=""
    ):
        """
        Convierte HTML de producto
        en ScrapedProduct.
        """

        return self.product_parser.parse(
            html,
            url=url,
            category=category
        )