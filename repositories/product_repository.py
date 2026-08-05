import sqlite3

from database.db_manager import DBManager
from models.product import Product


class ProductRepository:
    """Repositorio encargado del acceso a datos de productos."""

    def __init__(
        self,
        db: DBManager | None = None,
    ):
        self.db = db or DBManager()

    def create(
        self,
        product: Product,
    ) -> Product:
        """Inserta un producto."""

        query = """
        INSERT INTO products
        (
            code,
            name,
            category,
            description,
            price,
            price_sample,
            price_hundred,
            price_thousand,
            stock,
            image_url,
            image_path,
            content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            product.code,
            product.name,
            product.category,
            product.description,
            product.price,
            product.price_sample,
            product.price_hundred,
            product.price_thousand,
            product.stock,
            product.image_url,
            product.image_path,
            product.content_hash,
        )

        cursor = self.db.execute_query(
            query,
            params,
        )

        product.product_id = cursor.lastrowid

        return product

    def update(
        self,
        product: Product,
    ) -> Product:
        """Actualiza un producto."""

        query = """
        UPDATE products
        SET
            code = ?,
            name = ?,
            category = ?,
            description = ?,
            price = ?,
            price_sample = ?,
            price_hundred = ?,
            price_thousand = ?,
            stock = ?,
            image_url = ?,
            image_path = ?,
            content_hash = ?
        WHERE id = ?
        """

        params = (
            product.code,
            product.name,
            product.category,
            product.description,
            product.price,
            product.price_sample,
            product.price_hundred,
            product.price_thousand,
            product.stock,
            product.image_url,
            product.image_path,
            product.content_hash,
            product.id,
        )

        self.db.execute_query(
            query,
            params,
        )

        return product

    def delete(
        self,
        product_id: int,
    ) -> None:
        """Elimina un producto."""

        query = """
        DELETE FROM products
        WHERE id = ?
        """

        self.db.execute_query(
            query,
            (product_id,),
        )

    def get_all(self) -> list[Product]:
        """Obtiene todos los productos."""

        query = """
        SELECT *
        FROM products
        ORDER BY id DESC
        """

        rows: list[sqlite3.Row] = self.db.fetch_all(query)

        return [
            self._row_to_product(row)
            for row in rows
        ]

    def search(
        self,
        text: str,
    ) -> list[Product]:
        """Busca productos."""

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

        rows = self.db.fetch_all(
            query,
            (
                value,
                value,
                value,
            ),
        )

        return [
            self._row_to_product(row)
            for row in rows
        ]

    def get_by_id(
        self,
        product_id: int,
    ) -> Product | None:
        """Busca producto por ID."""

        query = """
        SELECT *
        FROM products
        WHERE id = ?
        """

        rows = self.db.fetch_all(
            query,
            (product_id,),
        )

        if not rows:
            return None

        return self._row_to_product(
            rows[0],
        )

    def get_by_code(
        self,
        code: str,
    ) -> Product | None:
        """Busca producto por código."""

        query = """
        SELECT *
        FROM products
        WHERE code = ?
        """

        rows = self.db.fetch_all(
            query,
            (code,),
        )

        if not rows:
            return None

        return self._row_to_product(
            rows[0],
        )

    def get(
        self,
        code: str,
    ) -> Product | None:
        """
        Obtiene un producto por código.

        Método utilizado por servicios de sincronización.
        """
        return self.get_by_code(
            code,
        )

    def save(
        self,
        product: Product,
    ) -> Product:
        """
        Guarda un producto.

        Crea si no existe.
        Actualiza si ya existe.
        """

        existing = self.get_by_code(
            product.code,
        )

        if existing is None:
            return self.create(
                product,
            )

        product.product_id = existing.product_id

        return self.update(
            product,
        )

    def _row_to_product(
        self,
        row: sqlite3.Row,
    ) -> Product:
        """Convierte SQLite a Product."""

        return Product(
            product_id=row["id"],
            code=row["code"],
            name=row["name"],
            category=row["category"],
            description=row["description"],
            price=row["price"],
            price_sample=row["price_sample"],
            price_hundred=row["price_hundred"],
            price_thousand=row["price_thousand"],
            stock=row["stock"],
            image_url=row["image_url"],
            image_path=row["image_path"],
            content_hash=row["content_hash"],
        )
