import re

from bs4 import BeautifulSoup


class ProductBlockExtractor:
    """Extrae bloques de productos desde una página categoría."""

    SELECTOR = ".jsfb-filterable"
    CODE_PATTERN = re.compile(r"\b[A-Z0-9]{1,16}(?:-[A-Z0-9]+)+\b", re.IGNORECASE)

    def extract(self, soup: BeautifulSoup):
        if soup is None:
            return []

        blocks = list(soup.select(self.SELECTOR))
        known_codes = self._codes_from_blocks(blocks)

        # Algunas categorías contienen un bloque visual de 25 productos y,
        # más abajo, una tabla HTML con el catálogo completo (hasta 50+).
        # La tabla es la fuente adicional de cobertura; no reemplaza los
        # bloques existentes y se deduplica por código.
        for row in soup.select("table tr"):
            block = self._table_row_to_block(row)
            if block is None:
                continue
            code = self._extract_code(block)
            if not code or code in known_codes:
                continue
            known_codes.add(code)
            blocks.append(block)

        return blocks

    @classmethod
    def _codes_from_blocks(cls, blocks):
        return {
            code
            for block in blocks
            if (code := cls._extract_code(block))
        }

    @classmethod
    def _extract_code(cls, block) -> str:
        for selector in ("span.sku", "p.brxe-heading", "[sku]", "[data-sku]", ".sku"):
            element = block.select_one(selector)
            if element is None:
                continue
            value = element.get("sku") or element.get("data-sku") or element.get_text(" ", strip=True)
            match = cls.CODE_PATTERN.search(str(value))
            if match:
                return match.group(0).upper()
        match = cls.CODE_PATTERN.search(block.get_text(" ", strip=True))
        return match.group(0).upper() if match else ""

    @classmethod
    def _table_row_to_block(cls, row):
        cells = row.select("td")
        if len(cells) < 3:
            return None

        row_text = row.get_text(" ", strip=True)
        code_match = cls.CODE_PATTERN.search(row_text)
        if not code_match:
            return None

        product_link = row.select_one('a[href*="/producto/"]')
        href = product_link.get("href") if product_link else ""
        if not isinstance(href, str) or not href.strip():
            return None

        name = ""
        if product_link:
            name = product_link.get_text(" ", strip=True)
        if not name and len(cells) >= 3:
            name = cells[2].get_text(" ", strip=True)
        if not name:
            return None

        wrapper = BeautifulSoup("<div class='jsfb-filterable'></div>", "html.parser").div
        if wrapper is None:
            return None

        sku = wrapper.new_tag("span", attrs={"class": "sku"})
        sku.string = code_match.group(0).upper()
        wrapper.append(sku)

        title = wrapper.new_tag("h3", attrs={"class": "brxe-heading"})
        title.string = name
        wrapper.append(title)

        link = wrapper.new_tag("a", href=href)
        link.string = name
        wrapper.append(link)

        for child in row.contents:
            wrapper.append(child.__copy__() if hasattr(child, "__copy__") else str(child))

        return wrapper
