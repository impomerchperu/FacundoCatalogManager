from urllib.parse import unquote, urlsplit

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
            if product_rows:
                # Visual cards can include site-wide featured products in
                # addition to the category results. The table rows define the
                # category membership when both layouts disagree on products.
                if not self._same_product_set(cards, product_rows):
                    return product_rows
                if not self._visual_cards_have_complete_prices(cards):
                    return product_rows
            return cards

        if product_rows:
            return product_rows

        return soup.select(".jsfb-filterable")

    @staticmethod
    def _product_url_key(element):
        link = element.select_one('a[href*="/producto/"]')
        href = str(link.get("href", "") or "").strip() if link else ""
        if not href:
            return ""
        path = unquote(urlsplit(href).path).rstrip("/").casefold()
        return path

    @classmethod
    def _same_product_set(cls, cards, table_rows):
        visual_keys = [cls._product_url_key(card) for card in cards]
        table_keys = [cls._product_url_key(row) for row in table_rows]
        if not visual_keys or not table_keys:
            return False
        if any(not key for key in visual_keys + table_keys):
            return False
        if len(set(visual_keys)) != len(visual_keys):
            return False
        if len(set(table_keys)) != len(table_keys):
            return False
        return set(visual_keys) == set(table_keys)

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
