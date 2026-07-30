from scrapers.browser import Browser
from scrapers.parser import Parser


class ProductScraper:

    def __init__(
        self,
        browser=None,
        parser=None
    ):

        self.browser = browser or Browser()
        self.parser = parser or Parser()


    def scrape(
        self,
        url
    ):

        html = self.browser.fetch(
            url
        )

        soup = self.parser.parse(
            html
        )

        return soup