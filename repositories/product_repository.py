import json
import re
import sqlite3

from database.db_manager import DBManager
from models.product import Product


class ProductRepository:
    _INVALID_COLOR_MARKERS = (
        "var acss",
        "sourceurl=",
        "sourceurl:",
        "javascript",
        "color_mode",
        "enable_client_color_preference",
    )

    def __init__(self, db: DBManager | None = None) -> None:
        self.db = db or DBManager()

    def create(self, product: Product) -> Product:
        query = """
        INSERT INTO products
        (
            code, name, category, description, price,
            price_sample, price_hundred, price_thousand, stock,
            color_stock, image_url, image_path,
            image_hash, content_hash
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        cursor = self.db.execute_query(
            query,
            (
                product.code,
                product.name,
                product.category,
                product.description,
                product.price,
                product.price_sample,
                product.price_hundred,
                product.price_thousand,
                product.stock,
                json.dumps(
                    self._clean_color_stock(product.color_stock),
                    ensure_ascii=False,
                ),
                product.image_url,
                product.image_path,
                product.image_hash,
                product.content_hash,
            ),
        )
        product.product_id = cursor.lastrowid
        return product

    def update(self, product: Product) -> Product:
        query = """
        UPDATE products SET
            code=?, name=?, category=?, description=?, price=?,
            price_sample=?, price_hundred=?, price_thousand=?, stock=?,
            color_stock=?, image_url=?, image_path=?,
            image_hash=?, content_hash=?
        WHERE id=?
        """
        self.db.execute_query(
            query,
            (
                product.code,
                product.name,
                product.category,
                product.description,
                product.price,
                product.price_sample,
                product.price_hundred,
                product.price_thousand,
                product.stock,
                json.dumps(
                    self._clean_color_stock(product.color_stock),
                    ensure_ascii=False,
                ),
                product.image_url,
                product.image_path,
                product.image_hash,
                product.content_hash,
                product.product_id,
            ),
        )
        return product

    def save(self, product: Product) -> Product:
        existing = self.get_by_code(product.code)
        if existing is not None:
            product.product_id = existing.product_id
            return self.update(product)
        return self.create(product)

    def get_by_code(self, code: str) -> Product | None:
        rows = self.db.fetch_all(
            "SELECT * FROM products WHERE code = ? COLLATE NOCASE",
            (code,),
        )
        return self._row_to_product(rows[0]) if rows else None

    def get(self, code: str) -> Product | None:
        return self.get_by_code(code)

    def get_by_id(self, product_id: int) -> Product | None:
        rows = self.db.fetch_all(
            "SELECT * FROM products WHERE id=?",
            (product_id,),
        )
        return self._row_to_product(rows[0]) if rows else None

    def get_all(self) -> list[Product]:
        rows = self.db.fetch_all(
            "SELECT * FROM products ORDER BY id DESC",
        )
        return [self._row_to_product(row) for row in rows]

    def search(self, text: str) -> list[Product]:
        value = f"%{text}%"
        rows = self.db.fetch_all(
            """
            SELECT * FROM products
            WHERE code LIKE ? OR name LIKE ? OR category LIKE ?
            ORDER BY id DESC
            """,
            (value, value, value),
        )
        return [self._row_to_product(row) for row in rows]

    def delete(self, product_id: int) -> None:
        self.db.execute_query(
            "DELETE FROM products WHERE id=?",
            (product_id,),
        )

    def delete_by_code(self, code: str) -> None:
        """Elimina un producto identificado por su código, ignorando mayúsculas."""
        self.db.execute_query(
            "DELETE FROM products WHERE code = ? COLLATE NOCASE",
            (code,),
        )

    @classmethod
    def _is_valid_color_name(cls, value: str) -> bool:
        if not value or len(value) > 80:
            return False
        folded = value.casefold()
        if folded in {
            "color",
            "colour",
            "colores",
            "seleccionar color",
            "choose an option",
        }:
            return False
        if any(marker in folded for marker in cls._INVALID_COLOR_MARKERS):
            return False
        if any(token in value for token in ("{", "}", ";", "//", "=>")):
            return False
        return not re.fullmatch(r"[\d\s.,:+-]+", value)

    @classmethod
    def _json_dict(cls, value) -> dict[str, int]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        result: dict[str, int] = {}
        for key, stock in parsed.items():
            try:
                normalized = re.sub(r"\s+", " ", str(key)).strip(" .:-|")
                if not cls._is_valid_color_name(normalized):
                    continue
                result[normalized] = max(int(stock), 0)
            except (TypeError, ValueError):
                continue
        return result

    @classmethod
    def _clean_color_stock(
        cls,
        color_stock: dict[str, int] | None,
    ) -> dict[str, int]:
        if not color_stock:
            return {}
        return cls._json_dict(json.dumps(color_stock, ensure_ascii=False))

    def _row_to_product(self, row: sqlite3.Row) -> Product:
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
            color_stock=self._json_dict(row["color_stock"]),
            image_url=row["image_url"],
            image_path=row["image_path"],
            image_hash=row["image_hash"],
            content_hash=row["content_hash"],
        )
