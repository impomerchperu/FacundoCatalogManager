from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from gui.workers.scraping_worker import ScrapingWorker


class ScrapingDialog(QDialog):
    """
    Ventana manual de actualización del catálogo.

    Ejecuta scraping en segundo plano
    mediante QThread.
    """

    finished_success = Signal()

    def __init__(
        self,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.scraping_thread: QThread | None = None
        self.worker: ScrapingWorker | None = None

        self.setWindowTitle(
            "Actualizar catálogo",
        )

        self.resize(
            500,
            280,
        )

        self.build_ui()

    def build_ui(self) -> None:
        layout = QVBoxLayout(
            self,
        )

        self.status_label = QLabel(
            "Listo para actualizar catálogo.",
        )

        layout.addWidget(
            self.status_label,
        )

        self.progress = QProgressBar()

        layout.addWidget(
            self.progress,
        )

        buttons = QHBoxLayout()

        self.start_button = QPushButton(
            "Iniciar actualización",
        )

        self.start_button.clicked.connect(
            self.start_scraping,
        )

        buttons.addWidget(
            self.start_button,
        )

        close_button = QPushButton(
            "Cerrar",
        )

        close_button.clicked.connect(
            self.close,
        )

        buttons.addWidget(
            close_button,
        )

        layout.addLayout(
            buttons,
        )

    def start_scraping(self) -> None:
        self.start_button.setEnabled(
            False,
        )

        self.progress.setValue(
            0,
        )

        self.status_label.setText(
            "Ejecutando scraping...",
        )

        self.scraping_thread = QThread(
            self,
        )

        self.worker = ScrapingWorker()

        self.worker.moveToThread(
            self.scraping_thread,
        )

        self.scraping_thread.started.connect(
            self.worker.run,
        )

        self.worker.progress.connect(
            self.update_progress,
        )

        self.worker.finished.connect(
            self.scraping_finished,
        )

        self.worker.error.connect(
            self.scraping_error,
        )

        self.worker.finished.connect(
            self.scraping_thread.quit,
        )

        self.worker.error.connect(
            self.scraping_thread.quit,
        )

        self.scraping_thread.finished.connect(
            self.cleanup_thread,
        )

        self.scraping_thread.start()

    def update_progress(
        self,
        current: int,
        total: int,
    ) -> None:
        if total <= 0:
            return

        value = int(
            current * 100 / total,
        )

        self.progress.setValue(
            value,
        )

        self.status_label.setText(
            f"Procesando categoría {current}/{total}...",
        )

    def scraping_finished(
        self,
        result,
    ) -> None:
        self.progress.setValue(
            100,
        )

        self.status_label.setText(
            "Actualización completada.",
        )

        self.finished_success.emit()

        self.show_result(
            result,
        )

        self.start_button.setEnabled(
            True,
        )

    def scraping_error(
        self,
        message: str,
    ) -> None:
        self.start_button.setEnabled(
            True,
        )

        self.status_label.setText(
            "La actualización terminó con errores.",
        )

        QMessageBox.critical(
            self,
            "Error de scraping",
            message,
        )

    def show_result(
        self,
        result,
    ) -> None:
        QMessageBox.information(
            self,
            "Resumen actualización",
            (
                f"Productos procesados: "
                f"{result.processed}\n\n"
                f"Nuevos: "
                f"{result.created}\n"
                f"Actualizados: "
                f"{result.updated}\n"
                f"Sin cambios: "
                f"{result.unchanged}\n\n"
                f"Errores: "
                f"{len(result.errors)}"
            ),
        )

    def cleanup_thread(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()

        if self.scraping_thread is not None:
            self.scraping_thread.deleteLater()

        self.worker = None
        self.scraping_thread = None
