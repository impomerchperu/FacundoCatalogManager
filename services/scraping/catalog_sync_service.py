from models.scraping.sync_result import SyncResult


class CatalogSyncService:
    """
    Compara productos obtenidos durante el scraping contra el
    snapshot incremental almacenado.

    IMPORTANTE:

    Este servicio NO modifica el catálogo visible.

    El catálogo visible se encuentra en:

        products

    y solamente debe ser modificado mediante:

        CatalogLoadRepository.apply(load_id)

    Este servicio trabaja exclusivamente con:

        sync_records

    Responsabilidades:

    - Detectar productos nuevos.
    - Detectar productos modificados.
    - Detectar productos sin cambios.
    - Generar el resultado de sincronización.
    - Mantener actualizado el snapshot incremental.

    La creación de una nueva carga histórica queda a cargo de:

        CatalogLoadRepository
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
        snapshot incremental almacenado en sync_records.

        IMPORTANTE:

        Esta operación NO modifica products.

        Solamente actualiza el snapshot incremental para
        permitir comparar la siguiente ejecución.

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
