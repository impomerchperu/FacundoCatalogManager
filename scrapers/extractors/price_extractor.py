import re



class PriceExtractor:


    def _extract_price_block(
        self,
        soup,
        label
    ):


        heading = soup.find(
            lambda tag:
            tag.name in ["h3", "h4"]
            and label in tag.get_text()
        )


        if not heading:
            return 0.0


        price = heading.find_next(
            "h4"
        )


        if not price:
            return 0.0


        text = price.get_text(
            strip=True
        )


        numbers = re.findall(
            r"\d+(?:\.\d+)?",
            text
        )


        if numbers:

            return float(
                numbers[0]
            )


        return 0.0



    def extract_sample(
        self,
        soup
    ):

        return self._extract_price_block(
            soup,
            "Precio Muestra"
        )



    def extract_hundred(
        self,
        soup
    ):

        return self._extract_price_block(
            soup,
            "Precio Ciento"
        )



    def extract_thousand(
        self,
        soup
    ):

        return self._extract_price_block(
            soup,
            "Precio Millar"
        )