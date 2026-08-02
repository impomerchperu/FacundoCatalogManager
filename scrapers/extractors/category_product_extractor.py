from models.scraping.scraped_product import ScrapedProduct
from scrapers.extractors.price_extractor import PriceExtractor


class CategoryProductExtractor:
    """
    Extrae productos desde tarjetas de categoría
    generadas por Bricks Builder + Jet Engine.
    """

    SOURCE = "importacionesfacundo"


    def __init__(self):

        self.price_extractor = PriceExtractor()



    def extract(
        self,
        card,
        url="",
        category=""
    ):

        return ScrapedProduct(

            source=self.SOURCE,

            url=url or self._url(card),

            code=self._code(card),

            name=self._name(card),

            category=category,

            description=self._description(card),

            stock=self._stock(card),

            price_sample=(
                self.price_extractor.extract_sample(
                    card
                )
            ),

            price_hundred=(
                self.price_extractor.extract_hundred(
                    card
                )
            ),

            price_thousand=(
                self.price_extractor.extract_thousand(
                    card
                )
            ),

            image_url=self._image(card)

        )



    # --------------------------------------------------
    # URL PRODUCTO
    # --------------------------------------------------

    def _url(self, soup):

        element = soup.select_one(
            'a[href*="/producto/"]'
        )

        if not element:
            return ""

        return element.get(
            "href",
            ""
        )



    # --------------------------------------------------
    # CODIGO
    # --------------------------------------------------

    def _code(self, soup):

        element = soup.select_one(
            "p.brxe-a26f34"
        )

        if not element:
            return ""

        return element.get_text(
            strip=True
        )



    # --------------------------------------------------
    # NOMBRE
    # --------------------------------------------------

    def _name(self, soup):

        element = soup.select_one(
            "h2.brxe-f31760"
        )

        if not element:
            return ""

        return element.get_text(
            " ",
            strip=True
        )



    # --------------------------------------------------
    # DESCRIPCION
    # --------------------------------------------------

    def _description(self, soup):

        element = soup.select_one(
            ".text-content"
        )

        if not element:
            return ""

        return element.get_text(
            " ",
            strip=True
        )



    # --------------------------------------------------
    # STOCK
    # --------------------------------------------------

    def _stock(self, soup):

        values = soup.select(
            ".variaciones-producto p"
        )


        total = 0


        for value in values:

            text = value.get_text(
                strip=True
            )


            if text.isdigit():

                total += int(text)


        return total



    # --------------------------------------------------
    # IMAGEN
    # --------------------------------------------------

    def _image(self, soup):

        images = soup.select(
            'a[href*="/producto/"] img'
        )


        for image in images:

            url = (

                image.get(
                    "data-src"
                )

                or

                image.get(
                    "src"
                )

                or

                ""

            )


            if not url:
                continue


            # Ignorar placeholder
            if "data:image" in url:
                continue


            # Ignorar categoría próximo ingreso
            if "Proximo" in url:
                continue


            # Ignorar logos
            if "Logo" in url:
                continue


            return self._normalize_image_url(
                url
            )


        return ""



    # --------------------------------------------------
    # NORMALIZAR IMAGEN ORIGINAL
    # --------------------------------------------------

    def _normalize_image_url(
        self,
        url
    ):

        replacements = [

            "-150x150",

            "-300x300",

            "-600x600",

            "-768x768",

            "-1024x1024"

        ]


        for item in replacements:

            url = url.replace(
                item,
                ""
            )


        return url