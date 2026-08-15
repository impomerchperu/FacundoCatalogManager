from models.scraping.sync_result import SyncResult


class SyncController:
    """Controlador de sincronización del catálogo."""

    def __init__(self, runner):
        self.runner = runner

    def synchronize(self, categories) -> SyncResult:
        try:
            products = self.runner.run(categories)
            sync_result = getattr(
                self.runner.scraping_service,
                "last_sync_result",
                None,
            )

            if isinstance(sync_result, SyncResult):
                result = SyncResult(
                    success=sync_result.success,
                    started_at=sync_result.started_at,
                    finished_at=sync_result.finished_at,
                    processed=sync_result.processed,
                    created=sync_result.created,
                    updated=sync_result.updated,
                    unchanged=sync_result.unchanged,
                    changes=list(sync_result.changes),
                    failures=list(sync_result.failures),
                    categories_processed=sync_result.categories_processed,
                    products_found=sync_result.products_found,
                    products_created=sync_result.products_created,
                    products_updated=sync_result.products_updated,
                    products_unchanged=sync_result.products_unchanged,
                    images_processed=sync_result.images_processed,
                    images_downloaded=sync_result.images_downloaded,
                    images_failed=sync_result.images_failed,
                    errors=list(sync_result.errors),
                )
                return result

            # Compatibilidad con runners antiguos que no exponen
            # last_sync_result: en ese caso solo podemos reportar lo procesado.
            result = SyncResult()
            result.processed = len(products)
            result.unchanged = len(products)
            result.finish()
            return result

        except (RuntimeError, ValueError, TypeError) as error:
            result = SyncResult()
            result.add_error(str(error))
            result.failures.append(str(error))
            result.finish()
            return result
