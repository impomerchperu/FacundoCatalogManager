from scrapers.browser import Browser
from scrapers.category_scraper import CategoryScraper
from scrapers.extractors.product_extractor import ProductExtractor


url = (
    "https://stock.importacionesfacundo.com/"
    "categoria-producto/jarros-mug/"
)


browser = Browser()


scraper = CategoryScraper(
    browser
)


html = scraper.get_html(
    url
)


print("=" * 80)
print("HTML:")
print(len(html))
print("=" * 80)


cards = scraper.extract_product_cards(
    html
)


print(
    "TOTAL CARDS:",
    len(cards)
)


card = cards[0]


print("=" * 80)
print("PRIMER CARD")
print("=" * 80)

print(
    card.prettify()[:5000]
)


extractor = ProductExtractor()


print("=" * 80)
print("IMAGEN EXTRAIDA")
print("=" * 80)


print(
    extractor.extract_image(
        card
    )
)