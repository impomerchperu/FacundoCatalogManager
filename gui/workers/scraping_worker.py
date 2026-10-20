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
        """Ejecuta scraping y solo notifica el resultado tras liberar recursos."""
        controller = None
        result = None
        error_message = None
        try:
            controller = ScrapingController()
            result = controller.run_full_scraping(
                progress_callback=self.emit_progress,
            )
        except Exception as error:  # noqa: BLE001
            error_message = str(error)
        finally:
            if controller is not None:
                try:
                    controller.close()
                except Exception as error:  # noqa: BLE001
                    if error_message is None:
                        error_message = (
                            "La actualización terminó, pero no se pudieron "
                            f"liberar todos los recursos: {error}"
                        )

        # The GUI must not announce completion while close() is still running.
        if error_message is not None:
            self.error.emit(error_message)
        else:
            self.finished.emit(result)

    def emit_progress(self, current: int, total: int) -> None:
        """Envía progreso hacia la interfaz."""
        self.progress.emit(current, total)
