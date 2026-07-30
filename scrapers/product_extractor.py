from scrapers.selectors import product_selectors


class ProductExtractor:

    def extract(self, soup):

        name = ""
        price = 0.0
        image_url = ""
        description = ""


        name_element = soup.select_one(
            product_selectors.PRODUCT_NAME
        )

        if name_element:
            name = name_element.text.strip()


        price_element = soup.select_one(
            product_selectors.PRODUCT_PRICE
        )

        if price_element:
            price_text = price_element.text.strip()

            try:
                price = float(
                    price_text
                )
            except ValueError:
                price = 0.0


        image_element = soup.select_one(
            product_selectors.PRODUCT_IMAGE
        )

        if image_element:
            image_url = image_element.get(
                "src",
                ""
            )


        description_element = soup.select_one(
            product_selectors.PRODUCT_DESCRIPTION
        )

        if description_element:
            description = description_element.text.strip()


        return {
            "name": name,
            "price": price,
            "image_url": image_url,
            "description": description
        }