import json
from typing import ClassVar

from database.db_manager import DBManager


class CatalogHistoryRecoveryService:
    """Reconstruye un catálogo vacío a partir de cambios históricos exitosos."""

    PRODUCT_FIELDS: ClassVar[set[str]] = {
        "name",
        "category",
        "description",
        "price",
        "price_sample",
        "price_hundred",
        "price_thousand",
        "stock",
        "color_stock",
        "image_url",
        "image_path",
        "image_hash",
        "content_hash",
    }
    PRODUCT_COLUMNS: ClassVar[tuple[str, ...]] = (
        "code",
        "name",
        "category",
        "description",
        "price",
        "price_sample",
        "price_hundred",
        "price_thousand",
        "stock",
        "color_stock",
        "image_url",
        "image_path",
        "image_hash",
        "content_hash",
    )

    def __init__(self, db: DBManager) -> None:
        self.db = db

    def restore(self, *, manage_transaction: bool = True) -> int:
        """Reconstruye un catálogo vacío usando únicamente cambios de historiales exitosos."""
        if self._product_count() > 0:
            return 0

        changes = self._successful_changes()
        if not changes:
            return 0

        products, deleted_codes = self._build_product_state(changes)
        if manage_transaction:
            self.db.begin()
        try:
            self._apply_product_state(products, deleted_codes)
            if manage_transaction:
                self.db.commit()
        except Exception:
            if manage_transaction:
                self.db.rollback()
            raise

        return self._product_count()

    def _successful_changes(self):
        return self.db.fetch_all(
            """
            SELECT c.history_id, c.id, c.change_type, c.code, c.product_name,
                   c.field_name, c.new_value
            FROM download_changes c
            INNER JOIN scraping_history h ON h.id = c.history_id
            WHERE h.status='SUCCESS'
              AND c.code IS NOT NULL
              AND TRIM(c.code) <> ''
            ORDER BY c.history_id ASC, c.id ASC
            """
        )

    def _build_product_state(self, changes):
        products: dict[str, dict[str, object]] = {}
        deleted_codes: set[str] = set()
        for change in changes:
            code = self._normalize_code(change["code"])
            if not code:
                continue
            item_type = str(change["change_type"] or "").strip().upper()
            if item_type == "DELETED":
                self._mark_deleted(code, products, deleted_codes)
                continue
            if item_type in {"MISSING_CODE", "CODE_GENERATED"}:
                continue
            self._apply_change(code, change, products, deleted_codes)

        products = {
            code: product
            for code, product in products.items()
            if str(product.get("name", "")).strip()
        }
        return products, deleted_codes

    @staticmethod
    def _mark_deleted(
        code: str,
        products: dict[str, dict[str, object]],
        deleted_codes: set[str],
    ) -> None:
        deleted_codes.add(code)
        products.pop(code, None)

    def _apply_change(
        self,
        code: str,
        change,
        products: dict[str, dict[str, object]],
        deleted_codes: set[str],
    ) -> None:
        deleted_codes.discard(code)
        product = products.setdefault(code, self._empty_product(code))
        if change["product_name"]:
            product["name"] = str(change["product_name"]).strip()
        field = change["field_name"]
        if field in self.PRODUCT_FIELDS:
            product[field] = self._convert_field(field, change["new_value"])

    def _apply_product_state(
        self,
        products: dict[str, dict[str, object]],
        deleted_codes: set[str],
    ) -> None:
        for code in deleted_codes:
            self.db.execute_query(
                "DELETE FROM products WHERE UPPER(TRIM(code))=?", (code,)
            )

        placeholders = ", ".join("?" for _ in self.PRODUCT_COLUMNS)
        updates = ", ".join(
            f"{field}=excluded.{field}" for field in self.PRODUCT_COLUMNS[1:]
        )
        query = (
            f"INSERT INTO products ({', '.join(self.PRODUCT_COLUMNS)}) "
            f"VALUES ({placeholders}) ON CONFLICT(code) DO UPDATE SET {updates}"
        )
        for product in products.values():
            self.db.execute_query(
                query,
                tuple(product[field] for field in self.PRODUCT_COLUMNS),
            )

    def _product_count(self) -> int:
        row = self.db.fetch_all("SELECT COUNT(*) AS total FROM products")
        return int(row[0]["total"]) if row else 0

    @staticmethod
    def _normalize_code(value) -> str:
        return str(value or "").strip().upper()

    @staticmethod
    def _empty_product(code: str) -> dict[str, object]:
        return {
            "code": code,
            "name": "",
            "category": "",
            "description": "",
            "price": 0.0,
            "price_sample": 0.0,
            "price_hundred": 0.0,
            "price_thousand": 0.0,
            "stock": 0,
            "color_stock": "{}",
            "image_url": "",
            "image_path": "",
            "image_hash": "",
            "content_hash": "",
        }

    @staticmethod
    def _convert_field(field: str, value):
        defaults = {
            "stock": 0,
            "price": 0.0,
            "price_sample": 0.0,
            "price_hundred": 0.0,
            "price_thousand": 0.0,
            "color_stock": "{}",
        }
        if value is None:
            value = defaults.get(field, "")

        try:
            if field in {"price", "price_sample", "price_hundred", "price_thousand"}:
                return float(value)
            if field == "stock":
                return int(float(value))
            if field == "color_stock":
                return json.dumps(json.loads(str(value)), ensure_ascii=False)
            return str(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return defaults.get(field, "")
