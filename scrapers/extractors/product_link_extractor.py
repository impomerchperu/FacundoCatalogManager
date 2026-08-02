from scrapers.selectors.product_selectors import ProductSelectors


class ProductLinkExtractor:


    def extract(self, soup):

        if soup is None:
            return []


        links = soup.select(
            ProductSelectors.PRODUCT_LINK
        )


        if not links:

            links = soup.find_all(
                "a",
                href=True
            )


        urls = []


        for link in links:

            url = link.get(
                "href",
                ""
            )


            if url:

                urls.append(url)


        return list(
            dict.fromkeys(urls)
        )