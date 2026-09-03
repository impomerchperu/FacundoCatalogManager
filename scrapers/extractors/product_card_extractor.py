from scrapers.selectors import product_card_selectors


class ProductCardExtractor:
    """
    Extrae tarjetas de producto desde una página de categoría.

    La plantilla puede publicar dos representaciones simultáneas: tarjetas
    visuales con los bloques de precios etiquetados y una tabla de productos.
    Priorizamos las tarjetas cuando conservan esos precios; si no, usamos la
    tabla para mantener la cobertura completa de productos/páginas.
    """

    def extract(self, soup):
        cards = soup.select(product_card_selectors.PRODUCT_CARD)
        if cards and self._cards_have_labeled_prices(cards):
            return cards

        table_rows = soup.select("table tbody tr")
        product_rows = [
            row
            for row in table_rows
            if row.select_one('a[href*="/producto/"]')
        ]
        if product_rows:
            return product_rows

        if cards:
            return cards

        return soup.select(".jsfb-filterable")

    @staticmethod
    def _cards_have_labeled_prices(cards):
        """Detecta la representación histórica que conserva los precios."""
        for card in cards:
            if card.select_one(".content-precio"):
                return True
            text = card.get_text(" ", strip=True).casefold()
            if all(label in text for label in ("precio muestra", "precio ciento")):
                return True
            if all(label in text for label in ("precio muestra", "precio millar")):
                return True
        return False
