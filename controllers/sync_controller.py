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
                return SyncResult(
                    success=sync_result.success,
                    started_at=sync_result.started_at,
                    finished_at=sync_result.finished_at,
                    run_id=sync_result.run_id,
                    processed=sync_result.processed,
                    created=sync_result.created,
                    updated=sync_result.updated,
                    unchanged=sync_result.unchanged,
                    deleted=sync_result.deleted,
                    generated=sync_result.generated,
                    missing_code=sync_result.missing_code,
                    changes=list(sync_result.changes),
                    failures=list(sync_result.failures),
                    categories_processed=sync_result.categories_processed,
                    products_expected=sync_result.products_expected,
                    expected_category_occurrences=sync_result.expected_category_occurrences,
                    products_found=sync_result.products_found,
                    products_unique=sync_result.products_unique,
                    products_multiple_categories=sync_result.products_multiple_categories,
                    duplicate_occurrences=sync_result.duplicate_occurrences,
                    category_summary=list(sync_result.category_summary),
                    multiple_category_products=list(sync_result.multiple_category_products),
                    images_processed=sync_result.images_processed,
                    images_downloaded=sync_result.images_downloaded,
                    images_failed=sync_result.images_failed,
                    errors=list(sync_result.errors),
                )

            # Compatibilidad con runners antiguos que no exponen
            # last_sync_result: en ese caso solo podemos reportar lo procesado.
            result = SyncResult()
            result.processed = len(products)
            result.unchanged = len(products)
        except (RuntimeError, ValueError, TypeError) as error:
            result = SyncResult()
            result.add_error(str(error))
            result.failures.append(str(error))
        else:
            result.finish()
            return result

        result.finish()
        return result
