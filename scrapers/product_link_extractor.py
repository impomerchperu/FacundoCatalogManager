from scrapers.selectors.product_selectors import ProductSelectors


class ProductLinkExtractor:

    def extract(self, soup):

        urls = []

        for link in soup.select(ProductSelectors.PRODUCT_LINK):

            href = link.get("href")

            if href:
                urls.append(href)

        return list(dict.fromkeys(urls))