import re

from models.scraping.scraped_product import ScrapedProduct
from scrapers.extractors.price_extractor import PriceExtractor


class CategoryProductExtractor:
    """Extrae productos desde tarjetas de categoría Bricks + Jet Engine."""

    SOURCE = "importacionesfacundo"

    def __init__(self):
        self.price_extractor = PriceExtractor()

    def extract(self, card, url="", category=""):
        colors, color_stock = self._colors(card)
        return ScrapedProduct(
            source=self.SOURCE,
            url=url or self._url(card),
            code=self._code(card),
            name=self._name(card),
            category=category,
            description=self._description(card),
            stock=self._stock(card),
            price_sample=self.price_extractor.extract_sample(card),
            price_hundred=self.price_extractor.extract_hundred(card),
            price_thousand=self.price_extractor.extract_thousand(card),
            colors=colors,
            color_stock=color_stock,
            image_url=self._image(card),
        )

    def _url(self, soup):
        element = soup.select_one('a[href*="/producto/"]')
        return element.get("href", "") if element else ""

    def _code(self, soup):
        element = soup.select_one("p.brxe-a26f34")
        return element.get_text(strip=True) if element else ""

    def _name(self, soup):
        element = soup.select_one("h2.brxe-f31760")
        return element.get_text(" ", strip=True) if element else ""

    def _description(self, soup):
        element = soup.select_one(".text-content")
        return element.get_text(" ", strip=True) if element else ""

    def _stock(self, soup):
        values = soup.select(".variaciones-producto p")
        total = 0
        for value in values:
            text = value.get_text(strip=True)
            if text.isdigit():
                total += int(text)
        return total

    def _colors(self, soup) -> tuple[list[str], dict[str, int]]:
        colors: list[str] = []
        color_stock: dict[str, int] = {}

        def add_color(name: str, stock: int | None = None) -> None:
            value = re.sub(r"\s+", " ", str(name)).strip()
            if not value or value.casefold() in {
                "color", "colour", "seleccionar color", "sin color",
            }:
                return
            if value not in colors:
                colors.append(value)
            if stock is not None:
                color_stock[value] = max(color_stock.get(value, 0), stock)

        for element in soup.select(
            ".variaciones-producto [data-color], "
            ".variaciones-producto [data-value], "
            ".variaciones-producto [title], "
            ".variaciones-producto .color, "
            ".variaciones-producto .color-name, "
            ".variaciones-producto .swatch",
        ):
            name = (
                element.get("data-color")
                or element.get("data-value")
                or element.get("title")
                or element.get_text(" ", strip=True)
            )
            stock = self._stock_attribute(element)
            add_color(name, stock)

        for select in soup.select("select"):
            selector_text = " ".join(
                str(select.get(key, ""))
                for key in ("name", "id", "class")
            ).casefold()
            if "color" not in selector_text and "colour" not in selector_text:
                continue
            for option in select.select("option"):
                name = option.get_text(" ", strip=True) or option.get("value", "")
                add_color(name, self._stock_attribute(option))

        return colors, color_stock

    @staticmethod
    def _stock_attribute(element) -> int | None:
        for key in ("data-stock", "data-quantity", "data-max-qty", "data-max_quantity"):
            value = element.get(key)
            if value is not None:
                try:
                    return int(float(str(value).strip()))
                except ValueError:
                    pass
        return None

    def _image(self, soup):
        images = soup.select('a[href*="/producto/"] img')
        for image in images:
            url = image.get("data-src") or image.get("src") or ""
            if not url or "data:image" in url:
                continue
            if "Proximo" in url or "Logo" in url:
                continue
            return self._normalize_image_url(url)
        return ""

    @staticmethod
    def _normalize_image_url(url):
        for item in (
            "-150x150",
            "-300x300",
            "-600x600",
            "-768x768",
            "-1024x1024",
        ):
            url = url.replace(item, "")
        return url
