from services.scraping.sync_result import SyncResult


class SyncController:
    """
    Controlador de sincronización del catálogo.
    """

    def __init__(
        self,
        runner,
    ):
        self.runner = runner

    def synchronize(
        self,
        categories,
    ) -> SyncResult:

        result = SyncResult()

        try:
            products = self.runner.run(
                categories,
            )

            result.processed = len(products)

            result.created = len(products)

        except (RuntimeError, ValueError, TypeError) as error:

            result.errors += 1

            result.failures.append(
                str(error),
            )

        result.finish()

        return result
