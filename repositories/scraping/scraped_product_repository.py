import json

from models.scraping.scraped_product import ScrapedProduct


class ScrapedProductRepository:
    """Persiste productos obtenidos mediante scraping."""

    def __init__(self, db):
        self.db = db

    def save(self, product: ScrapedProduct):
        existing = self.get_by_url(product.url)
        if not existing and product.code:
            existing = self.get_by_code(product.code)
        if existing:
            self.update(product)
        else:
            self.create(product)

    def create(self, product: ScrapedProduct):
        query = """
        INSERT INTO scraped_products (
            source, url, code, name, category, description,
            stock, price, price_sample, price_hundred, price_thousand,
            colors, color_stock, image_url, image_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.db.execute_query(query, self._params(product))

    def update(self, product: ScrapedProduct):
        query = """
        UPDATE scraped_products
        SET source=?, code=?, name=?, category=?, description=?,
            stock=?, price=?, price_sample=?, price_hundred=?,
            price_thousand=?, colors=?, color_stock=?, image_url=?,
            image_path=?, updated_at=CURRENT_TIMESTAMP
        WHERE url=?
        """
        params = (*self._params(product), product.url)
        self.db.execute_query(query, params)

    def get_by_url(self, url):
        result = self.db.fetch_all(
            "SELECT * FROM scraped_products WHERE url = ?",
            (url,),
        )
        return result[0] if result else None

    def get_by_code(self, code):
        result = self.db.fetch_all(
            "SELECT * FROM scraped_products WHERE code = ?",
            (code,),
        )
        return result[0] if result else None

    def get_all(self):
        return self.db.fetch_all(
            "SELECT * FROM scraped_products ORDER BY id",
        )

    def delete_by_code(self, code):
        self.db.execute_query(
            "DELETE FROM scraped_products WHERE code = ?",
            (code,),
        )

    @staticmethod
    def _params(product: ScrapedProduct) -> tuple:
        return (
            product.source,
            product.url,
            product.code,
            product.name,
            product.category,
            product.description,
            product.stock,
            product.price,
            product.price_sample,
            product.price_hundred,
            product.price_thousand,
            json.dumps(product.colors, ensure_ascii=False),
            json.dumps(product.color_stock, ensure_ascii=False),
            product.image_url,
            product.image_path,
        )
