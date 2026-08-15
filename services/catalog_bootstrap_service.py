import json
from collections.abc import Callable
from typing import ClassVar

from controllers.scraping_controller import ScrapingController
from database.db_manager import DBManager


class CatalogBootstrapService:
    """Gestiona la recuperación local del catálogo persistente."""

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

    def restore_from_change_history(self) -> int:
        """Reconstruye el catálogo local usando el historial ya descargado.

        Esta operación solo se usa como recuperación cuando ``products`` está
        vacío. No realiza ninguna petición web y por tanto no retrasa ni hace
        depender el arranque de la aplicación del scraper.
        """
        if self.product_count() > 0:
            return 0

        changes = self.db.fetch_all(
            """
            SELECT id, change_type, code, product_name, field_name, new_value
            FROM download_changes
            WHERE code IS NOT NULL AND TRIM(code) <> ''
            ORDER BY id ASC
            """
        )
        if not changes:
            return 0

        products: dict[str, dict[str, object]] = {}
        for change in changes:
            code = str(change["code"]).strip()
            if not code:
                continue

            product = products.setdefault(
                code,
                {
                    "code": code,
                    "name": str(change["product_name"] or "").strip(),
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
                },
            )

            if change["product_name"]:
                product["name"] = str(change["product_name"]).strip()

            field = change["field_name"]
            if field not in self.PRODUCT_FIELDS:
                continue

            product[field] = self._convert_field(field, change["new_value"])

        if not products:
            return 0

        self.db.begin()
        try:
            for product in products.values():
                if not product["name"]:
                    continue
                self.db.execute_query(
                    """
                    INSERT INTO products (
                        code, name, category, description, price,
                        price_sample, price_hundred, price_hundred, price_thousand,
                        stock, color_stock, image_url, image_path, image_hash,
                        content_hash
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    tuple(
                        product[field]
                        for field in (
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
                    ),
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        restored = self.product_count()
        if restored:
            self.mark_initialized()
            self.db.commit()
        return restored

    @staticmethod
    def _convert_field(field: str, value):
        if value is None:
            defaults = {
                "stock": 0,
                "price": 0.0,
                "price_sample": 0.0,
                "price_hundred": 0.0,
                "price_thousand": 0.0,
                "color_stock": "{}",
            }
            return defaults.get(field, "")

        if field in {"price", "price_sample", "price_hundred", "price_thousand"}:
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        if field == "stock":
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return 0

        if field == "color_stock":
            try:
                parsed = json.loads(str(value))
            except (TypeError, ValueError, json.JSONDecodeError):
                return "{}"
            return json.dumps(parsed, ensure_ascii=False)

        return str(value)

    def bootstrap(self):
        """Mantiene compatibilidad con el servicio anterior sin hacer scraping."""
        if self.is_ready():
            return None

        restored = self.restore_from_change_history()
        return restored if restored else None
