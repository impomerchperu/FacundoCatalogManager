from models.scraping.sync_result import SyncResult


class CatalogSyncService:
    """
    Sincroniza productos del catálogo contra un repositorio.

    Responsabilidades:
    - Crear productos nuevos.
    - Actualizar productos modificados.
    - Registrar productos sin cambios.
    - Generar un resultado consolidado de sincronización.
    """

    def __init__(
        self,
        repository,
        diff_service,
    ):
        self.repository = repository
        self.diff_service = diff_service

    def sync(self, products):
        """
        Ejecuta la sincronización de una colección de productos.

        Retorna:
            SyncResult con métricas del proceso.
        """

        result = SyncResult()

        for product in products:

            result.increment_processed()

            existing = self.repository.get(product.code)

            if existing is None:
                self.repository.save(product)
                result.created += 1
                continue

            if self.diff_service.has_changes(
                existing,
                product,
            ):
                self.repository.save(product)
                result.updated += 1

            else:
                result.unchanged += 1

        result.finish()

        return result

    def synchronize(self, products):
        """
        Alias público para mantener compatibilidad.
        """

        return self.sync(products)
