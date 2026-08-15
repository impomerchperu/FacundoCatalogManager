from scrapers.product_scraper import ProductScraper
from services.scraping.scraped_product_mapper import ScrapedProductMapper


def test_product_scraper_returns_product():

    scraper = ProductScraper()
    mapper = ScrapedProductMapper()

    soup = scraper.scrape("https://example.com")

    product = mapper.map(soup, "https://example.com")

    assert product.url == "https://example.com"
    assert product.name != ""
