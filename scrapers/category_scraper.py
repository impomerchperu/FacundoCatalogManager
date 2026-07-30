class CategoryScraper:
    def __init__(self, browser, parser):
        self.browser = browser
        self.parser = parser

    def scrape(self, url):
        html = self.browser.get(url)
        return self.parser.extract_categories(html)