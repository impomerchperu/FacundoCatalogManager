import sqlite3

from PySide6.QtCore import QObject, Signal, Slot

from config.runtime_paths import DATABASE_PATH

from models.product import Product
from repositories.product_repository import ProductRepository


class CatalogLoadWorker(QObject):
    """Lee el catálogo persistido sin inicializar SQLite desde la interfaz."""

    finished = Signal(object)
    error = Signal(str)

    @staticmethod
    def _database_path() -> str:
        return str(DATABASE_PATH)

    @staticmethod
    def _row_to_product(row: sqlite3.Row) -> Product:
        return Product(
            product_id=row["id"],
            code=row["code"],
            name=row["name"],
            price=row["price"],
            category=row["category"],
            description=row["description"],
            price_sample=row["price_sample"],
            price_hundred=row["price_hundred"],
            price_thousand=row["price_thousand"],
            stock=row["stock"],
            color_stock=ProductRepository._json_dict(row["color_stock"]),
            image_url=row["image_url"],
            image_path=row["image_path"],
            image_hash=row["image_hash"],
            content_hash=row["content_hash"],
        )

    @Slot()
    def run(self) -> None:
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                self._database_path(),
                timeout=5,
            )
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT * FROM products ORDER BY id DESC",
            ).fetchall()
            products = [self._row_to_product(row) for row in rows]
            self.finished.emit(products)
        except Exception as error:  # noqa: BLE001
            self.error.emit(str(error))
        finally:
            if connection is not None:
                connection.close()
