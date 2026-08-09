from datetime import datetime, timezone

from database.db_manager import DBManager


class CatalogLoadRepository:
    """Administra versiones históricas completas del catálogo."""

    def __init__(self, db: DBManager) -> None:
        self.db = db

    def create_from_products(
        self,
        products,
        source: str = "SCRAPING",
        status: str = "SUCCESS",
        message: str = "",
    ) -> int:
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
            FROM products
            ORDER BY id
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
        Aplica una carga y conserva permanentemente su marca de aplicación.

        Las cargas ya aplicadas no se desmarcan cuando se aplica una carga
        posterior. De esta forma el historial conserva la fecha real en que
        cada carga fue aplicada.
        """

        load = self.get_by_id(load_id)

        if load is None:
            return False

        if bool(load["applied"]):
            return True

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

        applied_at = datetime.now(timezone.utc).isoformat()
        connection = self.db.connection

        try:
            connection.execute("BEGIN")
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

    def get_by_id(self, load_id: int):
        return self.db.fetch_one(
            """
            SELECT * FROM catalog_loads WHERE id = ?
            """,
            (load_id,),
        )

    def get_latest(self, limit: int = 10):
        return self.db.fetch_all(
            """
            SELECT * FROM catalog_loads
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        )

    def get_latest_applied(self):
        return self.db.fetch_one(
            """
            SELECT * FROM catalog_loads
            WHERE applied = 1
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

        products = self.db.fetch_all(
            "SELECT id FROM products LIMIT 1",
        )

        if not products:
            return None

        return self.create_from_current_catalog(
            source="INITIAL",
            status="SUCCESS",
            message=(
                "Carga inicial creada a partir del catálogo existente."
            ),
            applied=True,
        )

    @staticmethod
    def _require_load_id(load_id: int | None) -> int:
        if load_id is None:
            raise RuntimeError(
                "No fue posible obtener el ID de la carga creada.",
            )

        return int(load_id)
