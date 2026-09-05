import re
from typing import ClassVar


class PriceExtractor:
    """Extrae los tres precios de las tarjetas de producto."""

    _PRICE_LABELS: ClassVar[tuple[str, ...]] = (
        "Precio Muestra",
        "Precio Ciento",
        "Precio Millar",
        "Precio Caja",
        "Precio Por Caja",
    )

    def _extract_price_block(self, soup, label):
        """Extrae el precio manteniendo la estrategia histórica del scraper."""
        label_normalized = label.casefold()

        heading = soup.find(
            lambda tag: tag.name in ["h3", "h4"]
            and label_normalized in tag.get_text(" ", strip=True).casefold()
        )
        if heading is not None:
            price = self._next_labeled_price(heading, label_normalized)
            if price is not None:
                return price

        blocks = soup.select(".content-precio")
        for block in blocks:
            title = block.find(["h3", "h4"])
            if title is None:
                continue
            title_text = " ".join(title.get_text(" ", strip=True).split())
            if label_normalized not in title_text.casefold():
                continue
            price = self._price_from_elements(block.find_all(["h3", "h4"]))
            if price is not None:
                return price
            price = self._price_from_text(block.get_text(" ", strip=True))
            if price is not None:
                return price

        table_price = self._extract_table_row_price(soup, label_normalized)
        if table_price is not None:
            return table_price

        return self._extract_labeled_price_from_text(soup, label)

    def _next_labeled_price(self, heading, label_normalized):
        """Busca el valor siguiente sin saltar al siguiente nivel de precio."""
        for element in heading.find_all_next(["h3", "h4", "div", "span"]):
            text = " ".join(element.get_text(" ", strip=True).split())
            if self._contains_other_price_label(text, label_normalized):
                break
            if element.name in ["h3", "h4"]:
                price = self._parse_price(element.get_text(" ", strip=True))
                if price is not None:
                    return price
            if element.name in ["div", "span"]:
                price = self._price_from_text(text)
                if price is not None:
                    return price
        return None

    @classmethod
    def _contains_other_price_label(cls, text, current_label):
        normalized = text.casefold()
        return any(
            label.casefold() != current_label and label.casefold() in normalized
            for label in cls._PRICE_LABELS
        )

    @staticmethod
    def _price_from_elements(elements):
        for element in reversed(elements):
            price = PriceExtractor._parse_price(element.get_text(" ", strip=True))
            if price is not None:
                return price
        return None

    @staticmethod
    def _price_from_text(text):
        matches = re.findall(
            r"(?:S/|US\$|USD|\$)\s*([\d][\d,.]*)",
            text,
            flags=re.IGNORECASE,
        )
        if matches:
            return PriceExtractor._parse_price(matches[-1])
        return None

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
        """Extrae importes de las columnas de precios de la tabla."""
        price_cells = []
        for cell in cells:
            text = " ".join(cell.stripped_strings)
            value = self._price_from_text(text)
            if value is None:
                continue
            price_cells.append((text.casefold(), value))
        return price_cells

    @staticmethod
    def _match_table_price(price_cells, label_normalized):
        """Selecciona el importe correspondiente al nivel solicitado."""
        matchers = {
            "precio muestra": r"\bmenos de\s+\d+\s+unidades?\b",
            "precio ciento": r"\ba partir(?: de)?\s+50\s+unidades?\b",
            "precio millar": r"\ba partir(?: de)?\s+500\s+unidades?\b",
            "precio caja": r"\ba partir(?: de)?\s+\d+\s+unidades?\b",
            "precio por caja": r"\ba partir(?: de)?\s+\d+\s+unidades?\b",
        }
        pattern = matchers.get(label_normalized)
        if pattern is not None:
            for text, value in price_cells:
                if re.search(pattern, text):
                    return value

        positions = {
            "precio muestra": 0,
            "precio ciento": 1,
            "precio caja": 1,
            "precio por caja": 1,
            "precio millar": 2,
        }
        position = positions.get(label_normalized)
        if position is not None and position < len(price_cells):
            return price_cells[position][1]
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
        price = self._extract_price_block(soup, "Precio Ciento")
        if price:
            return price
        price = self._extract_price_block(soup, "Precio Caja")
        if price:
            return price
        return self._extract_price_block(soup, "Precio Por Caja")

    def extract_thousand(self, soup):
        return self._extract_price_block(soup, "Precio Millar")