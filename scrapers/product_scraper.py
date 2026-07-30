from scrapers.browser import Browser
from scrapers.parser import Parser


class ProductScraper:

    def __init__(self):

        self.browser = Browser()
        self.parser = Parser()


    def scrape(self, url):

        html = self.browser.fetch(url)

        soup = self.parser.parse(
            html
        )

        return soup