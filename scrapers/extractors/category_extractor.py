import re

from models.scraping.category import Category
from scrapers.selectors import category_selectors


_COUNT_PATTERN = re.compile(r"Producto\(s\)\s*(\d+)", re.IGNORECASE)


class CategoryExtractor:
    """Extrae categorías WooCommerce y su conteo publicado en la tienda."""

    def extract(self, soup):
        categories = []
        seen = set()

        links = soup.select(category_selectors.CATEGORY_LINK)

        for link in links:
            url = link.get("href", "")
            if not url:
                continue

            if "nuevos-productos" in url:
                continue

            if url in seen:
                continue

            name = link.get_text(" ", strip=True)
            if not name or "Ver Categoría" in name:
                name = (
                    url.rstrip("/")
                    .split("/")[-1]
                    .replace("-", " ")
                    .title()
                )

            expected_count = self._extract_expected_count(link)
            categories.append(
                Category(
                    name=name,
                    url=url,
                    expected_count=expected_count,
                )
            )
            seen.add(url)

        return categories

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
