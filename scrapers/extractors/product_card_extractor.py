from scrapers.selectors import product_card_selectors


class ProductCardExtractor:
    """Extrae tarjetas visuales de producto desde una página de categoría."""

    def extract(self, soup):
        cards = soup.select(product_card_selectors.PRODUCT_CARD)
        if cards:
            return cards

        table_rows = soup.select("table tbody tr")
        product_rows = [
            row
            for row in table_rows
            if row.select_one('a[href*="/producto/"]')
        ]
        if product_rows:
            return product_rows

        return soup.select(".jsfb-filterable")
