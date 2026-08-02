class ScrapedProductPersistenceService:


    def __init__(self, repository):

        self.repository = repository



    def save_products(self, products):

        saved = []


        for product in products:


            if isinstance(product, dict):

                self.repository.save(
                    product
                )

            else:

                self.repository.save(
                    product
                )


            saved.append(
                product
            )


        return saved