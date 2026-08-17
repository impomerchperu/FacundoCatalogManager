from scrapers.selectors import product_card_selectors


class ProductCardExtractor:
    """
    Extrae tarjetas de producto desde una página de categoría.

    La página actual publica una tabla completa de productos además del
    bloque visual limitado a 25 tarjetas. Preferimos las filas de esa tabla
    cuando están disponibles para no truncar categorías grandes.
    """

    def extract(self, soup):
        table_rows = soup.select("table tbody tr")
        product_rows = [
            row
            for row in table_rows
            if row.select_one('a[href*="/producto/"]')
        ]
        if product_rows:
            return product_rows

        return soup.select(product_card_selectors.PRODUCT_CARD)
