import sqlite3
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.db_manager import DBManager
from repositories.scraping.catalog_load_repository import CatalogLoadRepository
from repositories.scraping.scraping_history_repository import ScrapingHistoryRepository


class ScrapingHistoryDialog(QDialog):
    """Ventana que muestra el historial de ejecuciones de actualización."""

    catalog_applied = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.db = DBManager()
        self.repository = ScrapingHistoryRepository(self.db)
        self.catalog_load_repository = CatalogLoadRepository(self.db)

        self.setWindowTitle("Historial de actualizaciones")
        self.resize(1100, 500)
        self.build_ui()
        self.load_history()

    def build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Historial de actualizaciones del catálogo")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
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
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.show_details)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()

        refresh_button = QPushButton("Actualizar")
        refresh_button.clicked.connect(self.load_history)
        buttons.addWidget(refresh_button)

        details_button = QPushButton("Ver detalle")
        details_button.clicked.connect(self.show_selected_details)
        buttons.addWidget(details_button)

        buttons.addStretch()

        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)

        layout.addLayout(buttons)

    def load_history(self) -> None:
        try:
            self.catalog_load_repository.cleanup_expired_history()
            history = self.repository.get_latest(limit=100)
            latest_applied = self.catalog_load_repository.get_latest_applied()
            latest_applied_id = (
                int(latest_applied["id"])
                if latest_applied is not None
                else None
            )
        except sqlite3.Error as error:
            QMessageBox.critical(
                self,
                "Error",
                f"No fue posible cargar el historial.\n\n{error}",
            )
            return

        self.table.setRowCount(len(history))

        for row, record in enumerate(history):
            started_at = self._parse_datetime(record.started_at)
            finished_at = self._parse_datetime(record.finished_at)

            self._set_item(
                row,
                0,
                self._format_datetime(started_at),
                record,
            )
            self._set_item(
                row,
                1,
                self._format_duration(started_at, finished_at),
            )
            self._set_item(row, 2, str(record.processed))
            self._set_item(row, 3, str(record.created))
            self._set_item(row, 4, str(record.updated))
            self._set_item(row, 5, str(record.unchanged))
            self._set_item(row, 6, str(record.errors))
            self._set_item(row, 7, record.status)
            self._set_catalog_action(row, record.load_id, latest_applied_id)
            self.table.setRowHeight(row, 48)

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(7, 100)
        self.table.setColumnWidth(8, 190)

    def _set_catalog_action(
        self,
        row: int,
        load_id: int | None,
        latest_applied_id: int | None,
    ) -> None:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)

        if load_id is None:
            label = QLabel("Sin carga")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            self.table.setCellWidget(row, 8, container)
            return

        try:
            load = self.catalog_load_repository.get_by_id(int(load_id))
        except sqlite3.Error:
            load = None

        if load is None:
            label = QLabel("No disponible")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
        elif load["applied_at"] is not None:
            applied_datetime = self._parse_datetime(load["applied_at"])
            label = QLabel(
                "Aplicado\n"
                f"{self._format_datetime(applied_datetime)}",
            )
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-weight: bold; color: #00838f;")
            layout.addWidget(label)
        elif latest_applied_id is None or int(load_id) > latest_applied_id:
            if load["status"] == "SUCCESS":
                button = QPushButton("Aplicar")
                button.setProperty("load_id", int(load_id))
                button.clicked.connect(self.apply_selected_load)
                layout.addWidget(button)
            else:
                label = QLabel("No aplicable")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(label)
        else:
            label = QLabel("No aplicado")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color: #757575;")
            layout.addWidget(label)

        self.table.setCellWidget(row, 8, container)

    def apply_selected_load(self) -> None:
        button = self.sender()
        if not isinstance(button, QPushButton):
            return

        load_id = button.property("load_id")
        if not isinstance(load_id, int):
            return

        load = self.catalog_load_repository.get_by_id(load_id)
        if load is None:
            QMessageBox.warning(
                self,
                "Aplicar catálogo",
                "La carga seleccionada ya no está disponible.",
            )
            self.load_history()
            return

        product_count = int(load["product_count"])
        response = QMessageBox.question(
            self,
            "Aplicar catálogo",
            (
                f"¿Desea aplicar la carga #{load_id} al catálogo visible?\n\n"
                f"Productos: {product_count}\n\n"
                "Esta aplicación quedará registrada permanentemente "
                "en el historial."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if response != QMessageBox.StandardButton.Yes:
            return

        try:
            applied = self.catalog_load_repository.apply(load_id)
        except sqlite3.Error as error:
            QMessageBox.critical(
                self,
                "Error",
                f"No fue posible aplicar la carga.\n\n{error}",
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
        self.catalog_applied.emit(load_id)

        QMessageBox.information(
            self,
            "Catálogo actualizado",
            (
                f"La carga #{load_id} fue aplicada correctamente.\n\n"
                "La fecha de aplicación quedó registrada en el historial."
            ),
        )

    def show_selected_details(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(
                self,
                "Historial",
                "Seleccione una ejecución.",
            )
            return
        self.show_details(row, 0)

    def show_details(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        if item is None:
            return

        history = item.data(Qt.ItemDataRole.UserRole)
        if history is None:
            return

        started_at = self._parse_datetime(history.started_at)
        finished_at = self._parse_datetime(history.finished_at)
        duration = self._format_duration(started_at, finished_at)

        if history.load_id is not None:
            try:
                variations = self.catalog_load_repository.get_load_changes(
                    int(history.load_id),
                )
            except sqlite3.Error as error:
                QMessageBox.critical(
                    self,
                    "Detalle de actualización",
                    f"No fue posible obtener las variaciones.\n\n{error}",
                )
                return
            self._show_variation_dialog(
                history,
                started_at,
                finished_at,
                duration,
                variations,
            )
            return

        message = history.message.strip() or "Sin mensaje adicional."
        QMessageBox.information(
            self,
            "Detalle de actualización",
            (
                f"Fecha de inicio:\n{self._format_datetime(started_at)}\n\n"
                f"Fecha de finalización:\n{self._format_datetime(finished_at)}\n\n"
                f"Duración:\n{duration}\n\n"
                f"Productos procesados: {history.processed}\n"
                f"Nuevos: {history.created}\n"
                f"Actualizados: {history.updated}\n"
                f"Sin cambios: {history.unchanged}\n"
                f"Errores: {history.errors}\n"
                f"Estado: {history.status}\n\n"
                f"Mensaje:\n{message}"
            ),
        )

    def _show_variation_dialog(
        self,
        history,
        started_at: datetime,
        finished_at: datetime,
        duration: str,
        variations: list[dict],
    ) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Detalle de actualización")
        dialog.resize(1050, 620)

        layout = QVBoxLayout(dialog)

        summary = QLabel(
            f"Inicio: {self._format_datetime(started_at)}    "
            f"Fin: {self._format_datetime(finished_at)}    "
            f"Duración: {duration}\n"
            f"Procesados: {history.processed}    "
            f"Nuevos: {history.created}    "
            f"Actualizados: {history.updated}    "
            f"Sin cambios: {history.unchanged}    "
            f"Errores: {history.errors}",
        )
        summary.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(summary)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["Tipo", "Código", "Producto", "Variación", "Anterior", "Nuevo"],
        )
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setWordWrap(True)
        table.horizontalHeader().setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        table.horizontalHeader().setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        table.horizontalHeader().setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )
        table.horizontalHeader().setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.Stretch,
        )

        row_count = sum(
            max(len(item["changes"]), 1)
            for item in variations
        )
        table.setRowCount(row_count)

        row = 0
        for item in variations:
            if item["type"] == "NEW":
                values = [
                    "NUEVO",
                    str(item["code"]),
                    str(item["name"]),
                    "Producto nuevo",
                    "—",
                    "Alta",
                ]
                self._set_variation_row(table, row, values, True)
                row += 1
                continue

            for change in item["changes"]:
                values = [
                    "ACTUALIZADO",
                    str(item["code"]),
                    str(item["name"]),
                    str(change["label"]),
                    self._format_change_value(change["old"]),
                    self._format_change_value(change["new"]),
                ]
                self._set_variation_row(table, row, values, True)
                row += 1

        if not variations:
            table.setRowCount(1)
            self._set_variation_row(
                table,
                0,
                ["—", "—", "—", "Sin variaciones", "—", "—"],
                False,
            )

        table.resizeRowsToContents()
        layout.addWidget(table)

        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.exec()

    @staticmethod
    def _set_variation_row(
        table: QTableWidget,
        row: int,
        values: list[str],
        highlight: bool,
    ) -> None:
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter
                | (
                    Qt.AlignmentFlag.AlignCenter
                    if column != 2
                    else Qt.AlignmentFlag.AlignLeft
                ),
            )
            if highlight:
                font = QFont(item.font())
                font.setBold(column in {0, 3})
                item.setFont(font)
                item.setBackground(
                    table.palette().alternateBase()
                    if column not in {3, 4, 5}
                    else table.palette().highlight(),
                )
            table.setItem(row, column, item)

    @staticmethod
    def _format_change_value(value) -> str:
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:,.2f}"
        return str(value)

    def _set_item(
        self,
        row: int,
        column: int,
        value: str,
        history=None,
    ) -> None:
        item = QTableWidgetItem(value)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if history is not None:
            item.setData(Qt.ItemDataRole.UserRole, history)
        self.table.setItem(row, column, item)

    @staticmethod
    def _parse_datetime(value) -> datetime:
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value))

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        return value.astimezone().strftime("%d/%m/%Y %H:%M:%S")

    @staticmethod
    def _format_duration(started_at: datetime, finished_at: datetime) -> str:
        seconds = int((finished_at - started_at).total_seconds())
        if seconds < 0:
            return "N/D"

        minutes, remaining_seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours:
            return f"{hours}h {minutes}m {remaining_seconds}s"
        if minutes:
            return f"{minutes}m {remaining_seconds}s"
        return f"{remaining_seconds}s"

    def closeEvent(self, event) -> None:
        try:
            self.db.close()
        finally:
            super().closeEvent(event)
