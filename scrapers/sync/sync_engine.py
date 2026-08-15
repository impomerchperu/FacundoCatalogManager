import sqlite3

from repositories.scraping.sync_repository import SyncRepository
from scrapers.sync.image_sync import ImageSync
from scrapers.sync.product_comparator import ProductComparator
from scrapers.sync.sync_result import SyncResult


class SyncEngine:
    """
    Motor principal de sincronización incremental.
    """

    def __init__(
        self,
        storage=None,
        comparator=None,
        image_sync=None,
    ):

        self.storage = storage or SyncRepository()

        self.comparator = (
            comparator
            or ProductComparator()
        )

        self.image_sync = (
            image_sync
            or ImageSync()
        )


    def synchronize(
        self,
        products,
    ):

        result = SyncResult()


        try:

            old_products = self.storage.load()

            comparison = self.comparator.compare(
                old_products,
                products,
            )


            result.new = comparison["new"]

            result.updated = comparison["updated"]

            result.unchanged = comparison["unchanged"]

            result.removed = comparison["removed"]


            processed = self._merge_images(
                products,
                old_products,
                comparison,
                result,
            )


            self.storage.save(
                processed
            )


        except (
            sqlite3.Error,
            AttributeError,
            ValueError,
            TypeError,
        ) as error:

            result.errors.append(
                str(error)
            )


        return result



    def _merge_images(
        self,
        products,
        old_products,
        comparison,
        result,
    ):

        old_map = {
            self._get_code(product): product
            for product in old_products
            if self._get_code(product)
        }


        changed_codes = {
            self._get_code(product)
            for product in (
                comparison["new"]
                +
                comparison["updated"]
            )
        }


        processed = []


        for product in products:

            code = self._get_code(product)

            old = old_map.get(code)


            if code not in changed_codes:

                if old:

                    product.image_path = (
                        self._get_value(
                            old,
                            "image_path",
                        )
                    )

                    product.image_hash = (
                        self._get_value(
                            old,
                            "image_hash",
                        )
                    )


                processed.append(product)

                continue


            try:

                product = self.image_sync.sync_product(
                    product,
                    old,
                )


                if self._get_value(
                    product,
                    "image_path",
                ):

                    result.images_processed += 1


                if self._get_value(
                    product,
                    "image_error",
                ):

                    result.image_errors += 1


            except (
                OSError,
                AttributeError,
                ValueError,
                TypeError,
            ) as error:

                result.image_errors += 1

                result.errors.append(
                    str(error)
                )


            processed.append(product)


        return processed



    def _get_code(
        self,
        product,
    ):

        if isinstance(product, dict):

            return product.get(
                "code"
            )

        return getattr(
            product,
            "code",
            None,
        )



    def _get_value(
        self,
        product,
        field,
    ):

        if isinstance(product, dict):

            return product.get(
                field,
                "",
            )

        return getattr(
            product,
            field,
            "",
        )
