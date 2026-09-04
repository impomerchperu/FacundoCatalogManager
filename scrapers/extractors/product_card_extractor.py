from scrapers.selectors import product_card_selectors


class ProductCardExtractor:
    """
    Extrae tarjetas de producto desde una página de categoría.

    La plantilla puede publicar dos representaciones simultáneas: tarjetas
    visuales con los bloques de precios etiquetados y una tabla de productos.
    Priorizamos las tarjetas solo cuando toda la representación visual
    conserva los precios; si está incompleta, usamos la tabla para mantener
    los precios y la cobertura completa de productos.
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
        """Detecta si todos los productos visuales conservan precios etiquetados."""
        if not cards:
            return False

        for card in cards:
            if card.select_one(".content-precio"):
                continue
            text = card.get_text(" ", strip=True).casefold()
            if all(label in text for label in ("precio muestra", "precio ciento")):
                continue
            if all(label in text for label in ("precio muestra", "precio millar")):
                continue
            return False
        return True
