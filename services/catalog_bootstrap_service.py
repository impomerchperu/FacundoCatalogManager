import json
from collections.abc import Callable
from typing import ClassVar

from controllers.scraping_controller import ScrapingController
from database.db_manager import DBManager


class CatalogBootstrapService:
    """Repara una instalación existente sin volver a scrapear el sitio."""

    HISTORY_RECOVERY_KEY = "history_recovery_applied"
    HISTORY_RECOVERY_VERSION = "530-526-4-v1"

    REFERENCE_CATEGORIES = 24
    REFERENCE_OCCURRENCES = 530
    REFERENCE_PRODUCTS_FOUND = 530
    REFERENCE_PRODUCTS_UNIQUE = 526
    REFERENCE_MULTI_CATEGORY_PRODUCTS = 4
    REFERENCE_DUPLICATE_OCCURRENCES = 4

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

    def __init__(
        self,
        db: DBManager | None = None,
        controller_factory: Callable[[], ScrapingController] = ScrapingController,
    ) -> None:
        self.db = db or DBManager()
        self.controller_factory = controller_factory

    def is_initialized(self) -> bool:
        row = self.db.fetch_all(
            "SELECT value FROM catalog_metadata WHERE key=?",
            ("initialized",),
        )
        return bool(row and row[0]["value"] == "1")

    def product_count(self) -> int:
        row = self.db.fetch_all("SELECT COUNT(*) AS total FROM products")
        return int(row[0]["total"]) if row else 0

    def is_ready(self) -> bool:
        return self.is_initialized() or self.product_count() > 0

    def mark_initialized(self) -> None:
        self.db.execute_query(
            """
            INSERT INTO catalog_metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            ("initialized", "1"),
        )

    def _history_recovery_applied(self) -> bool:
        row = self.db.fetch_one(
            "SELECT value FROM catalog_metadata WHERE key=?",
            (self.HISTORY_RECOVERY_KEY,),
        )
        return bool(row and row["value"] == self.HISTORY_RECOVERY_VERSION)

    def _mark_history_recovery_applied(self) -> None:
        self.db.execute_query(
            """
            INSERT INTO catalog_metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (self.HISTORY_RECOVERY_KEY, self.HISTORY_RECOVERY_VERSION),
        )

    def _find_reference_full_run(self):
        return self.db.fetch_one(
            """
            SELECT id
            FROM scraping_runs
            WHERE mode='full'
              AND status='SUCCESS'
              AND coverage_complete=1
              AND categories_requested=?
              AND expected_category_occurrences=?
              AND actual_category_occurrences=?
              AND products_found=?
              AND products_unique=?
              AND products_multiple_categories=?
              AND duplicate_occurrences=?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                self.REFERENCE_CATEGORIES,
                self.REFERENCE_OCCURRENCES,
                self.REFERENCE_OCCURRENCES,
                self.REFERENCE_PRODUCTS_FOUND,
                self.REFERENCE_PRODUCTS_UNIQUE,
                self.REFERENCE_MULTI_CATEGORY_PRODUCTS,
                self.REFERENCE_DUPLICATE_OCCURRENCES,
            ),
        )

    def reconcile_reference_run(self) -> int:
        """Restaura el catálogo a la ejecución histórica validada 530/526/4."""
        run = self._find_reference_full_run()
        if run is None:
            return 0

        run_id = int(run["id"])
        occurrence_count = self.db.fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM scraping_product_occurrences
            WHERE run_id=?
            """,
            (run_id,),
        )
        if occurrence_count is None or int(occurrence_count["total"] or 0) != self.REFERENCE_OCCURRENCES:
            return 0

        self.db.begin()
        try:
            self.db.execute_query("DELETE FROM product_categories")
            self.db.execute_query(
                """
                DELETE FROM products
                WHERE UPPER(TRIM(code)) NOT IN (
                    SELECT DISTINCT UPPER(TRIM(code))
                    FROM scraping_product_occurrences
                    WHERE run_id=?
                )
                """,
                (run_id,),
            )
            self.db.execute_query(
                """
                UPDATE scraping_product_occurrences
                SET product_id = (
                    SELECT p.id
                    FROM products p
                    WHERE UPPER(TRIM(p.code)) =
                          UPPER(TRIM(scraping_product_occurrences.code))
                    LIMIT 1
                )
                WHERE run_id=?
                """,
                (run_id,),
            )
            missing_product_ids = self.db.fetch_one(
                """
                SELECT COUNT(*) AS total
                FROM scraping_product_occurrences
                WHERE run_id=? AND product_id IS NULL
                """,
                (run_id,),
            )
            if missing_product_ids is None or int(missing_product_ids["total"] or 0) != 0:
                self.db.rollback()
                return 0

            self.db.execute_query(
                """
                INSERT INTO product_categories
                    (product_id, category_id, first_seen_at, last_seen_at)
                SELECT
                    product_id,
                    category_id,
                    MIN(discovered_at),
                    MAX(discovered_at)
                FROM scraping_product_occurrences
                WHERE run_id=?
                GROUP BY product_id, category_id
                ON CONFLICT(product_id, category_id) DO UPDATE SET
                    last_seen_at=excluded.last_seen_at
                """,
                (run_id,),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.product_count()

    def restore_from_change_history(self) -> int:
        """Aplica acumulativamente los cambios históricos cuando no existe run de referencia."""
        changes = self.db.fetch_all(
            """
            SELECT history_id, id, change_type, code, product_name,
                   field_name, new_value
            FROM download_changes
            WHERE code IS NOT NULL AND TRIM(code) <> ''
            ORDER BY history_id ASC, id ASC
            """
        )
        if not changes:
            return self.product_count()

        products: dict[str, dict[str, object]] = {}
        existing_rows = self.db.fetch_all(
            """
            SELECT code, name, category, description, price, price_sample,
                   price_hundred, price_thousand, stock, color_stock,
                   image_url, image_path, image_hash, content_hash
            FROM products
            """
        )
        for row in existing_rows:
            code = self._normalize_code(row["code"])
            if not code:
                continue
            products[code] = {field: row[field] for field in self.PRODUCT_COLUMNS}

        deleted_codes: set[str] = set()
        for change in changes:
            code = self._normalize_code(change["code"])
            if not code:
                continue

            item_type = str(change["change_type"] or "").strip().upper()
            if item_type == "DELETED":
                deleted_codes.add(code)
                products.pop(code, None)
                continue
            if item_type in {"MISSING_CODE", "CODE_GENERATED"}:
                continue

            deleted_codes.discard(code)
            product = products.setdefault(code, self._empty_product(code))
            if change["product_name"]:
                product["name"] = str(change["product_name"]).strip()

            field = change["field_name"]
            if field not in self.PRODUCT_FIELDS:
                continue
            product[field] = self._convert_field(field, change["new_value"])

        for code in deleted_codes:
            products.pop(code, None)

        products = {
            code: product
            for code, product in products.items()
            if str(product.get("name", "")).strip()
        }

        self.db.begin()
        try:
            for code in deleted_codes:
                self.db.execute_query(
                    "DELETE FROM products WHERE UPPER(TRIM(code)) = ?",
                    (code,),
                )

            for product in products.values():
                placeholders = ", ".join("?" for _ in self.PRODUCT_COLUMNS)
                update_fields = ", ".join(
                    f"{field}=excluded.{field}"
                    for field in self.PRODUCT_COLUMNS[1:]
                )
                self.db.execute_query(
                    f"""
                    INSERT INTO products ({', '.join(self.PRODUCT_COLUMNS)})
                    VALUES ({placeholders})
                    ON CONFLICT(code) DO UPDATE SET {update_fields}
                    """,
                    tuple(product[field] for field in self.PRODUCT_COLUMNS),
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        restored = self.product_count()
        if restored:
            self.mark_initialized()
            self._mark_history_recovery_applied()
            self.db.commit()
        return restored

    def bootstrap(self) -> int:
        """Ejecuta la reparación de referencia una sola vez."""
        if self._history_recovery_applied():
            return self.product_count()

        restored = self.reconcile_reference_run()
        if restored == self.REFERENCE_PRODUCTS_UNIQUE:
            self._mark_history_recovery_applied()
            self.mark_initialized()
            self.db.commit()
            return restored

        restored = self.restore_from_change_history()
        if restored or self.product_count() > 0:
            self._mark_history_recovery_applied()
            self.mark_initialized()
            self.db.commit()
        return restored

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
