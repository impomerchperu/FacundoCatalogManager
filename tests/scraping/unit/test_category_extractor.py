from scrapers.browser import Browser
from scrapers.extractors.category_extractor import CategoryExtractor
from scrapers.parser import Parser

url = "https://stock.importacionesfacundo.com/tienda/"


browser = Browser()

parser = Parser()

html = browser.get(url)

soup = parser.parse(html)


extractor = CategoryExtractor()

categories = extractor.extract(soup)


for category in categories:
    print(category.name, "->", category.url)


print("Total:", len(categories))
