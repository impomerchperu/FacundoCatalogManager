from bs4 import BeautifulSoup

from scrapers.extractors.product_extractor import ProductExtractor
from scrapers.extractors.product_link_extractor import ProductLinkExtractor
from scrapers.product_scraper import ProductScraper


class ProductCollectionScraper:
    """
    Recorre una categoría completa:
    páginas -> productos -> datos producto
    """

    def __init__(
        self,
        category_scraper,
        product_link_extractor=None,
        product_scraper=None,
        product_extractor=None,
    ):

        self.category_scraper = category_scraper

        self.product_link_extractor = (
            product_link_extractor
            or ProductLinkExtractor()
        )

        self.product_scraper = (
            product_scraper
            or ProductScraper()
        )

        self.product_extractor = (
            product_extractor
            or ProductExtractor()
        )


    def scrape_category(self, category):

        products = []

        pages = self.category_scraper.get_category_pages(
            category.url
        )


        product_urls = []


        for page in pages:

            html = self.category_scraper.get_html(
                page
            )

            if not html:
                continue


            soup = BeautifulSoup(
                html,
                "html.parser"
            )


            urls = self.product_link_extractor.extract(
                soup
            )


            product_urls.extend(urls)



        product_urls = list(
            dict.fromkeys(product_urls)
        )


        for url in product_urls:

            soup = self.product_scraper.scrape(
                url
            )


            product = self.product_extractor.extract(
                soup,
                url=url,
                category=category.name,
            )


            products.append(product)


        return products