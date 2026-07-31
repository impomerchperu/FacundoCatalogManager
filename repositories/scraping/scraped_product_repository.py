class ScrapedProductRepository:
    def __init__(self, db):
        self.db = db

    def create(self, product):

        query = """
        INSERT INTO scraped_products (
            source,
            url,
            code,
            name,
            category,
            price,
            image_url,
            description
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            product.source,
            product.url,
            product.code,
            product.name,
            product.category,
            product.price,
            product.image_url,
            product.description,
        )

        self.db.execute_query(query, params)

    def save(self, product):

        self.create(product)

    def get_by_url(self, url):

        query = """
        SELECT *
        FROM scraped_products
        WHERE url = ?
        """

        result = self.db.fetch_all(query, (url,))

        if result:
            return result[0]

        return None

    def get_all(self):

        query = """
        SELECT *
        FROM scraped_products
        """

        return self.db.fetch_all(query)
