class SyncRepository:

    def __init__(self, db):

        self.db = db


    def get(self, code):

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

        rows = self.db.fetch_all(
            query,
            (code,)
        )

        if not rows:
            return None


        row = rows[0]

        return {
            "code": row[0],
            "name": row[1],
            "category": row[2],
            "price": row[3],
            "stock": row[4],
            "image_path": row[5],
            "image_url": row[6],
        }



    def save(self, product):

        query = """
        INSERT INTO sync_records
        (
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

            name=excluded.name,
            category=excluded.category,
            price=excluded.price,
            stock=excluded.stock,
            image_path=excluded.image_path,
            image_url=excluded.image_url,
            updated_at=CURRENT_TIMESTAMP
        """

        self.db.execute_query(
            query,
            (
                product.code,
                product.name,
                product.category,
                product.price,
                getattr(product, "stock", 0),
                getattr(product, "image_path", ""),
                getattr(product, "image_url", ""),
            )
        )