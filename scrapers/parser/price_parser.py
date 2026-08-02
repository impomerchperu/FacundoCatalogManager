import re


class PriceParser:
    """
    Parser de precios del catálogo Facundo.

    Extrae:
    - Precio muestra
    - Precio ciento
    - Precio millar
    """

    def clean_price(self, text):
        """
        Convierte:
        S/ 1,100.00

        en:

        1100.00
        """

        if not text:
            return 0

        text = (
            text
            .replace("S/", "")
            .replace(",", "")
            .strip()
        )

        match = re.search(
            r"\d+\.?\d*",
            text
        )

        if match:
            return float(match.group())

        return 0


    def extract_prices(self, product):

        prices = {
            "sample": 0,
            "hundred": 0,
            "thousand": 0,
        }


        for block in product.select(".content-precio"):

            title = block.find("h3")
            value = block.find("h4")


            if not title or not value:
                continue


            number = self.clean_price(
                value.text
            )


            label = title.text.strip()


            if "Muestra" in label:
                prices["sample"] = number

            elif "Ciento" in label:
                prices["hundred"] = number

            elif "Millar" in label:
                prices["thousand"] = number


        return prices