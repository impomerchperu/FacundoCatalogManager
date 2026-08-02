from scrapers.browser import Browser
from scrapers.parser import Parser
from scrapers.extractors.product_link_extractor import ProductLinkExtractor

url = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"


browser = Browser()

parser = Parser()

html = browser.get(url)

soup = parser.parse(html)


extractor = ProductLinkExtractor()

products = extractor.extract(soup)


for product in products:
    print(product)


print("Total productos:", len(products))
