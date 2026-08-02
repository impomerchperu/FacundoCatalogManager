from scrapers.extractors.product_extractor import ProductExtractor
from scrapers.product_scraper import ProductScraper

url = (
    "https://stock.importacionesfacundo.com/"
    "producto/jarro-mug-ecologico-con-tapa-600-ml/"
)


scraper = ProductScraper()

extractor = ProductExtractor()


soup = scraper.scrape(url)


product = extractor.extract(soup, url=url, category="Jarros Mug")


print(product)
