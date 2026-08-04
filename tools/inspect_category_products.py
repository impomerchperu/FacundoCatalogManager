from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.extractors.product_link_extractor import ProductLinkExtractor

BASE_URL = "https://stock.importacionesfacundo.com"


def main():

    extractor = ProductLinkExtractor()

    scraper = CategoryScraper(
        BASE_URL,
        extractor=extractor,
    )

    category_url = f"{BASE_URL}/categoria-producto/jarros-mug/"

    pages = scraper.get_category_pages(category_url)

    print("=" * 80)
    print("PÁGINAS ENCONTRADAS")
    print("=" * 80)

    for page in pages:
        print(page)

    print()

    print("=" * 80)
    print("PRODUCTOS")
    print("=" * 80)

    products = []

    for page in pages:
        urls = scraper.get_product_urls(page)

        print()
        print("PÁGINA:")
        print(page)

        print(
            "PRODUCTOS ENCONTRADOS:",
            len(urls),
        )

        for url in urls:
            print(url)

        products.extend(urls)

    print()

    print("=" * 80)
    print(
        "TOTAL PRODUCTOS:",
        len(products),
    )

    print("=" * 80)


if __name__ == "__main__":
    main()
