from scrapers.browser import Browser
from scrapers.extractors.category_extractor import CategoryExtractor
from scrapers.parser import Parser

browser = Browser()
parser = Parser()


html = browser.fetch("https://stock.importacionesfacundo.com/tienda/")


soup = parser.parse(html)


extractor = CategoryExtractor()


categories = extractor.extract(soup)


print("=" * 80)

print("TOTAL CATEGORIAS:", len(categories))

print("=" * 80)


for category in categories:
    print(category.name, "->", category.url)
