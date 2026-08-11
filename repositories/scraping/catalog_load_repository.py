import json
from datetime import datetime, timezone
from typing import ClassVar

from database.db_manager import DBManager


class CatalogLoadRepository:
    """Administra versiones históricas completas del catálogo."""

    PRODUCT_FIELDS = (
        "name",
        "category",
        "description",
        "price",
        "price_sample",
        "price_hundred",
        "price_thousand",
        "stock",
        "colors",
        "color_stock",
        "image_url",
        "image_path",
        "image_hash",
        "content_hash",
    )

    FIELD_LABELS: ClassVar[dict[str, str]] = {
        "name": "Nombre",
        "category": "Categoría",
        "description": "Detalle",
        "price": "Precio",
        "price_sample": "Precio muestra",
        "price_hundred": "Precio ciento",
        "price_thousand": "Precio millar",
        "stock": "Stock",
        "colors": "Colores",
        "color_stock": "Stock por color",
        "image_url": "URL imagen",
        "image_path": "Ruta imagen",
        "image_hash": "Hash imagen",
        "content_hash": "Hash contenido",
    }

    def __init__(self, db: DBManager) -> None:
        self.db = db

    def create_from_products(
        self,
        products,
        source: str = "SCRAPING",
        status: str = "SUCCESS",
        message: str = "",
    ) -> int:
        """Crea una descarga histórica sin modificar el catálogo activo."""
        unique_products = self._deduplicate_products(products)
        created_at = datetime.now(timezone.utc).isoformat()
        connection = self.db.connection

        try:
            connection.execute("BEGIN")
            cursor = connection.execute(
                """
                INSERT INTO catalog_loads (
                    created_at, source, status, applied,
                    applied_at, product_count, message
                ) VALUES (?, ?, ?, 0, NULL, ?, ?)
                """,
                (created_at, source, status, len(unique_products), message),
            )
            load_id = self._require_load_id(cursor.lastrowid)

            for product in unique_products:
                connection.execute(
                    """
                    INSERT INTO catalog_load_products (
                        load_id, code, name, category, description,
                        price, price_sample, price_hundred,
                        price_thousand, stock, colors, color_stock,
                        image_url, image_path, image_hash, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._product_params(load_id, product),
                )

            connection.commit()
        except Exception:
            connection.rollback()
            raise

        return load_id

    def create_from_current_catalog(
        self,
        source: str = "INITIAL",
        status: str = "SUCCESS",
        message: str = "",
        applied: bool = False,
    ) -> int:
        """Crea una versión histórica a partir del catálogo actual."""
        products = self.db.fetch_all(
            """
            SELECT code, name, category, description, price,
                   price_sample, price_hundred, price_thousand, stock,
                   colors, color_stock, image_url, image_path,
                   image_hash, content_hash
            FROM products ORDER BY id
            """,
        )

        created_at = datetime.now(timezone.utc).isoformat()
        applied_at = created_at if applied else None
        connection = self.db.connection

        try:
            connection.execute("BEGIN")
            cursor = connection.execute(
                """
                INSERT INTO catalog_loads (
                    created_at, source, status, applied,
                    applied_at, product_count, message
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    source,
                    status,
                    1 if applied else 0,
                    applied_at,
                    len(products),
                    message,
                ),
            )
            load_id = self._require_load_id(cursor.lastrowid)

            for product in products:
                connection.execute(
                    """
                    INSERT INTO catalog_load_products (
                        load_id, code, name, category, description,
                        price, price_sample, price_hundred,
                        price_thousand, stock, colors, color_stock,
                        image_url, image_path, image_hash, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        load_id,
                        product["code"],
                        product["name"],
                        product["category"],
                        product["description"],
                        product["price"],
                        product["price_sample"],
                        product["price_hundred"],
                        product["price_thousand"],
                        product["stock"],
                        product["colors"] or "[]",
                        product["color_stock"] or "{}",
                        product["image_url"],
                        product["image_path"],
                        product["image_hash"],
                        product["content_hash"],
                    ),
                )

            connection.commit()
        except Exception:
            connection.rollback()
            raise

        return load_id

    def apply(self, load_id: int) -> bool:
        """Aplica manualmente una descarga posterior a la última aplicada."""
        load = self.get_by_id(load_id)
        if load is None or load["status"] != "SUCCESS":
            return False

        latest_applied = self.get_latest_applied()
        if latest_applied is not None:
            latest_id = int(latest_applied["id"])
            if load_id == latest_id:
                return True
            if load_id < latest_id:
                return False

        connection = self.db.connection
        applied_at = datetime.now(timezone.utc).isoformat()

        try:
            connection.execute("BEGIN")
            self._replace_products_in_transaction(load_id)
            connection.execute(
                """
                UPDATE catalog_loads
                SET applied = 1, applied_at = ?
                WHERE id = ?
                """,
                (applied_at, load_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

        return True

    def restore_latest_applied(self) -> int | None:
        """Restaura en products la última carga que fue aplicada."""
        load = self.get_latest_applied()
        if load is None:
            return None
        self._replace_products(int(load["id"]))
        return int(load["id"])

    def cleanup_expired_history(self, retention_days: int | None = None) -> int:
        """
        Limpia historial únicamente cuando se solicita explícitamente.

        Por defecto no elimina nada: el historial de descargas debe
        conservarse para consulta y auditoría.
        """
        if retention_days is None:
            return 0
        if retention_days < 1:
            raise ValueError("retention_days debe ser mayor que cero.")

        from datetime import timedelta

        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=retention_days)
        ).isoformat()
        latest_applied = self.get_latest_applied()
        protected_id = int(latest_applied["id"]) if latest_applied else None
        connection = self.db.connection

        try:
            connection.execute("BEGIN")
            if protected_id is None:
                connection.execute(
                    "DELETE FROM scraping_history WHERE started_at < ?",
                    (cutoff,),
                )
                cursor = connection.execute(
                    "DELETE FROM catalog_loads WHERE created_at < ?",
                    (cutoff,),
                )
            else:
                connection.execute(
                    """
                    DELETE FROM scraping_history
                    WHERE started_at < ?
                      AND (load_id IS NULL OR load_id != ?)
                    """,
                    (cutoff, protected_id),
                )
                cursor = connection.execute(
                    """
                    DELETE FROM catalog_loads
                    WHERE created_at < ? AND id != ?
                    """,
                    (cutoff, protected_id),
                )
            deleted = cursor.rowcount
            connection.commit()
        except Exception:
            connection.rollback()
            raise

        return max(int(deleted), 0)

    def get_catalog_action(self, load_id: int) -> tuple[str, str | None]:
        """Devuelve el estado visible y la fecha de aplicación de una carga."""
        load = self.get_by_id(load_id)
        if load is None:
            return "NO_DISPONIBLE", None
        if load["status"] != "SUCCESS":
            return "NO_APLICABLE", None

        if bool(load["applied"]) or load["applied_at"] is not None:
            return "APLICADO", str(load["applied_at"])

        latest_applied = self.get_latest_applied()
        if latest_applied is not None:
            latest_id = int(latest_applied["id"])
            if load_id < latest_id:
                return "NO_APLICADO", None

        return "APLICAR", None

    def get_load_changes(self, load_id: int) -> list[dict]:
        """
        Devuelve altas y modificaciones de una descarga comparada
        contra la descarga exitosa inmediatamente anterior.
        """
        select_fields = """
            code, name, category, description, price,
            price_sample, price_hundred, price_thousand, stock,
            colors, color_stock, image_url, image_path,
            image_hash, content_hash
        """
        current_rows = self.db.fetch_all(
            f"SELECT {select_fields} FROM catalog_load_products "
            "WHERE load_id = ? ORDER BY code",
            (load_id,),
        )
        current = {row["code"]: row for row in current_rows}

        previous_load = self.db.fetch_one(
            """
            SELECT id FROM catalog_loads
            WHERE id < ? AND status = 'SUCCESS'
            ORDER BY id DESC LIMIT 1
            """,
            (load_id,),
        )

        if previous_load is None:
            return [
                {
                    "type": "NEW",
                    "code": row["code"],
                    "name": row["name"],
                    "fields": [],
                    "changes": [],
                }
                for row in current_rows
            ]

        previous_rows = self.db.fetch_all(
            f"SELECT {select_fields} FROM catalog_load_products WHERE load_id = ?",
            (int(previous_load["id"]),),
        )
        previous = {row["code"]: row for row in previous_rows}
        changes: list[dict] = []

        for code, row in current.items():
            old = previous.get(code)
            if old is None:
                changes.append(
                    {
                        "type": "NEW",
                        "code": code,
                        "name": row["name"],
                        "fields": [],
                        "changes": [],
                    }
                )
                continue

            field_changes = []
            for field in self.PRODUCT_FIELDS:
                old_value = self._decode_value(field, old[field])
                new_value = self._decode_value(field, row[field])
                if old_value != new_value:
                    field_changes.append(
                        {
                            "field": field,
                            "label": self.FIELD_LABELS[field],
                            "old": old_value,
                            "new": new_value,
                        }
                    )

            if field_changes:
                changes.append(
                    {
                        "type": "UPDATED",
                        "code": code,
                        "name": row["name"],
                        "fields": [item["label"] for item in field_changes],
                        "changes": field_changes,
                    }
                )

        return changes

    def _replace_products(self, load_id: int) -> None:
        connection = self.db.connection
        try:
            connection.execute("BEGIN")
            self._replace_products_in_transaction(load_id)
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def _replace_products_in_transaction(self, load_id: int) -> None:
        products = self.db.fetch_all(
            """
            SELECT code, name, category, description, price,
                   price_sample, price_hundred, price_thousand, stock,
                   colors, color_stock, image_url, image_path,
                   image_hash, content_hash
            FROM catalog_load_products
            WHERE load_id = ? ORDER BY id
            """,
            (load_id,),
        )
        connection = self.db.connection
        connection.execute("DELETE FROM products")

        for product in products:
            connection.execute(
                """
                INSERT INTO products (
                    code, name, category, description, price,
                    price_sample, price_hundred, price_thousand, stock,
                    colors, color_stock, image_url, image_path,
                    image_hash, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product["code"],
                    product["name"],
                    product["category"],
                    product["description"],
                    product["price"],
                    product["price_sample"],
                    product["price_hundred"],
                    product["price_thousand"],
                    product["stock"],
                    product["colors"] or "[]",
                    product["color_stock"] or "{}",
                    product["image_url"],
                    product["image_path"],
                    product["image_hash"],
                    product["content_hash"],
                ),
            )

    def get_by_id(self, load_id: int):
        return self.db.fetch_one(
            "SELECT * FROM catalog_loads WHERE id = ?",
            (load_id,),
        )

    def get_latest(self, limit: int = 10):
        return self.db.fetch_all(
            "SELECT * FROM catalog_loads ORDER BY id DESC LIMIT ?",
            (limit,),
        )

    def get_latest_applied(self):
        return self.db.fetch_one(
            """
            SELECT * FROM catalog_loads
            WHERE applied = 1 OR applied_at IS NOT NULL
            ORDER BY applied_at DESC, id DESC LIMIT 1
            """,
        )

    def get_latest_successful(self):
        return self.db.fetch_one(
            """
            SELECT * FROM catalog_loads
            WHERE status = 'SUCCESS'
            ORDER BY id DESC LIMIT 1
            """,
        )

    def has_applied_load(self) -> bool:
        return self.get_latest_applied() is not None

    def ensure_initial_applied_load(self) -> int | None:
        applied = self.get_latest_applied()
        if applied is not None:
            return int(applied["id"])

        products = self.db.fetch_all("SELECT id FROM products LIMIT 1")
        if not products:
            return None

        return self.create_from_current_catalog(
            source="INITIAL",
            status="SUCCESS",
            message="Carga inicial creada a partir del catálogo existente.",
            applied=True,
        )

    @classmethod
    def _product_params(cls, load_id: int, product) -> tuple:
        colors = cls._normalize_colors(getattr(product, "colors", []))
        color_stock = cls._normalize_color_stock(
            getattr(product, "color_stock", {}),
        )
        return (
            load_id,
            product.code,
            product.name,
            product.category,
            product.description,
            product.price,
            product.price_sample,
            product.price_hundred,
            product.price_thousand,
            product.stock,
            json.dumps(colors, ensure_ascii=False),
            json.dumps(color_stock, ensure_ascii=False),
            product.image_url,
            product.image_path,
            product.image_hash,
            product.content_hash,
        )

    @staticmethod
    def _normalize_colors(colors) -> list[str]:
        return list(
            dict.fromkeys(
                str(color).strip()
                for color in (colors or [])
                if str(color).strip()
            )
        )

    @staticmethod
    def _normalize_color_stock(color_stock) -> dict[str, int]:
        result: dict[str, int] = {}
        for color, stock in (color_stock or {}).items():
            name = str(color).strip()
            if not name:
                continue
            try:
                result[name] = max(int(stock), 0)
            except (TypeError, ValueError):
                result[name] = 0
        return result

    @staticmethod
    def _decode_value(field: str, value):
        if field == "colors":
            try:
                return json.loads(value or "[]")
            except (TypeError, json.JSONDecodeError):
                return []
        if field == "color_stock":
            try:
                return json.loads(value or "{}")
            except (TypeError, json.JSONDecodeError):
                return {}
        return value

    @staticmethod
    def _deduplicate_products(products):
        """Consolida por código sin perder categorías ni colores."""
        unique = {}

        for product in products:
            code = str(getattr(product, "code", "")).strip()
            if not code:
                continue

            existing = unique.get(code)
            if existing is None:
                unique[code] = product
                continue

            categories = [
                item.strip()
                for item in str(getattr(existing, "category", "")).split(",")
                if item.strip()
            ]
            incoming_categories = [
                item.strip()
                for item in str(getattr(product, "category", "")).split(",")
                if item.strip()
            ]
            existing.category = ", ".join(
                dict.fromkeys(categories + incoming_categories),
            )

            merged_colors = CatalogLoadRepository._normalize_colors(
                list(getattr(existing, "colors", []))
                + list(getattr(product, "colors", [])),
            )
            existing.colors = merged_colors

            merged_stock = CatalogLoadRepository._normalize_color_stock(
                getattr(existing, "color_stock", {}),
            )
            for color, stock in CatalogLoadRepository._normalize_color_stock(
                getattr(product, "color_stock", {}),
            ).items():
                merged_stock[color] = max(merged_stock.get(color, 0), stock)
            existing.color_stock = merged_stock

            if not getattr(existing, "image_url", "") and getattr(
                product, "image_url", "",
            ):
                existing.image_url = product.image_url

        return list(unique.values())

    @staticmethod
    def _require_load_id(load_id: int | None) -> int:
        if load_id is None:
            raise RuntimeError("No fue posible obtener el ID de la carga creada.")
        return int(load_id)
