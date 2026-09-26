from PySide6.QtCore import QObject, Signal, Slot

from services.catalog_bootstrap_service import CatalogBootstrapService
from services.catalog_seed_service import CatalogSeedService


class CatalogBootstrapWorker(QObject):
    """Ejecuta la reparación inicial fuera del hilo de la interfaz."""

    finished = Signal(int, bool)
    error = Signal(str)

    @Slot()
    def run(self) -> None:
        service = None
        seeded = False
        try:
            seeded = CatalogSeedService.seed_if_needed()
            service = CatalogBootstrapService()
            count = service.bootstrap()
            self.finished.emit(
                count,
                seeded or service.last_bootstrap_changed,
            )
        except Exception as error:  # noqa: BLE001
            self.error.emit(str(error))
        finally:
            if service is not None:
                service.db.close()
