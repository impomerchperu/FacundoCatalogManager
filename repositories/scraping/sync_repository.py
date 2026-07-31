class SyncRepository:

    def __init__(self, db=None):

        self.db = db
        self.records = {}


    def save(self, product):

        if self.db:

            query = """
            INSERT INTO sync_records (
                code,
                name,
                category,
                price,
                stock,
                image_path,
                image_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(code)
            DO UPDATE SET
                name = excluded.name,
                category = excluded.category,
                price = excluded.price,
                stock = excluded.stock,
                image_path = excluded.image_path,
                image_url = excluded.image_url
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
                ),
            )

            return


        self.records[product.code] = product



    def get(self, code):

        if self.db:

            query = """
            SELECT
                code,
                name,
                category,
                price,
                stock,
                image_path,
                image_url
            FROM sync_records
            WHERE code = ?
            """

            result = self.db.fetch_one(
                query,
                (code,)
            )

            if result is None:
                return None

            return dict(result)


        return self.records.get(code)