from scrapers.browser import Browser
from scrapers.parser import Parser
from scrapers.product_link_extractor import ProductLinkExtractor

browser = Browser()
parser = Parser()
extractor = ProductLinkExtractor()

url = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"

html = browser.fetch(url)

soup = parser.parse(html)

products = extractor.extract(soup)

print("=" * 80)
print("TOTAL PRODUCTOS:", len(products))
print("=" * 80)

for product in products:
    print(product)
