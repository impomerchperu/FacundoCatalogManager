from datetime import datetime, timedelta, timezone
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
                )
                VALUES (?, ?, ?, 0, NULL, ?, ?)
                """,
                (
                    created_at,
                    source,
                    status,
                    len(unique_products),
                    message,
                ),
            )

            load_id = self._require_load_id(cursor.lastrowid)

            for product in unique_products:
                connection.execute(
                    """
                    INSERT INTO catalog_load_products (
                        load_id, code, name, category, description,
                        price, price_sample, price_hundred,
                        price_thousand, stock, image_url, image_path,
                        image_hash, content_hash
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
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
                        product.image_url,
                        product.image_path,
                        product.image_hash,
                        product.content_hash,
                    ),
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
        products = self.db.fetch_all(
            """
            SELECT code, name, category, description, price,
                   price_sample, price_hundred, price_thousand,
                   stock, image_url, image_path, image_hash,
                   content_hash
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
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
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
                        price_thousand, stock, image_url, image_path,
                        image_hash, content_hash
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        """
        Aplica una carga y conserva permanentemente el estado de cada carga
        que haya sido aplicada anteriormente.

        ``applied`` representa si una carga fue aplicada alguna vez, no cuál
        es la carga actualmente visible en el catálogo. Por eso una nueva
        aplicación no revierte el estado ni la fecha ``applied_at`` de las
        cargas anteriores.
        """
        load = self.get_by_id(load_id)

        if load is None:
            return False
        if bool(load["applied"]) or load["applied_at"] is not None:
            return True

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

    def cleanup_expired_history(self, retention_days: int = 7) -> int:
        """
        Elimina historiales y cargas no aplicadas anteriores al período indicado.

        Las cargas aplicadas se conservan para no perder el registro histórico
        ni la fecha de aplicación de cada versión que haya sido utilizada.
        """
        if retention_days < 1:
            raise ValueError("retention_days debe ser mayor que cero.")

        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=retention_days)
        ).isoformat()
        connection = self.db.connection

        try:
            connection.execute("BEGIN")

            connection.execute(
                """
                DELETE FROM scraping_history
                WHERE started_at < ?
                  AND (
                      load_id IS NULL
                      OR NOT EXISTS (
                          SELECT 1
                          FROM catalog_loads
                          WHERE catalog_loads.id = scraping_history.load_id
                            AND (
                                catalog_loads.applied = 1
                                OR catalog_loads.applied_at IS NOT NULL
                            )
                      )
                  )
                """,
                (cutoff,),
            )

            cursor = connection.execute(
                """
                DELETE FROM catalog_loads
                WHERE created_at < ?
                  AND applied = 0
                  AND applied_at IS NULL
                """,
                (cutoff,),
            )
            deleted = cursor.rowcount
            connection.commit()
        except Exception:
            connection.rollback()
            raise

        return max(int(deleted), 0)

    def get_load_changes(self, load_id: int) -> list[dict]:
        """Compara una carga con la carga exitosa inmediatamente anterior."""
        current_rows = self.db.fetch_all(
            """
            SELECT code, name, category, description, price,
                   price_sample, price_hundred, price_thousand,
                   stock, image_url, image_path, image_hash,
                   content_hash
            FROM catalog_load_products
            WHERE load_id = ?
            ORDER BY code
            """,
            (load_id,),
        )
        current = {row["code"]: row for row in current_rows}

        previous_load = self.db.fetch_one(
            """
            SELECT id
            FROM catalog_loads
            WHERE id < ? AND status = 'SUCCESS'
            ORDER BY id DESC
            LIMIT 1
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
            """
            SELECT code, name, category, description, price,
                   price_sample, price_hundred, price_thousand,
                   stock, image_url, image_path, image_hash,
                   content_hash
            FROM catalog_load_products
            WHERE load_id = ?
            """,
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
                    },
                )
                continue

            field_changes = []
            for field in self.PRODUCT_FIELDS:
                old_value = old[field]
                new_value = row[field]
                if old_value != new_value:
                    field_changes.append(
                        {
                            "field": field,
                            "label": self.FIELD_LABELS[field],
                            "old": old_value,
                            "new": new_value,
                        },
                    )

            if field_changes:
                changes.append(
                    {
                        "type": "UPDATED",
                        "code": code,
                        "name": row["name"],
                        "fields": [item["label"] for item in field_changes],
                        "changes": field_changes,
                    },
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
                   price_sample, price_hundred, price_thousand,
                   stock, image_url, image_path, image_hash,
                   content_hash
            FROM catalog_load_products
            WHERE load_id = ?
            ORDER BY id
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
                    price_sample, price_hundred, price_thousand,
                    stock, image_url, image_path, image_hash,
                    content_hash
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ORDER BY applied_at DESC, id DESC
            LIMIT 1
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

    @staticmethod
    def _deduplicate_products(products):
        """Elimina duplicados por código antes de persistir una carga."""
        unique = {}

        for product in products:
            code = str(getattr(product, "code", "")).strip()
            if not code:
                continue
            unique.setdefault(code, product)

        return list(unique.values())

    @staticmethod
    def _require_load_id(load_id: int | None) -> int:
        if load_id is None:
            raise RuntimeError(
                "No fue posible obtener el ID de la carga creada.",
            )
        return int(load_id)
