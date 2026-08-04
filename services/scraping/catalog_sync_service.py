import sqlite3

from models.scraping.scraped_product import ScrapedProduct
from services.scraping.scraped_product_mapper import ScrapedProductMapper
from services.scraping.sync_result import SyncResult


class CatalogSyncService:
    """
    Sincroniza productos scrapeados
    contra el catálogo local.
    """

    def __init__(
        self,
        repository,
        diff_service,
        mapper=None,
    ):
        self.repository = repository
        self.diff_service = diff_service
        self.mapper = mapper or ScrapedProductMapper()

    def synchronize(
        self,
        products,
    ):
        """
        Ejecuta sincronización incremental.
        """

        result = SyncResult()

        for item in products:
            result.increment_processed()

            try:
                product = self._prepare_product(
                    item,
                )

                existing = self.repository.get(
                    product.code,
                )

                if existing is None:
                    self.repository.save(
                        product,
                    )

                    result.created += 1
                    continue

                diff = self.diff_service.compare(
                    existing,
                    product,
                )

                if diff["changed"]:

                    self.repository.save(
                        product,
                    )

                    result.updated += 1

                    result.changes.append(
                        {
                            "code": product.code,
                            "fields": diff["fields"],
                        }
                    )

                else:
                    result.unchanged += 1

            except (
                ValueError,
                AttributeError,
                sqlite3.Error,
            ) as error:

                result.errors += 1

                result.failures.append(
                    {
                        "product": getattr(
                            item,
                            "code",
                            "unknown",
                        ),
                        "error": str(error),
                    }
                )

        result.finish()

        return result

    def sync(
        self,
        products,
    ):
        return self.synchronize(
            products,
        )

    def _prepare_product(
        self,
        product,
    ):

        if isinstance(
            product,
            ScrapedProduct,
        ):
            return self.mapper.to_product(
                product,
            )

        return product
