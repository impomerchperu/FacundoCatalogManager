class SyncRepository:
    """
    Repository encargado de almacenar registros
    de sincronización incremental.
    """

    def __init__(self, db=None):
        self.db = db
        self.records = {}

    def save(self, product):
        """
        Guarda o actualiza un registro de sincronización.
        """

        if self.db:

            query = """
            INSERT INTO sync_records (
                code,
                name,
                category,
                price,
                stock,
                image_path,
                image_url,
                hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(code)
            DO UPDATE SET
                name = excluded.name,
                category = excluded.category,
                price = excluded.price,
                stock = excluded.stock,
                image_path = excluded.image_path,
                image_url = excluded.image_url,
                hash = excluded.hash,
                updated_at = CURRENT_TIMESTAMP
            """

            self.db.execute_query(
                query,
                (
                    product.code,
                    product.name,
                    product.category,
                    product.price,
                    product.stock,
                    product.image_path,
                    product.image_url,
                    getattr(
                        product,
                        "content_hash",
                        "",
                    ),
                ),
            )

            return

        self.records[product.code] = product

    def get(self, code):
        """
        Obtiene un registro por código.
        """

        if self.db:

            query = """
            SELECT
                code,
                name,
                category,
                price,
                stock,
                image_path,
                image_url,
                hash
            FROM sync_records
            WHERE code = ?
            """

            result = self.db.fetch_one(
                query,
                (code,),
            )

            if result is None:
                return None

            return dict(result)

        return self.records.get(code)
