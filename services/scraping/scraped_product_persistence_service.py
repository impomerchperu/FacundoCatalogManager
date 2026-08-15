from models.scraping.scraped_product import ScrapedProduct


class ScrapedProductPersistenceService:
    """
    Servicio encargado de persistir productos obtenidos
    mediante scraping.
    """

    def __init__(self, repository):
        self.repository = repository

    def save_products(self, products):
        """
        Guarda una colección de productos.

        Mantiene compatibilidad:
        - dict -> devuelve dict original
        - ScrapedProduct -> devuelve objeto original
        """

        saved = []

        for product in products:
            if isinstance(product, dict):
                self.repository.save(product)
                saved.append(product)
                continue

            if isinstance(product, ScrapedProduct):
                self.repository.save(product)
                saved.append(product)

        return saved
