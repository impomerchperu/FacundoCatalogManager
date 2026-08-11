from PySide6.QtCore import QElapsedTimer, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from gui.workers.scraping_worker import ScrapingWorker


class ScrapingDialog(QDialog):
    """Ventana manual de actualización del catálogo."""

    finished_success = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.scraping_thread: QThread | None = None
        self.worker: ScrapingWorker | None = None
        self.pending_result = None
        self.pending_error: str | None = None
        self.elapsed_timer = QElapsedTimer()
        self.elapsed_clock = QTimer(self)
        self.elapsed_clock.setInterval(250)
        self.elapsed_clock.timeout.connect(self.update_elapsed_status)

        self.setWindowTitle("Actualizar catálogo")
        self.resize(560, 320)
        self.build_ui()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

    def build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.status_label = QLabel("Listo para actualizar catálogo.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFormat("%p%")
        layout.addWidget(self.progress)

        buttons = QHBoxLayout()

        self.start_button = QPushButton("Iniciar actualización")
        self.start_button.clicked.connect(self.start_scraping)
        buttons.addWidget(self.start_button)

        self.details_button = QPushButton("Ver detalle")
        self.details_button.setEnabled(False)
        self.details_button.clicked.connect(self.show_result_details)
        buttons.addWidget(self.details_button)

        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.close)
        buttons.addWidget(close_button)

        layout.addLayout(buttons)

    def start_scraping(self) -> None:
        if self.scraping_thread is not None and self.scraping_thread.isRunning():
            return

        self.start_button.setEnabled(False)
        self.details_button.setEnabled(False)
        self.progress.setValue(0)
        self.status_label.setText("Preparando actualización... 0%")
        self.pending_result = None
        self.pending_error = None
        self.elapsed_timer.start()
        self.elapsed_clock.start()

        self.scraping_thread = QThread(self)
        self.worker = ScrapingWorker()
        self.worker.moveToThread(self.scraping_thread)

        self.scraping_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.scraping_finished)
        self.worker.error.connect(self.scraping_error)
        self.worker.finished.connect(self.scraping_thread.quit)
        self.worker.error.connect(self.scraping_thread.quit)
        self.scraping_thread.finished.connect(self.cleanup_thread)
        self.scraping_thread.finished.connect(self.thread_finished)
        self.scraping_thread.start()

    def update_progress(self, current: int, total: int) -> None:
        if total <= 0:
            return

        value = min(100, int(current * 100 / total))
        self.progress.setValue(value)
        elapsed = self._format_elapsed()
        self.status_label.setText(
            f"Procesando categoría {current}/{total} "
            f"• {value}% • {elapsed}",
        )

    def update_elapsed_status(self) -> None:
        if self.scraping_thread is None or not self.scraping_thread.isRunning():
            return

        elapsed = self._format_elapsed()
        self.status_label.setText(
            f"Actualización en curso • {self.progress.value()}% "
            f"• {elapsed}",
        )

    def scraping_finished(self, result) -> None:
        self.pending_result = result
        self.progress.setValue(100)
        self.elapsed_clock.stop()
        self.status_label.setText(
            f"Actualización completada • 100% • {self._format_elapsed()}",
        )
        self.finished_success.emit()

    def scraping_error(self, message: str) -> None:
        self.pending_error = message
        self.elapsed_clock.stop()
        self.status_label.setText(
            f"La actualización terminó con errores • "
            f"{self._format_elapsed()}",
        )

    def thread_finished(self) -> None:
        """Muestra el resultado solamente después de que QThread haya terminado."""
        result = self.pending_result
        error = self.pending_error

        QTimer.singleShot(
            0,
            lambda: self.show_thread_result(result, error),
        )

    def show_thread_result(self, result, error: str | None) -> None:
        if error is not None:
            QMessageBox.critical(
                self,
                "Error de scraping",
                error,
            )
            self.start_button.setEnabled(True)
            return

        if result is not None:
            self.details_button.setEnabled(True)
            self.show_result(result)

        self.start_button.setEnabled(True)

    def show_result(self, result) -> None:
        QMessageBox.information(
            self,
            "Resumen actualización",
            (
                f"Productos procesados: {result.processed}\n\n"
                f"Nuevos: {result.created}\n"
                f"Actualizados: {result.updated}\n"
                f"Sin cambios: {result.unchanged}\n\n"
                f"Errores: {len(result.errors)}\n\n"
                "Use 'Ver detalle' para revisar los productos nuevos "
                "y las variaciones detectadas."
            ),
        )

    def show_result_details(self) -> None:
        result = self.pending_result
        if result is None:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Detalle de la descarga")
        dialog.resize(1000, 600)
        layout = QVBoxLayout(dialog)

        summary = QLabel(
            f"Procesados: {result.processed}    "
            f"Nuevos: {result.created}    "
            f"Actualizados: {result.updated}    "
            f"Sin cambios: {result.unchanged}    "
            f"Errores: {len(result.errors)}",
        )
        summary.setStyleSheet("font-weight: bold;")
        layout.addWidget(summary)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["Tipo", "Código", "Producto", "Variación", "Anterior", "Nuevo"],
        )
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setWordWrap(True)

        rows = []
        for change in result.changes:
            if change["type"] == "NEW":
                rows.append(
                    (
                        "NUEVO",
                        str(change["code"]),
                        str(change["name"]),
                        "Producto nuevo",
                        "—",
                        "Alta",
                    ),
                )
                continue

            for field_change in change["changes"]:
                rows.append(
                    (
                        "ACTUALIZADO",
                        str(change["code"]),
                        str(change["name"]),
                        str(field_change["label"]),
                        self._format_value(field_change["old"]),
                        self._format_value(field_change["new"]),
                    ),
                )

        table.setRowCount(max(len(rows), 1))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {0, 3}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column in {0, 3, 4, 5}:
                    font = QFont(item.font())
                    font.setBold(column in {0, 3})
                    item.setFont(font)
                    item.setBackground(table.palette().highlight())
                table.setItem(row, column, item)

        if not rows:
            table.setItem(0, 0, QTableWidgetItem("—"))
            table.setItem(0, 3, QTableWidgetItem("Sin variaciones"))

        table.resizeColumnsToContents()
        layout.addWidget(table)

        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    @staticmethod
    def _format_value(value) -> str:
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:,.2f}"
        return str(value)

    def _format_elapsed(self) -> str:
        if not self.elapsed_timer.isValid():
            return "00:00"
        seconds = self.elapsed_timer.elapsed() // 1000
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def cleanup_thread(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()

        if self.scraping_thread is not None:
            self.scraping_thread.deleteLater()

        self.worker = None
        self.scraping_thread = None
