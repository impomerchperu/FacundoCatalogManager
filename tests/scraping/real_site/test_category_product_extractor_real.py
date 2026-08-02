from bs4 import BeautifulSoup

from scrapers.browser import Browser
from scrapers.extractors.category_product_extractor import (
    CategoryProductExtractor,
)


url = (
    "https://stock.importacionesfacundo.com/"
    "categoria-producto/jarros-mug/"
)


browser = Browser()

html = browser.fetch(url)


soup = BeautifulSoup(
    html,
    "html.parser"
)


cards = soup.select(
    ".jsfb-filterable"
)


print("=" * 80)
print("TOTAL TARJETAS:", len(cards))
print("=" * 80)


extractor = CategoryProductExtractor()


for card in cards[:5]:

    product_link = card.select_one(
        "a[href*='/producto/']"
    )


    if not product_link:
        continue


    product = extractor.extract(
        card,
        url=product_link.get("href"),
        category="Jarros Mug"
    )


    print(product)
    break