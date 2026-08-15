from PySide6.QtCore import QObject, Signal, Slot

from controllers.scraping_controller import ScrapingController


class ScrapingWorker(QObject):
    """Worker encargado de ejecutar scraping en segundo plano."""

    progress = Signal(int, int)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()

    @Slot()
    def run(self) -> None:
        """Ejecuta el scraping completo y comunica siempre su resultado."""
        try:
            controller = ScrapingController()
            result = controller.run_full_scraping(
                progress_callback=self.emit_progress,
            )
            self.finished.emit(result)
        except Exception as error:  # noqa: BLE001
            self.error.emit(str(error))

    def emit_progress(self, current: int, total: int) -> None:
        """Envía progreso hacia la interfaz."""
        self.progress.emit(current, total)
