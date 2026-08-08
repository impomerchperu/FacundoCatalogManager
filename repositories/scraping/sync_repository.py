from scrapers.sync.content_hash import ContentHash


class SyncRepository:
    """
    Repository encargado de almacenar snapshots
    de productos para sincronización incremental.
    """

    def __init__(self, db=None):
        self.db = db
        self.records = {}

    def save(self, product):
        """
        Guarda o actualiza un producto sincronizado.
        """

        if isinstance(product, list):
            for item in product:
                self.save(item)

            return

        self._ensure_hash(product)

        if self.db:
            query = """
            INSERT INTO sync_records (
                code,
                url,
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
                content_hash,
                image_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(code)
            DO UPDATE SET
                url = excluded.url,
                name = excluded.name,
                category = excluded.category,
                description = excluded.description,
                price = excluded.price,
                price_sample = excluded.price_sample,
                price_hundred = excluded.price_hundred,
                price_thousand = excluded.price_thousand,
                stock = excluded.stock,
                image_url = excluded.image_url,
                image_path = excluded.image_path,
                content_hash = excluded.content_hash,
                image_hash = excluded.image_hash,
                updated_at = CURRENT_TIMESTAMP
            """

            self.db.execute_query(
                query,
                (
                    self._get(product, "code"),
                    self._get(product, "url"),
                    self._get(product, "name"),
                    self._get(product, "category"),
                    self._get(product, "description"),
                    self._get(product, "price"),
                    self._get(product, "price_sample"),
                    self._get(product, "price_hundred"),
                    self._get(product, "price_thousand"),
                    self._get(product, "stock"),
                    self._get(product, "image_url"),
                    self._get(product, "image_path"),
                    self._get(product, "content_hash"),
                    self._get(product, "image_hash"),
                ),
            )

            return

        self.records[self._get(product, "code")] = product

    def get(self, code):
        """
        Obtiene un producto sincronizado por código.
        """

        if self.db:
            query = """
            SELECT
                code,
                url,
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
                content_hash,
                image_hash
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

    def load(self):
        """
        Obtiene todos los snapshots almacenados.
        """

        if self.db:
            query = """
            SELECT
                code,
                url,
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
                content_hash,
                image_hash
            FROM sync_records
            """

            results = self.db.fetch_all(query)

            return [
                dict(row)
                for row in results
            ]

        return list(self.records.values())

    def save_all(self, products):
        """
        Guarda una colección completa.
        """

        for product in products:
            self.save(product)

    def delete(self, code):
        """
        Elimina un producto sincronizado.
        """

        if self.db:
            query = """
            DELETE FROM sync_records
            WHERE code = ?
            """

            self.db.execute_query(
                query,
                (code,),
            )

            return

        self.records.pop(
            code,
            None,
        )

    def _ensure_hash(self, product):
        """
        Genera content_hash si no existe.
        """

        current = self._get(
            product,
            "content_hash",
        )

        if not current:
            product.content_hash = ContentHash.generate(
                product,
            )

    def _get(self, product, field):
        if isinstance(product, dict):
            return product.get(
                field,
                "",
            )

        return getattr(
            product,
            field,
            "",
        )
