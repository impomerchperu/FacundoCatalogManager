from urllib.parse import urljoin

from models.scraping.scraped_product import ScrapedProduct
from scrapers.extractors.price_extractor import PriceExtractor
from scrapers.selectors import product_selectors


class ProductExtractor:
    """
    Extrae información de productos desde:

    - Tarjetas de categoría Bricks Builder
    - Página individual WooCommerce

    Fuente:
    Importaciones Facundo
    """

    SOURCE = "importacionesfacundo"

    BASE_URL = "https://stock.importacionesfacundo.com"

    def __init__(self):

        self.price_extractor = PriceExtractor()

    def extract(self, soup, url="", category=""):

        return ScrapedProduct(
            source=self.SOURCE,
            url=url,
            code=self.extract_code(soup),
            name=self.extract_name(soup),
            category=category,
            description=self.extract_description(soup),
            stock=self.extract_stock(soup),
            price=self.extract_price(soup),
            price_sample=self.price_extractor.extract_sample(soup),
            price_hundred=self.price_extractor.extract_hundred(soup),
            price_thousand=self.price_extractor.extract_thousand(soup),
            image_url=self.extract_image(soup),
        )

    # =====================================================
    # CÓDIGO
    # =====================================================

    def extract_code(self, soup):

        selectors = [
            "p.brxe-heading",
            "span.sku",
            "[sku]",
        ]

        for selector in selectors:
            element = soup.select_one(selector)

            if element:
                text = element.get_text(" ", strip=True)

                if "FB-" in text:
                    return text.split()[0]

        return ""

    # =====================================================
    # NOMBRE
    # =====================================================

    def extract_name(self, soup):

        selectors = [
            "h2.brxe-heading",
            "h1",
            product_selectors.PRODUCT_NAME,
        ]

        for selector in selectors:
            element = soup.select_one(selector)

            if element:
                return element.get_text(" ", strip=True)

        return ""

    # =====================================================
    # DESCRIPCIÓN
    # =====================================================

    def extract_description(self, soup):

        selectors = [
            ".text-content",
            ".x-tabs_panel-content",
            ".product-description",
            product_selectors.PRODUCT_DESCRIPTION,
            ".description",
        ]

        for selector in selectors:
            element = soup.select_one(selector)

            if element:
                return element.get_text(" ", strip=True)

        return ""

    # =====================================================
    # STOCK
    # =====================================================

    def extract_stock(self, soup):

        text = soup.get_text(" ", strip=True)

        marker = "Stock Disponible"

        if marker in text:
            after = text.split(marker, 1)[1]

            numbers = "".join(x for x in after if x.isdigit())

            if numbers:
                return int(numbers)

        return 0

    # =====================================================
    # PRECIO
    # =====================================================

    def extract_price(self, soup):

        selectors = [
            ".product-price",
            ".price",
            "span.price",
            ".woocommerce-Price-amount",
            "[class*='price']",
        ]

        for selector in selectors:
            element = soup.select_one(selector)

            if element:
                text = element.get_text(" ", strip=True)

                clean = text.replace("S/", "").replace("$", "").replace(",", "").strip()

                try:
                    return float(clean)

                except ValueError:
                    continue

        return 0.0

    # =====================================================
    # IMAGEN
    # =====================================================

    def extract_image(self, soup):

        code = self.extract_code(soup)

        candidates = []

        for img in soup.find_all("img"):
            url = (
                img.get("data-src") or img.get("data-lazy-src") or img.get("src") or ""
            )

            if not url:
                continue

            if url.startswith("data:image"):
                continue

            if "Logo" in url:
                continue

            if "Proximo" in url:
                continue

            url = self._normalize_image_url(url)

            candidates.append(url)

        if not candidates:
            return ""

        if code:
            for url in candidates:
                if code.lower() in url.lower():
                    return url

        for url in candidates:
            if "/uploads/" in url:
                return url

        return candidates[0]

    # =====================================================
    # NORMALIZAR URL IMAGEN
    # =====================================================

    def _normalize_image_url(self, url):

        if not url:
            return ""

        if url.startswith("//"):
            return "https:" + url

        if url.startswith("/"):
            return urljoin(self.BASE_URL, url)

        return url
