from scrapers.collectors.category_scraper import CategoryScraper

BASE_URL = "https://stock.importacionesfacundo.com"


CATEGORY_URL = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"


scraper = CategoryScraper(BASE_URL)


pages = scraper.get_category_pages(CATEGORY_URL)


print("=" * 80)
print("PÁGINAS ENCONTRADAS")
print("=" * 80)


for page in pages:
    print(page)


print("=" * 80)
print("TOTAL:", len(pages))
