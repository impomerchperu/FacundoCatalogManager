import re

from models.scraping.category import Category
from scrapers.selectors import category_selectors


_COUNT_PATTERN = re.compile(r"Producto\(s\)\s*(\d+)", re.IGNORECASE)


class CategoryExtractor:
    """Extrae categorías WooCommerce y su conteo publicado en la tienda."""

    def extract(self, soup):
        categories = []
        seen = set()

        for link in soup.select(category_selectors.CATEGORY_LINK):
            url = link.get("href", "")
            if not url or "nuevos-productos" in url or url in seen:
                continue

            name = self._extract_name(link, url)
            expected_count = self._extract_expected_count(link)
            categories.append(
                Category(name=name, url=url, expected_count=expected_count)
            )
            seen.add(url)

        return categories

    @staticmethod
    def _extract_name(link, url: str) -> str:
        name = link.get_text(" ", strip=True)
        if name and "Ver Categoría" not in name:
            return name

        container = link.find_parent(["section", "article", "li", "div"])
        if container is not None:
            heading = container.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            if heading is not None:
                heading_name = heading.get_text(" ", strip=True)
                if heading_name:
                    return heading_name

        return url.rstrip("/").split("/")[-1].replace("-", " ").title()

    @staticmethod
    def _extract_expected_count(link) -> int:
        """Busca el ``Producto(s) N`` del bloque visual de la categoría."""
        current = link
        for _ in range(7):
            current = getattr(current, "parent", None)
            if current is None:
                break
            text = current.get_text(" ", strip=True)
            matches = _COUNT_PATTERN.findall(text)
            if len(matches) == 1:
                return int(matches[0])
        return 0
