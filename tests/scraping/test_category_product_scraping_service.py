from scrapers.parser.category_product_parser import (
    CategoryProductParser,
)
from scrapers.services.category_product_scraping_service import (
    CategoryProductScrapingService,
)


class FakeScraper:
    def get_category_pages(self, url):

        return [
            url,
        ]

    def get_product_blocks(self, url):

        from bs4 import BeautifulSoup

        html = """
        <div class="jsfb-query--querymovil">

            <p>FB-1812</p>

            <h2>
                Taza de Plástico
            </h2>

            <img
            data-src="https://site.com/FB-1812.webp"
            >

        </div>
        """

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        return [soup.select_one(".jsfb-query--querymovil")]


def test_category_product_scraping_service():

    service = CategoryProductScrapingService(
        FakeScraper(),
        CategoryProductParser(),
    )

    products = service.scrape_category("https://example.com/categoria")

    assert len(products) == 1

    assert products[0].code == "FB-1812"

    assert products[0].name == "Taza de Plástico"
