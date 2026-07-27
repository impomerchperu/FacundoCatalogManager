from database.db_manager import DBManager
from models.product import Product


class ProductService:

    def __init__(self):
        self.db = DBManager()

    def create_product(self, product):
        query = """
        INSERT INTO products
        (code, name, category, description, price, stock, image_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            product.code,
            product.name,
            product.category,
            product.description,
            product.price,
            product.stock,
            product.image_path,
        )

        self.db.execute_query(query, params)


    def get_products(self):
        query = """
        SELECT *
        FROM products
        ORDER BY id DESC
        """

        return self.db.fetch_all(query)


    def delete_product(self, product_id):
        query = """
        DELETE FROM products
        WHERE id = ?
        """

        self.db.execute_query(query, (product_id,))