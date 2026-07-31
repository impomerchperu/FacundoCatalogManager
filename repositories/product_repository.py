import sqlite3

from database.db_manager import DBManager
from models.product import Product


class ProductRepository:
    """Repositorio encargado del acceso a datos de los productos."""

    def __init__(self, db: DBManager | None = None):
        self.db = db or DBManager()

    def create(self, product: Product) -> Product:
        """Inserta un nuevo producto."""

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
            product.image_path,
        )

        cursor = self.db.execute_query(query, params)

        product.product_id = cursor.lastrowid

        return product

    def update(self, product: Product) -> Product:
        """Actualiza un producto existente."""

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

        return product

    def delete(self, product_id: int) -> None:
        """Elimina un producto por su ID."""

        query = """
        DELETE FROM products
        WHERE id = ?
        """

        self.db.execute_query(query, (product_id,))

    def get_all(self) -> list[Product]:
        """Obtiene todos los productos."""

        query = """
        SELECT *
        FROM products
        ORDER BY id DESC
        """

        rows: list[sqlite3.Row] = self.db.fetch_all(query)

        return [self._row_to_product(row) for row in rows]

    def search(self, text: str) -> list[Product]:
        """Busca productos por código, nombre o categoría."""

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

        rows: list[sqlite3.Row] = self.db.fetch_all(
            query,
            (value, value, value),
        )

        return [self._row_to_product(row) for row in rows]

    def get_by_id(self, product_id: int) -> Product | None:
        """Obtiene un producto por su ID."""

        query = """
        SELECT *
        FROM products
        WHERE id = ?
        """

        rows: list[sqlite3.Row] = self.db.fetch_all(
            query,
            (product_id,),
        )

        if not rows:
            return None

        return self._row_to_product(rows[0])

    def _row_to_product(
        self,
        row: sqlite3.Row | None,
    ) -> Product | None:
        """Convierte un sqlite3.Row en un objeto Product."""

        if row is None:
            return None

        return Product(
            product_id=row["id"],
            code=row["code"],
            name=row["name"],
            category=row["category"],
            description=row["description"],
            price=row["price"],
            stock=row["stock"],
            image_path=row["image_path"],
        )
