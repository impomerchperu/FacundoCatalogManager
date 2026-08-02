from models.scraping.scraped_product import ScrapedProduct
from scrapers.selectors import product_selectors


class ProductExtractor:

    SOURCE = "importacionesfacundo"


    def extract(
        self,
        soup,
        url="",
        category=""
    ):

        return ScrapedProduct(

            source=self.SOURCE,

            url=url,

            code=self._extract_text(
                soup,
                product_selectors.PRODUCT_SKU
            ),

            name=self._extract_name(soup),

            category=category,

            description=self._extract_description(
                soup
            ),

            stock=self._extract_stock(
                soup
            ),

            price=self._extract_price(
                soup
            ),

            image_url=self._extract_image(
                soup
            )
        )


    def _extract_name(self, soup):

        selectors = [

            product_selectors.PRODUCT_NAME,

            ".product-name",

            "h1"

        ]


        for selector in selectors:

            element = soup.select_one(selector)

            if element:

                return element.get_text(
                    " ",
                    strip=True
                )


        return ""



    def _extract_text(
        self,
        soup,
        selector
    ):

        if not selector:
            return ""


        element = soup.select_one(selector)


        if not element:
            return ""


        return element.get_text(
            " ",
            strip=True
        )



    def _extract_price(self, soup):

        selectors = [

            ".price",

            ".product-price",

        ]


        for selector in selectors:

            element = soup.select_one(selector)


            if element:

                text = element.get_text(
                    strip=True
                )


                numbers = (
                    text
                    .replace(",","")
                    .replace("$","")
                    .strip()
                )


                try:
                    return float(numbers)

                except ValueError:
                    pass


        return 0.0



    def _extract_description(
        self,
        soup
    ):

        selectors = [

            ".product-description",

            ".description",

            ".brxe-text"

        ]


        for selector in selectors:

            element = soup.select_one(selector)


            if element:

                return element.get_text(
                    " ",
                    strip=True
                )


        return ""



    def _extract_stock(
        self,
        soup
    ):

        element = soup.select_one(
            product_selectors.PRODUCT_STOCK
        )


        if not element:
            return 0


        text = element.get_text(
            " ",
            strip=True
        )


        numbers = "".join(
            x for x in text
            if x.isdigit()
        )


        return int(numbers) if numbers else 0



    def _extract_image(
        self,
        soup
    ):

        selectors = [

            product_selectors.PRODUCT_IMAGE,

            ".product-image"

        ]


        for selector in selectors:

            element = soup.select_one(selector)


            if element:

                return (
                    element.get("src")
                    or element.get("data-src")
                    or ""
                )


        return ""