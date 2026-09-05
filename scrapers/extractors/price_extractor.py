import re
from typing import ClassVar


class PriceExtractor:
    """Extrae los tres precios de las tarjetas de producto."""

    _FIELDS: ClassVar[dict[str, str]] = {
        "muestra": "sample",
        "ciento": "hundred",
        "millar": "thousand",
    }
    _PRICE_LABELS: ClassVar[tuple[str, ...]] = (
        "Precio Muestra",
        "Precio Ciento",
        "Precio Millar",
    )

    def _extract_price_block(self, soup, label):
        """Extrae un precio a partir de un bloque etiquetado."""
        blocks = soup.select(".content-precio")
        label_normalized = label.casefold()

        for block in blocks:
            title = block.find(["h3", "h4"])
            if title is None:
                continue

            title_text = " ".join(title.get_text(" ", strip=True).split())
            if label_normalized not in title_text.casefold():
                continue

            value = block.find_all(["h3", "h4"])
            for element in reversed(value):
                if element is title:
                    continue
                price = self._parse_price(element.get_text(" ", strip=True))
                if price is not None:
                    return price

            price = self._parse_price(block.get_text(" ", strip=True))
            if price is not None:
                return price

        heading = soup.find(
            lambda tag: tag.name in ["h3", "h4"]
            and label_normalized in tag.get_text(" ", strip=True).casefold()
        )
        if heading is not None:
            for element in heading.find_all_next(["h3", "h4", "div", "span"]):
                text = element.get_text(" ", strip=True)
                if self._contains_other_price_label(text, label_normalized):
                    break
                parsed = self._parse_price(text)
                if parsed is not None:
                    return parsed

        table_price = self._extract_table_row_price(soup, label_normalized)
        if table_price is not None:
            return table_price

        return self._extract_labeled_price_from_text(soup, label)

    @classmethod
    def _contains_other_price_label(cls, text, current_label):
        normalized = text.casefold()
        return any(
            label.casefold() != current_label and label.casefold() in normalized
            for label in cls._PRICE_LABELS
        )

    @staticmethod
    def _table_rows(soup):
        """Obtiene las filas de tabla relevantes para la tarjeta."""
        rows = []
        if getattr(soup, "name", "") == "tr":
            rows.append(soup)
        rows.extend(soup.select("tr.jsfb-filterable"))
        if not rows:
            rows.extend(soup.select("table tbody tr"))
        return rows

    def _extract_table_row_price(self, soup, label_normalized):
        """Recupera precios de filas Bricks aunque cambie el markup de las celdas."""
        for row in self._table_rows(soup):
            cells = row.find_all("td", recursive=False)
            if len(cells) < 3:
                continue
            price_cells = self._table_price_cells(cells)
            price = self._match_table_price(price_cells, label_normalized)
            if price is not None:
                return price
        return None

    def _table_price_cells(self, cells):
        """Extrae importe y texto de umbral desde las celdas de precio."""
        price_cells = []
        for cell in cells:
            text = " ".join(cell.stripped_strings)
            if not re.search(r"\b(?:menos de|a partir de)\b", text.casefold()):
                continue
            value = self._parse_price(text)
            if value is not None:
                price_cells.append((text.casefold(), value))
        return price_cells

    @staticmethod
    def _match_table_price(price_cells, label_normalized):
        """Selecciona el importe correspondiente al nivel solicitado."""
        matchers = {
            "precio muestra": lambda text: "menos de" in text,
            "precio ciento": lambda text: "a partir de" in text and "50" in text,
            "precio millar": lambda text: "a partir de" in text and "500" in text,
        }
        matcher = matchers.get(label_normalized)
        if matcher is None:
            return None
        for text, value in price_cells:
            if matcher(text):
                return value
        return None

    def _extract_labeled_price_from_text(self, soup, label):
        """Recupera el importe aunque la plantilla no conserve clases CSS."""
        text = " ".join(soup.stripped_strings)
        pattern = re.compile(
            rf"{re.escape(label)}\s*[:\-]?\s*"
            rf"(?:S/|US\$|USD|\$)?\s*([\d][\d,.]*)",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match is None:
            return 0.0
        return self._parse_price(match.group(1)) or 0.0

    @staticmethod
    def _parse_price(text):
        """Convierte importes monetarios comunes del sitio a float."""
        cleaned = text.replace("S/", "").replace("US$", "")
        cleaned = cleaned.replace("USD", "").replace("$", "").strip()

        match = re.search(r"\d[\d,.]*", cleaned)
        if match is None:
            return None

        raw = match.group(0)
        if "," in raw and "." in raw:
            if raw.rfind(",") > raw.rfind("."):
                raw = raw.replace(".", "").replace(",", ".")
            else:
                raw = raw.replace(",", "")
        elif "," in raw:
            raw = raw.replace(",", ".")

        try:
            return float(raw)
        except ValueError:
            return None

    def extract_sample(self, soup):
        return self._extract_price_block(soup, "Precio Muestra")

    def extract_hundred(self, soup):
        return self._extract_price_block(soup, "Precio Ciento")

    def extract_thousand(self, soup):
        return self._extract_price_block(soup, "Precio Millar")
