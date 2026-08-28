import re

from models.scraping.category import Category
from scrapers.selectors import category_selectors

_COUNT_PATTERN = re.compile(r"Producto\(s\)\s*(\d+)", re.IGNORECASE)
_HEADING_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6"]
_CATEGORY_SECTION_NAME = "nuestras categorías"


class CategoryExtractor:
    """Extrae categorías WooCommerce y su conteo publicado en la tienda."""

    def extract(self, soup):
        categories_by_url: dict[str, Category] = {}

        for link in self._category_links(soup):
            url = link.get("href", "")
            if not url or "nuevos-productos" in url:
                continue

            name = self._extract_name(link, url)
            expected_count = self._extract_expected_count(link, name)
            category = Category(
                name=name,
                url=url,
                expected_count=expected_count,
            )
            previous = categories_by_url.get(url)
            if previous is None:
                categories_by_url[url] = category
                continue

            if (
                category.expected_count > previous.expected_count
                or self._is_better_name(category.name, previous.name)
            ):
                categories_by_url[url] = Category(
                    name=(
                        category.name
                        if self._is_better_name(category.name, previous.name)
                        else previous.name
                    ),
                    url=url,
                    expected_count=max(
                        previous.expected_count,
                        category.expected_count,
                    ),
                )

        return list(categories_by_url.values())

    @classmethod
    def _category_links(cls, soup):
        """Limita la extracción a la sección pública de categorías del catálogo."""
        heading = next(
            (
                node
                for node in soup.find_all(_HEADING_TAGS)
                if node.get_text(" ", strip=True).casefold()
                == _CATEGORY_SECTION_NAME
            ),
            None,
        )
        if heading is not None:
            for parent in heading.parents:
                links = parent.select(category_selectors.CATEGORY_LINK)
                category_links = [
                    link
                    for link in links
                    if "Ver Categoría" in link.get_text(" ", strip=True)
                ]
                if category_links:
                    return category_links

        return soup.select(category_selectors.CATEGORY_LINK)

    @staticmethod
    def _is_better_name(candidate: str, current: str) -> bool:
        candidate = str(candidate or "").strip()
        current = str(current or "").strip()
        if not candidate or candidate.casefold() == "ver categoría":
            return False
        return not current or current.casefold() == "ver categoría"

    @staticmethod
    def _extract_name(link, url: str) -> str:
        name = link.get_text(" ", strip=True)
        if name and "Ver Categoría" not in name:
            return name

        current = link
        while current is not None:
            current = getattr(current, "parent", None)
            if current is None:
                break
            heading = current.find(_HEADING_TAGS)
            if heading is not None:
                heading_name = heading.get_text(" ", strip=True)
                if heading_name and "Ver Categoría" not in heading_name:
                    return heading_name

        return url.rstrip("/").split("/")[-1].replace("-", " ").title()

    @staticmethod
    def _extract_expected_count(link, category_name: str) -> int:
        """Busca el conteo del bloque individual de la categoría."""
        heading = link.find_previous(_HEADING_TAGS)
        if heading is not None:
            heading_name = heading.get_text(" ", strip=True)
            if heading_name.casefold() == category_name.casefold():
                count_node = heading.find_previous(
                    string=lambda value: bool(
                        value and _COUNT_PATTERN.search(str(value))
                    )
                )
                if count_node is not None:
                    match = _COUNT_PATTERN.search(str(count_node))
                    if match:
                        return int(match.group(1))

        fallback_count = 0
        current = link
        while current is not None:
            current = getattr(current, "parent", None)
            if current is None:
                break

            text = current.get_text(" ", strip=True)
            matches = [int(value) for value in _COUNT_PATTERN.findall(text)]
            if len(matches) != 1:
                continue

            candidate = matches[0]
            if fallback_count == 0:
                fallback_count = candidate

            headings = current.find_all(_HEADING_TAGS)
            heading_texts = {
                heading.get_text(" ", strip=True).casefold()
                for heading in headings
            }
            if category_name.casefold() in heading_texts:
                return candidate

        return fallback_count
