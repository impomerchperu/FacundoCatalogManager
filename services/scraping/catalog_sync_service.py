from models.scraping.sync_result import SyncResult


class CatalogSyncService:
    """
    Compara productos obtenidos durante el scraping contra
    el catálogo actualmente aplicado.

    IMPORTANTE:
    Este servicio no modifica el catálogo visible.

    Su responsabilidad es exclusivamente:
    - Detectar productos nuevos.
    - Detectar productos modificados.
    - Detectar productos sin cambios.
    - Generar el resultado de sincronización.
    - Mantener actualizado el snapshot incremental.

    La persistencia de una nueva versión del catálogo queda
    a cargo de CatalogLoadRepository.
    """

    def __init__(
        self,
        repository,
        diff_service,
    ):
        self.repository = repository
        self.diff_service = diff_service

    def sync(
        self,
        products,
    ):
        """
        Compara una colección de productos contra el
        snapshot incremental almacenado.

        Retorna:
            SyncResult con las métricas del proceso.
        """

        result = SyncResult()

        for product in products:
            result.increment_processed()

            existing = self.repository.get(
                product.code,
            )

            if existing is None:
                result.created += 1

                self.repository.save(
                    product,
                )

                continue

            if self.diff_service.has_changes(
                existing,
                product,
            ):
                result.updated += 1

                self.repository.save(
                    product,
                )

                continue

            result.unchanged += 1

        result.finish()

        return result

    def synchronize(
        self,
        products,
    ):
        """
        Alias público para mantener compatibilidad.
        """

        return self.sync(
            products,
        )
