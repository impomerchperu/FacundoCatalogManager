class ScrapedProductPersistenceService:
    def __init__(self, repository):
        self.repository = repository

    def save_products(self, products):

        saved = []

        for product in products:
            self.repository.save(product)

            saved.append(product)

        return saved
