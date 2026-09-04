from scrapers.selectors import product_card_selectors


class ProductCardExtractor:
    """Extrae la representación de productos con precios disponibles."""

    _PRICE_LABELS = (
        "Precio Muestra",
        "Precio Ciento",
        "Precio Millar",
    )

    def extract(self, soup):
        cards = soup.select(product_card_selectors.PRODUCT_CARD)
        table_rows = soup.select("table tbody tr")
        product_rows = [
            row
            for row in table_rows
            if row.select_one('a[href*="/producto/"]')
        ]

        if cards:
            if product_rows and not self._visual_cards_have_complete_prices(cards):
                return product_rows
            return cards

        if product_rows:
            return product_rows

        return soup.select(".jsfb-filterable")

    @classmethod
    def _visual_cards_have_complete_prices(cls, cards):
        """Confirma que cada tarjeta visual conserva los tres precios."""
        for card in cards:
            for label in cls._PRICE_LABELS:
                if not cls._has_price_for_label(card, label):
                    return False
        return True

    @staticmethod
    def _has_price_for_label(card, label):
        label_normalized = label.casefold()
        for block in card.select(".content-precio"):
            title = block.find(["h3", "h4"])
            if title is None:
                continue
            title_text = " ".join(title.stripped_strings).casefold()
            if label_normalized not in title_text:
                continue
            values = block.find_all(["h3", "h4"])
            for value in reversed(values):
                if value is title:
                    continue
                text = " ".join(value.stripped_strings)
                if any(char.isdigit() for char in text):
                    return True
        return False
