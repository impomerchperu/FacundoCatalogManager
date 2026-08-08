from datetime import datetime, timezone

from database.db_manager import DBManager


class CatalogLoadRepository:
    """
    Repositorio encargado de administrar las cargas
    históricas completas del catálogo.

    Una carga representa una fotografía completa
    de la tabla products en un momento determinado.
    """

    def __init__(
        self,
        db: DBManager,
    ) -> None:
        self.db = db

    def create_from_current_catalog(
        self,
        source: str = "SCRAPING",
        status: str = "SUCCESS",
        message: str = "",
    ) -> int:
        """
        Crea una nueva carga utilizando el catálogo
        actualmente almacenado en products.

        La nueva carga NO queda aplicada automáticamente.
        """

        created_at = datetime.now(
            timezone.utc,
        ).isoformat()

        products = self.db.fetch_all(
            """
            SELECT
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
                image_hash,
                content_hash
            FROM products
            ORDER BY id
            """,
        )

        cursor = self.db.execute_query(
            """
            INSERT INTO catalog_loads (
                created_at,
                source,
                status,
                applied,
                product_count,
                message
            )
            VALUES (?, ?, ?, 0, ?, ?)
            """,
            (
                created_at,
                source,
                status,
                len(products),
                message,
            ),
        )

        load_id = cursor.lastrowid

        if load_id is None:
            raise RuntimeError(
                "No fue posible obtener el ID "
                "de la carga creada.",
            )

        for product in products:
            self.db.execute_query(
                """
                INSERT INTO catalog_load_products (
                    load_id,
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
                    image_hash,
                    content_hash
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
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

        return int(load_id)

    def apply(
        self,
        load_id: int,
    ) -> bool:
        """
        Aplica una carga histórica al catálogo actual.

        Esta es la única operación que debe cambiar
        explícitamente la carga visible/aplicada.
        """

        load = self.get_by_id(
            load_id,
        )

        if load is None:
            return False

        products = self.db.fetch_all(
            """
            SELECT
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
                image_hash,
                content_hash
            FROM catalog_load_products
            WHERE load_id = ?
            ORDER BY id
            """,
            (load_id,),
        )

        connection = self.db.connection

        try:
            connection.execute(
                "BEGIN",
            )

            connection.execute(
                "DELETE FROM products",
            )

            for product in products:
                connection.execute(
                    """
                    INSERT INTO products (
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
                        image_hash,
                        content_hash
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    )
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
                SET applied = 0
                """,
            )

            connection.execute(
                """
                UPDATE catalog_loads
                SET applied = 1
                WHERE id = ?
                """,
                (load_id,),
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        return True

    def get_by_id(
        self,
        load_id: int,
    ):
        return self.db.fetch_one(
            """
            SELECT *
            FROM catalog_loads
            WHERE id = ?
            """,
            (load_id,),
        )

    def get_latest(
        self,
        limit: int = 10,
    ):
        return self.db.fetch_all(
            """
            SELECT *
            FROM catalog_loads
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def get_latest_applied(self):
        """
        Devuelve la última carga que el usuario dejó aplicada.
        """

        return self.db.fetch_one(
            """
            SELECT *
            FROM catalog_loads
            WHERE applied = 1
            ORDER BY id DESC
            LIMIT 1
            """,
        )

    def get_latest_successful(self):
        """
        Devuelve la última carga exitosa disponible,
        independientemente de si está aplicada.
        """

        return self.db.fetch_one(
            """
            SELECT *
            FROM catalog_loads
            WHERE status = 'SUCCESS'
            ORDER BY id DESC
            LIMIT 1
            """,
        )

    def has_applied_load(self) -> bool:
        """
        Indica si existe una carga aplicada.
        """

        return self.get_latest_applied() is not None

    def ensure_initial_applied_load(self) -> int | None:
        """
        Inicializa el estado de cargas para instalaciones
        existentes.

        Si ya existe una carga aplicada, no modifica nada.

        Si no existe ninguna carga aplicada pero sí existen
        cargas exitosas, aplica la última carga exitosa.

        Devuelve el ID de la carga aplicada o None.
        """

        applied = self.get_latest_applied()

        if applied is not None:
            return int(applied["id"])

        latest = self.get_latest_successful()

        if latest is None:
            return None

        load_id = int(latest["id"])

        if self.apply(load_id):
            return load_id

        return None
