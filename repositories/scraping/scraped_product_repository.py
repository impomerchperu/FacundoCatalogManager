from models.scraping.scraped_product import ScrapedProduct


class ScrapedProductRepository:

    def __init__(self, db):
        self.db = db


    def create(self, product: ScrapedProduct):

        query = """
        INSERT INTO scraped_products
        (
            url,
            code,
            name,
            category,
            description,
            price,
            image_url
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            product.url,
            product.code,
            product.name,
            product.category,
            product.description,
            product.price,
            product.image_url
        )

        self.db.execute_query(query, params)


    def get_by_url(self, url):

        query = """
        SELECT *
        FROM scraped_products
        WHERE url = ?
        """

        return self.db.fetch_one(query, (url,))


    def get_all(self):

        query = """
        SELECT *
        FROM scraped_products
        """

        return self.db.fetch_all(query)


    def delete(self, url):

        query = """
        DELETE FROM scraped_products
        WHERE url = ?
        """

        self.db.execute_query(query, (url,))