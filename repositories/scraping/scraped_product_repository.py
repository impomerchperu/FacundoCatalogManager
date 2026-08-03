from models.scraping.scraped_product import ScrapedProduct


class ScrapedProductRepository:
    """
    Repository encargado de persistir productos
    obtenidos mediante scraping.
    """

    def __init__(self, db):
        self.db = db

    def save(self, product: ScrapedProduct):
        """
        Guarda un producto.

        Si la URL ya existe:
        actualiza.
        Si no existe:
        inserta.
        """

        existing = self.get_by_url(product.url)

        if existing:
            self.update(product)
        else:
            self.create(product)

    def create(self, product: ScrapedProduct):
        """
        Inserta un nuevo producto scrapeado.
        """

        query = """
        INSERT INTO scraped_products (
            source,
            url,
            code,
            name,
            category,
            description,
            stock,
            price,
            price_sample,
            price_hundred,
            price_thousand,
            image_url,
            image_path
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            product.source,
            product.url,
            product.code,
            product.name,
            product.category,
            product.description,
            product.stock,
            product.price,
            product.price_sample,
            product.price_hundred,
            product.price_thousand,
            product.image_url,
            product.image_path,
        )

        self.db.execute_query(query, params)

    def update(self, product: ScrapedProduct):
        """
        Actualiza un producto existente.
        """

        query = """
        UPDATE scraped_products
        SET
            source = ?,
            code = ?,
            name = ?,
            category = ?,
            description = ?,
            stock = ?,
            price = ?,
            price_sample = ?,
            price_hundred = ?,
            price_thousand = ?,
            image_url = ?,
            image_path = ?,
            updated_at = CURRENT_TIMESTAMP

        WHERE url = ?
        """

        params = (
            product.source,
            product.code,
            product.name,
            product.category,
            product.description,
            product.stock,
            product.price,
            product.price_sample,
            product.price_hundred,
            product.price_thousand,
            product.image_url,
            product.image_path,
            product.url,
        )

        self.db.execute_query(query, params)

    def get_by_url(self, url):
        """
        Busca un producto mediante URL.
        """

        query = """
        SELECT *
        FROM scraped_products
        WHERE url = ?
        """

        result = self.db.fetch_all(
            query,
            (url,),
        )

        if result:
            return result[0]

        return None

    def get_all(self):
        """
        Obtiene todos los productos scrapeados.
        """

        query = """
        SELECT *
        FROM scraped_products
        ORDER BY id
        """

        return self.db.fetch_all(query)

    def delete_by_url(self, url):
        """
        Elimina un producto por URL.
        """

        query = """
        DELETE FROM scraped_products
        WHERE url = ?
        """

        self.db.execute_query(
            query,
            (url,),
        )
