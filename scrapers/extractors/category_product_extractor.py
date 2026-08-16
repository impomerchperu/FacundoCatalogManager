import re

from models.scraping.scraped_product import ScrapedProduct
from scrapers.extractors.price_extractor import PriceExtractor


class CategoryProductExtractor:
    """Extrae productos desde tarjetas de categoría Bricks + Jet Engine."""

    SOURCE = "importacionesfacundo"

    def __init__(self):
        self.price_extractor = PriceExtractor()

    def extract(self, card, url="", category=""):
        color_stock = self._color_stock(card)
        stock_values = self._stock_values(card)
        total_stock = sum(stock_values) if stock_values else self._stock(card)
        if color_stock and len(color_stock) == len(stock_values):
            total_stock = sum(color_stock.values())

        return ScrapedProduct(
            source=self.SOURCE,
            url=url or self._url(card),
            code=self._code(card),
            name=self._name(card),
            category=category,
            description=self._description(card),
            stock=total_stock,
            price_sample=self.price_extractor.extract_sample(card),
            price_hundred=self.price_extractor.extract_hundred(card),
            price_thousand=self.price_extractor.extract_thousand(card),
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
        return sum(self._stock_values(soup))

    def _stock_values(self, soup) -> list[int]:
        """Extrae los valores de stock visibles en la tarjeta."""
        values: list[int] = []
        for value in soup.select(".variaciones-producto p"):
            text = value.get_text(" ", strip=True)
            if text.isdigit():
                values.append(int(text))
                continue

            match = re.match(r"^.+?\s*[:\-]\s*(\d[\d,.]*)\s*$", text)
            if match:
                try:
                    values.append(int(float(match.group(1).replace(",", ""))))
                except ValueError:
                    continue

        if values:
            return values

        text = soup.get_text(" ", strip=True)
        match = re.search(
            r"stock\s+disponible\s*((?:\d[\d,.]*\s*)+)",
            text,
            flags=re.IGNORECASE,
        )
        if match is None:
            return []

        for raw_value in re.findall(r"\d[\d,.]*", match.group(1)):
            try:
                values.append(int(float(raw_value.replace(",", ""))))
            except ValueError:
                continue
        return values

    def _color_stock(self, soup) -> dict[str, int]:
        color_stock: dict[str, int] = {}

        def add_color(name: str, stock: int | None = None) -> None:
            value = re.sub(r"\s+", " ", str(name)).strip(" :-.")
            if not value or value.casefold() in {
                "color",
                "colour",
                "colores",
                "seleccionar color",
                "sin color",
            }:
                return
            color_stock.setdefault(value, 0)
            if stock is not None:
                color_stock[value] = max(
                    color_stock.get(value, 0),
                    max(stock, 0),
                )

        variation = soup.select_one(".variaciones-producto")
        if variation:
            for element in variation.select(
                "[data-color], [data-value], [title], .color, "
                ".color-name, .swatch",
            ):
                name = (
                    element.get("data-color")
                    or element.get("data-value")
                    or element.get("title")
                    or element.get_text(" ", strip=True)
                )
                add_color(name, self._stock_attribute(element))

            for paragraph in variation.select("p"):
                text = re.sub(
                    r"\s+",
                    " ",
                    paragraph.get_text(" ", strip=True),
                )
                match = re.match(r"^(.+?)\s*[:\-]\s*(\d+)\s*$", text)
                if match:
                    add_color(match.group(1), int(match.group(2)))

        self._extract_labeled_colors(soup, add_color)

        stock_values = self._stock_values(soup)
        color_names = list(color_stock)
        if len(stock_values) == len(color_names):
            for color, stock in zip(color_names, stock_values, strict=True):
                color_stock[color] = stock
        else:
            color_stock.clear()

        return color_stock

    @staticmethod
    def _extract_labeled_colors(soup, add_color) -> None:
        """Extrae colores declarados en la descripción de la tarjeta."""
        patterns = (
            re.compile(
                r"\b(?:\d+\s+)?colores?\s+de\s+tinta\s*[:|\-]\s*(.+?)"
                r"(?=\s+(?:stock\s+disponible|precio|presentaci[oó]n|"
                r"c[oó]digo|sku|categor[ií]as?)\b|$)",
                flags=re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:\d+\s+)?colores?\s*[:|\-]\s*(.+?)"
                r"(?=\s+(?:stock\s+disponible|precio|presentaci[oó]n|"
                r"c[oó]digo|sku|categor[ií]as?)\b|$)",
                flags=re.IGNORECASE,
            ),
        )

        for element in soup.find_all(string=True):
            text = re.sub(r"\s+", " ", str(element)).strip()
            if not text:
                continue

            match = next(
                (pattern.search(text) for pattern in patterns if pattern.search(text)),
                None,
            )
            if match is None:
                continue

            normalized = match.group(1).strip(" .|-")
            normalized = re.sub(r"\s*\([^)]*\)\s*$", "", normalized)
            normalized = re.sub(r"\s+(?:y|e)\s+", ", ", normalized)
            for item in normalized.split(","):
                add_color(item)

    @staticmethod
    def _stock_attribute(element) -> int | None:
        for key in (
            "data-stock",
            "data-quantity",
            "data-max-qty",
            "data-max_quantity",
        ):
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
