import sqlite3
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.db_manager import DBManager
from repositories.scraping.catalog_load_repository import (
    CatalogLoadRepository,
)
from repositories.scraping.scraping_history_repository import (
    ScrapingHistoryRepository,
)


class ScrapingHistoryDialog(QDialog):
    """
    Ventana que muestra el historial de ejecuciones
    de actualización del catálogo.

    Cada ejecución exitosa asociada a una carga histórica
    permite aplicar esa carga al catálogo visible.
    """

    catalog_applied = Signal(int)

    def __init__(
        self,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.db = DBManager()

        self.repository = ScrapingHistoryRepository(
            self.db,
        )

        self.catalog_load_repository = CatalogLoadRepository(
            self.db,
        )

        self.setWindowTitle(
            "Historial de actualizaciones",
        )

        self.resize(
            1100,
            500,
        )

        self.build_ui()
        self.load_history()

    def build_ui(self) -> None:
        layout = QVBoxLayout(
            self,
        )

        title = QLabel(
            "Historial de actualizaciones del catálogo",
        )

        title.setStyleSheet(
            "font-size: 16px; font-weight: bold;",
        )

        layout.addWidget(
            title,
        )

        self.table = QTableWidget()

        self.table.setColumnCount(
            9,
        )

        self.table.setHorizontalHeaderLabels(
            [
                "Fecha",
                "Duración",
                "Procesados",
                "Nuevos",
                "Actualizados",
                "Sin cambios",
                "Errores",
                "Estado",
                "Catálogo",
            ],
        )

        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows,
        )

        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection,
        )

        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers,
        )

        self.table.cellDoubleClicked.connect(
            self.show_details,
        )

        layout.addWidget(
            self.table,
        )

        buttons = QHBoxLayout()

        refresh_button = QPushButton(
            "Actualizar",
        )

        refresh_button.clicked.connect(
            self.load_history,
        )

        buttons.addWidget(
            refresh_button,
        )

        details_button = QPushButton(
            "Ver detalle",
        )

        details_button.clicked.connect(
            self.show_selected_details,
        )

        buttons.addWidget(
            details_button,
        )

        buttons.addStretch()

        close_button = QPushButton(
            "Cerrar",
        )

        close_button.clicked.connect(
            self.accept,
        )

        buttons.addWidget(
            close_button,
        )

        layout.addLayout(
            buttons,
        )

    def load_history(self) -> None:
        """
        Carga las últimas ejecuciones registradas.
        """

        try:
            history = self.repository.get_latest(
                limit=100,
            )

        except sqlite3.Error as error:
            QMessageBox.critical(
                self,
                "Error",
                (
                    "No fue posible cargar "
                    f"el historial.\n\n{error}"
                ),
            )
            return

        self.table.setRowCount(
            len(history),
        )

        for row, record in enumerate(history):
            started_at = self._parse_datetime(
                record.started_at,
            )

            finished_at = self._parse_datetime(
                record.finished_at,
            )

            self._set_item(
                row,
                0,
                self._format_datetime(
                    started_at,
                ),
                record,
            )

            self._set_item(
                row,
                1,
                self._format_duration(
                    started_at,
                    finished_at,
                ),
            )

            self._set_item(
                row,
                2,
                str(record.processed),
            )

            self._set_item(
                row,
                3,
                str(record.created),
            )

            self._set_item(
                row,
                4,
                str(record.updated),
            )

            self._set_item(
                row,
                5,
                str(record.unchanged),
            )

            self._set_item(
                row,
                6,
                str(record.errors),
            )

            self._set_item(
                row,
                7,
                record.status,
            )

            self._set_catalog_action(
                row,
                record.load_id,
            )

            self.table.setRowHeight(
                row,
                34,
            )

        self.table.resizeColumnsToContents()

        self.table.setColumnWidth(
            0,
            160,
        )

        self.table.setColumnWidth(
            1,
            100,
        )

        self.table.setColumnWidth(
            7,
            100,
        )

        self.table.setColumnWidth(
            8,
            130,
        )

    def _set_catalog_action(
        self,
        row: int,
        load_id: int | None,
    ) -> None:
        """
        Crea el botón de aplicación de la carga histórica.
        """

        container = QWidget()
        layout = QHBoxLayout(
            container,
        )
        layout.setContentsMargins(
            4,
            2,
            4,
            2,
        )

        if load_id is None:
            label = QLabel("Sin carga")
            label.setAlignment(
                Qt.AlignmentFlag.AlignCenter,
            )
            layout.addWidget(label)
            self.table.setCellWidget(
                row,
                8,
                container,
            )
            return

        try:
            load = self.catalog_load_repository.get_by_id(
                int(load_id),
            )
        except sqlite3.Error:
            load = None

        if load is None:
            label = QLabel("No disponible")
            label.setAlignment(
                Qt.AlignmentFlag.AlignCenter,
            )
            layout.addWidget(label)
        elif bool(load["applied"]):
            label = QLabel("Aplicado")
            label.setAlignment(
                Qt.AlignmentFlag.AlignCenter,
            )
            label.setStyleSheet(
                "font-weight: bold; color: #00838f;",
            )
            layout.addWidget(label)
        elif load["status"] == "SUCCESS":
            button = QPushButton("Aplicar")
            button.setProperty(
                "load_id",
                int(load_id),
            )
            button.clicked.connect(
                self.apply_selected_load,
            )
            layout.addWidget(button)
        else:
            label = QLabel("No aplicable")
            label.setAlignment(
                Qt.AlignmentFlag.AlignCenter,
            )
            layout.addWidget(label)

        self.table.setCellWidget(
            row,
            8,
            container,
        )

    def apply_selected_load(self) -> None:
        """
        Aplica la carga asociada al botón pulsado.
        """

        button = self.sender()

        if not isinstance(
            button,
            QPushButton,
        ):
            return

        load_id = button.property("load_id")

        if not isinstance(load_id, int):
            return

        load = self.catalog_load_repository.get_by_id(
            load_id,
        )

        if load is None:
            QMessageBox.warning(
                self,
                "Aplicar catálogo",
                "La carga seleccionada ya no está disponible.",
            )
            self.load_history()
            return

        product_count = int(
            load["product_count"],
        )

        response = QMessageBox.question(
            self,
            "Aplicar catálogo",
            (
                f"¿Desea aplicar la carga #{load_id} al "
                f"catálogo visible?\n\n"
                f"Productos: {product_count}\n\n"
                "La carga actualmente aplicada será reemplazada."
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
        )

        if response != QMessageBox.StandardButton.Yes:
            return

        try:
            applied = self.catalog_load_repository.apply(
                load_id,
            )
        except sqlite3.Error as error:
            QMessageBox.critical(
                self,
                "Error",
                (
                    "No fue posible aplicar la carga.\n\n"
                    f"{error}"
                ),
            )
            return

        if not applied:
            QMessageBox.warning(
                self,
                "Aplicar catálogo",
                "La carga seleccionada no existe.",
            )
            self.load_history()
            return

        self.load_history()

        self.catalog_applied.emit(
            load_id,
        )

        QMessageBox.information(
            self,
            "Catálogo actualizado",
            (
                f"La carga #{load_id} fue aplicada correctamente.\n\n"
                "El catálogo visible ha sido actualizado."
            ),
        )

    def show_selected_details(self) -> None:
        """
        Muestra el detalle de la ejecución seleccionada.
        """

        row = self.table.currentRow()

        if row < 0:
            QMessageBox.information(
                self,
                "Historial",
                "Seleccione una ejecución.",
            )
            return

        self.show_details(
            row,
            0,
        )

    def show_details(
        self,
        row: int,
        _column: int,
    ) -> None:
        """
        Muestra el resumen completo de una ejecución.
        """

        item = self.table.item(
            row,
            0,
        )

        if item is None:
            return

        history = item.data(
            Qt.ItemDataRole.UserRole,
        )

        if history is None:
            return

        started_at = self._parse_datetime(
            history.started_at,
        )

        finished_at = self._parse_datetime(
            history.finished_at,
        )

        duration = self._format_duration(
            started_at,
            finished_at,
        )

        message = history.message.strip()

        if not message:
            message = "Sin mensaje adicional."

        details = (
            f"Fecha de inicio:\n"
            f"{self._format_datetime(started_at)}\n\n"
            f"Fecha de finalización:\n"
            f"{self._format_datetime(finished_at)}\n\n"
            f"Duración:\n"
            f"{duration}\n\n"
            f"Productos procesados: "
            f"{history.processed}\n"
            f"Nuevos: "
            f"{history.created}\n"
            f"Actualizados: "
            f"{history.updated}\n"
            f"Sin cambios: "
            f"{history.unchanged}\n"
            f"Errores: "
            f"{history.errors}\n"
            f"Estado: "
            f"{history.status}\n\n"
            f"Mensaje:\n"
            f"{message}"
        )

        QMessageBox.information(
            self,
            "Detalle de actualización",
            details,
        )

    def _set_item(
        self,
        row: int,
        column: int,
        value: str,
        history=None,
    ) -> None:
        item = QTableWidgetItem(
            value,
        )

        item.setTextAlignment(
            Qt.AlignmentFlag.AlignCenter,
        )

        if history is not None:
            item.setData(
                Qt.ItemDataRole.UserRole,
                history,
            )

        self.table.setItem(
            row,
            column,
            item,
        )

    @staticmethod
    def _parse_datetime(
        value,
    ) -> datetime:
        """
        Convierte el valor almacenado en SQLite
        a datetime.
        """

        if isinstance(
            value,
            datetime,
        ):
            return value

        return datetime.fromisoformat(
            str(value),
        )

    @staticmethod
    def _format_datetime(
        value: datetime,
    ) -> str:
        """
        Formatea una fecha para mostrarla en la GUI.
        """

        local_value = value.astimezone()

        return local_value.strftime(
            "%d/%m/%Y %H:%M:%S",
        )

    @staticmethod
    def _format_duration(
        started_at: datetime,
        finished_at: datetime,
    ) -> str:
        """
        Calcula y formatea la duración de la ejecución.
        """

        seconds = int(
            (
                finished_at - started_at
            ).total_seconds(),
        )

        if seconds < 0:
            return "N/D"

        minutes, remaining_seconds = divmod(
            seconds,
            60,
        )

        hours, minutes = divmod(
            minutes,
            60,
        )

        if hours:
            return (
                f"{hours}h "
                f"{minutes}m "
                f"{remaining_seconds}s"
            )

        if minutes:
            return (
                f"{minutes}m "
                f"{remaining_seconds}s"
            )

        return f"{remaining_seconds}s"

    def closeEvent(self, event) -> None:
        """Cierra la conexión SQLite propia del diálogo."""

        try:
            self.db.close()
        finally:
            super().closeEvent(event)
