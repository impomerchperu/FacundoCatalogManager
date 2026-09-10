import json
from collections.abc import Callable
from typing import ClassVar

from controllers.scraping_controller import ScrapingController
from database.db_manager import DBManager


class CatalogBootstrapService:
    """Repara instalaciones existentes sin sobrescribir un catálogo ya persistido."""

    HISTORY_RECOVERY_KEY = "history_recovery_applied"

    PRODUCT_FIELDS: ClassVar[set[str]] = {
        "name", "category", "description", "price", "price_sample",
        "price_hundred", "price_thousand", "stock", "color_stock",
        "image_url", "image_path", "image_hash", "content_hash",
    }
    PRODUCT_COLUMNS: ClassVar[tuple[str, ...]] = (
        "code", "name", "category", "description", "price", "price_sample",
        "price_hundred", "price_thousand", "stock", "color_stock", "image_url",
        "image_path", "image_hash", "content_hash",
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
            "SELECT value FROM catalog_metadata WHERE key=?", ("initialized",)
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
        return bool(row and row["value"] == "1")

    def _mark_history_recovery_applied(self) -> None:
        self.db.execute_query(
            """
            INSERT INTO catalog_metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (self.HISTORY_RECOVERY_KEY, "1"),
        )

    def _find_latest_successful_full_run(self):
        return self.db.fetch_one(
            """
            SELECT id
            FROM scraping_runs
            WHERE mode='full'
              AND status='SUCCESS'
              AND coverage_complete=1
            ORDER BY id DESC
            LIMIT 1
            """
        )

    def reconcile_latest_successful_run(self) -> int:
        """Reconstruye un catálogo desde la última ejecución FULL válida."""
        run = self._find_latest_successful_full_run()
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
        total_occurrences = int(occurrence_count["total"] or 0) if occurrence_count else 0
        if total_occurrences <= 0:
            return 0

        self.db.begin()
        try:
            self._restore_missing_products_from_legacy_sources(run_id)
            self.db.execute_query(
                """
                UPDATE scraping_product_occurrences
                SET product_id=(
                    SELECT p.id
                    FROM products p
                    WHERE UPPER(TRIM(p.code))=UPPER(TRIM(scraping_product_occurrences.code))
                    LIMIT 1
                )
                WHERE run_id=?
                """,
                (run_id,),
            )
            missing = self.db.fetch_one(
                """
                SELECT COUNT(*) AS total
                FROM scraping_product_occurrences
                WHERE run_id=? AND product_id IS NULL
                """,
                (run_id,),
            )
            if missing is None or int(missing["total"] or 0) != 0:
                self.db.rollback()
                return 0

            self.db.execute_query("DELETE FROM product_categories")
            self.db.execute_query(
                """
                DELETE FROM products
                WHERE id NOT IN (
                    SELECT DISTINCT product_id
                    FROM scraping_product_occurrences
                    WHERE run_id=?
                )
                """,
                (run_id,),
            )
            self.db.execute_query(
                """
                INSERT INTO product_categories
                    (product_id, category_id, first_seen_at, last_seen_at)
                SELECT product_id, category_id, MIN(discovered_at), MAX(discovered_at)
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

    def reconcile_reference_run(self) -> int:
        return self.reconcile_latest_successful_run()

    def _restore_missing_products_from_legacy_sources(self, run_id: int) -> None:
        missing = self.db.fetch_all(
            """
            SELECT DISTINCT UPPER(TRIM(o.code)) AS code
            FROM scraping_product_occurrences o
            LEFT JOIN products p
              ON UPPER(TRIM(p.code))=UPPER(TRIM(o.code))
            WHERE o.run_id=? AND p.id IS NULL
            """,
            (run_id,),
        )
        for row in missing:
            code = self._normalize_code(row["code"])
            if not code:
                continue
            legacy = self.db.fetch_one(
                """
                SELECT code, name, category, description, price, price_sample,
                       price_hundred, price_thousand, stock, color_stock,
                       image_url, image_path, image_hash, content_hash
                FROM scraped_products
                WHERE UPPER(TRIM(code))=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (code,),
            )
            if legacy is None:
                legacy = self.db.fetch_one(
                    """
                    SELECT code, name, category, description, price, price_sample,
                           price_hundred, price_thousand, stock, color_stock,
                           image_url, image_path, image_hash, content_hash
                    FROM sync_records
                    WHERE UPPER(TRIM(code))=?
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (code,),
                )
            if legacy is None:
                continue

            placeholders = ", ".join("?" for _ in self.PRODUCT_COLUMNS)
            self.db.execute_query(
                f"INSERT OR IGNORE INTO products ({', '.join(self.PRODUCT_COLUMNS)}) "
                f"VALUES ({placeholders})",
                tuple(legacy[column] for column in self.PRODUCT_COLUMNS),
            )

    def restore_from_change_history(self) -> int:
        """Reconstruye un catálogo vacío usando únicamente cambios persistidos."""
        if self.product_count() > 0:
            return 0

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
            return 0

        products: dict[str, dict[str, object]] = {}
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
            if field in self.PRODUCT_FIELDS:
                product[field] = self._convert_field(field, change["new_value"])

        products = {
            code: product
            for code, product in products.items()
            if str(product.get("name", "")).strip()
        }

        self.db.begin()
        try:
            for code in deleted_codes:
                self.db.execute_query(
                    "DELETE FROM products WHERE UPPER(TRIM(code))=?", (code,)
                )

            for product in products.values():
                placeholders = ", ".join("?" for _ in self.PRODUCT_COLUMNS)
                updates = ", ".join(
                    f"{field}=excluded.{field}" for field in self.PRODUCT_COLUMNS[1:]
                )
                self.db.execute_query(
                    f"INSERT INTO products ({', '.join(self.PRODUCT_COLUMNS)}) "
                    f"VALUES ({placeholders}) ON CONFLICT(code) DO UPDATE SET {updates}",
                    tuple(product[field] for field in self.PRODUCT_COLUMNS),
                )
            self.mark_initialized()
            self._mark_history_recovery_applied()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return self.product_count()

    def bootstrap(self) -> int:
        """Solo repara una instalación vacía; jamás reemplaza un catálogo existente."""
        if self.product_count() > 0 or self.is_initialized():
            return self.product_count()

        restored = self.reconcile_latest_successful_run()
        if restored <= 0:
            restored = self.restore_from_change_history()
        if restored > 0:
            self.mark_initialized()
            self._mark_history_recovery_applied()
            self.db.commit()
        return restored

    @staticmethod
    def _normalize_code(value) -> str:
        return str(value or "").strip().upper()

    @staticmethod
    def _empty_product(code: str) -> dict[str, object]:
        return {
            "code": code, "name": "", "category": "", "description": "",
            "price": 0.0, "price_sample": 0.0, "price_hundred": 0.0,
            "price_thousand": 0.0, "stock": 0, "color_stock": "{}",
            "image_url": "", "image_path": "", "image_hash": "",
            "content_hash": "",
        }

    @staticmethod
    def _convert_field(field: str, value):
        defaults = {
            "stock": 0, "price": 0.0, "price_sample": 0.0,
            "price_hundred": 0.0, "price_thousand": 0.0, "color_stock": "{}",
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
