from models.scraping.category import Category
from scrapers.selectors import category_selectors


class CategoryExtractor:
    """
    Extrae categorías WooCommerce desde HTML.
    """

    def extract(self, soup):

        categories = []

        seen = set()

        links = soup.select(category_selectors.CATEGORY_LINK)

        for link in links:
            url = link.get("href", "")

            if not url:
                continue

            # Ignorar categorías especiales
            if "nuevos-productos" in url:
                continue

            # Evitar duplicados
            if url in seen:
                continue

            name = link.get_text(" ", strip=True)

            # Algunos enlaces vienen sin texto
            if not name or "Ver Categoría" in name:
                name = url.rstrip("/").split("/")[-1].replace("-", " ").title()

            categories.append(Category(name=name, url=url))

            seen.add(url)

        return categories
