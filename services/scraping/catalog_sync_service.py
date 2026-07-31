from services.scraping.sync_result import SyncResult


class CatalogSyncService:

    def __init__(
        self,
        repository,
        diff_service,
    ):

        self.repository = repository
        self.diff_service = diff_service


    def synchronize(self, products):

        result = SyncResult()


        for product in products:

            existing = self.repository.get(
                product.code
            )


            if existing is None:

                self.repository.save(
                    product
                )

                result.created += 1

                continue


            diff = self.diff_service.compare(
                existing.__dict__,
                product.__dict__,
            )


            if diff["changed"]:

                self.repository.save(
                    product
                )

                result.updated += 1

            else:

                result.unchanged += 1


        return result