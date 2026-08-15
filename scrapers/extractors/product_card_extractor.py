from scrapers.selectors import product_card_selectors


class ProductCardExtractor:
    """
    Extrae tarjetas de producto desde una página categoría.

    NO transforma datos.
    Solo devuelve bloques HTML de productos.

    La transformación a ScrapedProduct
    la realiza CategoryProductExtractor.
    """

    def extract(self, soup):

        return soup.select(product_card_selectors.PRODUCT_CARD)
