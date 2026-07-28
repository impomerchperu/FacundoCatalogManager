from database.db_manager import DBManager


class ProductRepository:
    def __init__(self):
        self.db = DBManager()

    def create(self, product):

        query = """
        INSERT INTO products
        (
            code,
            name,
            category,
            description,
            price,
            stock,
            image_path
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            product.code,
            product.name,
            product.category,
            product.description,
            product.price,
            product.stock,
            product.image_path
        )

        self.db.execute_query(query, params)

    def update(self, product):

        query = """
        UPDATE products
        SET
            code = ?,
            name = ?,
            category = ?,
            description = ?,
            price = ?,
            stock = ?,
            image_path = ?
        WHERE id = ?
        """

        params = (
            product.code,
            product.name,
            product.category,
            product.description,
            product.price,
            product.stock,
            product.image_path,
            product.id,
        )

        self.db.execute_query(query, params)

    def delete(self, product_id):

        query = """
        DELETE FROM products
        WHERE id = ?
        """

        self.db.execute_query(query, (product_id,))

    def get_all(self):

        query = """
        SELECT *
        FROM products
        ORDER BY id DESC
        """

        return self.db.fetch_all(query)

    def search(self, text):

        query = """
        SELECT *
        FROM products
        WHERE
            code LIKE ?
            OR name LIKE ?
            OR category LIKE ?
        ORDER BY id DESC
        """

        value = f"%{text}%"

        params = (value, value, value)

        return self.db.fetch_all(query, params)

    def get_by_id(self, product_id):

        query = """
        SELECT *
        FROM products
        WHERE id = ?
        """

        result = self.db.fetch_all(query, (product_id,))

        if not result:
            return None

        return result[0]
