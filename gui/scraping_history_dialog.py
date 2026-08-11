import json
import sqlite3
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QFont
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

    APPLIED_BACKGROUND = "#b2ebf2"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.db = DBManager()
        self.repository = ScrapingHistoryRepository(self.db)
        self.catalog_load_repository = CatalogLoadRepository(self.db)
        self.detail_dialog: QDialog | None = None
        self.setWindowTitle("Historial de actualizaciones")
        self.resize(1250, 560)
        self.build_ui()
        self.load_history()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

    def build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Historial de actualizaciones del catálogo")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Fecha", "Duración", "Procesados", "Nuevos", "Actualizados",
            "Sin cambios", "Errores", "Estado", "Catálogo", "Detalle",
        ])
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
        close_button.clicked.connect(self.close)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def load_history(self) -> None:
        try:
            history = self.repository.get_latest(limit=100)
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
            self._set_item(row, 0, self._format_datetime(started_at), record)
            self._set_item(row, 1, self._format_duration(started_at, finished_at))
            self._set_item(row, 2, str(record.processed))
            self._set_item(row, 3, str(record.created))
            self._set_item(row, 4, str(record.updated))
            self._set_item(row, 5, str(record.unchanged))
            self._set_item(row, 6, str(record.errors))
            self._set_item(row, 7, record.status)
            self._set_catalog_action(row, record.load_id)
            self._set_detail_action(row, record.load_id)
            self.table.setRowHeight(row, 48)

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(7, 100)
        self.table.setColumnWidth(8, 230)
        self.table.setColumnWidth(9, 110)

    def _set_catalog_action(
        self,
        row: int,
        load_id: int | None,
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
            latest_applied = self.catalog_load_repository.get_latest_applied()
        except sqlite3.Error:
            load = None
            latest_applied = None

        if load is None:
            label = QLabel("No disponible")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
        elif load["status"] != "SUCCESS":
            label = QLabel("No aplicable")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
        elif bool(load["applied"]) or load["applied_at"] is not None:
            applied_at = self._parse_datetime(load["applied_at"])
            label = QLabel(
                f"Aplicado\n{self._format_datetime(applied_at)}",
            )
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._style_applied_widget(container, label)
            layout.addWidget(label)
        elif latest_applied is not None and int(load_id) < int(latest_applied["id"]):
            label = QLabel("No Aplicado")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setToolTip("Esta carga fue superada por una aplicación posterior.")
            layout.addWidget(label)
        else:
            button = QPushButton("Aplicar")
            button.setProperty("load_id", int(load_id))
            button.setToolTip(
                "Aplicar únicamente una carga posterior a la última aplicada.",
            )
            button.clicked.connect(self.apply_selected_load)
            layout.addWidget(button)

        self.table.setCellWidget(row, 8, container)

    def _set_detail_action(self, row: int, load_id: int | None) -> None:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        button = QPushButton("Ver detalle")
        button.setProperty("history_row", row)
        button.setEnabled(load_id is not None)
        button.clicked.connect(self.show_row_details)
        layout.addWidget(button)
        self.table.setCellWidget(row, 9, container)

    def _style_applied_widget(self, container: QWidget, label: QLabel) -> None:
        container.setStyleSheet(
            f"background-color: {self.APPLIED_BACKGROUND};"
        )
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
        label.setStyleSheet(
            f"background-color: {self.APPLIED_BACKGROUND};"
            "font-weight: bold;"
        )

    def apply_selected_load(self) -> None:
        button = self.sender()
        if not isinstance(button, QPushButton):
            return
        load_id = button.property("load_id")
        if not isinstance(load_id, int):
            return

        load = self.catalog_load_repository.get_by_id(load_id)
        latest_applied = self.catalog_load_repository.get_latest_applied()
        if load is None:
            QMessageBox.warning(
                self,
                "Aplicar catálogo",
                "La carga seleccionada ya no está disponible.",
            )
            self.load_history()
            return

        if latest_applied is not None and load_id <= int(latest_applied["id"]):
            QMessageBox.information(
                self,
                "Carga superada",
                "Solo se pueden aplicar cargas posteriores a la última carga aplicada.",
            )
            self.load_history()
            return

        response = QMessageBox.question(
            self,
            "Aplicar catálogo",
            (
                f"¿Desea aplicar la carga #{load_id} al catálogo visible?\n\n"
                f"Productos: {int(load['product_count'])}\n\n"
                "Esta carga pasará a ser la versión aplicada del catálogo."
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
                "La carga seleccionada no puede aplicarse porque fue superada.",
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
                "La tabla visible fue actualizada con esta versión."
            ),
        )

    def show_row_details(self) -> None:
        button = self.sender()
        if not isinstance(button, QPushButton):
            return
        row = button.property("history_row")
        if not isinstance(row, int):
            return
        self.show_details(row, 0)

    def show_selected_details(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Historial", "Seleccione una ejecución.")
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
        if self.detail_dialog is not None:
            self.detail_dialog.close()

        dialog = QDialog(self)
        self.detail_dialog = dialog
        dialog.setWindowTitle("Detalle de la descarga")
        dialog.resize(1050, 620)
        dialog.setModal(False)
        dialog.finished.connect(self._detail_dialog_closed)
        layout = QVBoxLayout(dialog)

        summary = QLabel(
            f"Inicio: {self._format_datetime(started_at)}    "
            f"Fin: {self._format_datetime(finished_at)}    "
            f"Duración: {duration}\n"
            f"Procesados: {history.processed}    Nuevos: {history.created}    "
            f"Actualizados: {history.updated}    Sin cambios: {history.unchanged}    "
            f"Errores: {history.errors}",
        )
        summary.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(summary)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Tipo", "Código", "Producto", "Variación", "Anterior", "Nuevo",
        ])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setWordWrap(True)
        for column in (2, 3, 4, 5):
            table.horizontalHeader().setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Stretch,
            )

        row_count = sum(max(len(item["changes"]), 1) for item in variations)
        table.setRowCount(max(row_count, 1))
        row = 0
        for item in variations:
            if item["type"] == "NEW":
                self._set_variation_row(
                    table,
                    row,
                    [
                        "NUEVO",
                        str(item["code"]),
                        str(item["name"]),
                        "Producto nuevo",
                        "—",
                        "Alta",
                    ],
                )
                row += 1
                continue
            for change in item["changes"]:
                self._set_variation_row(
                    table,
                    row,
                    [
                        "ACTUALIZADO",
                        str(item["code"]),
                        str(item["name"]),
                        str(change["label"]),
                        self._format_change_value(change["old"]),
                        self._format_change_value(change["new"]),
                    ],
                )
                row += 1

        if not variations:
            self._set_variation_row(
                table,
                0,
                ["—", "—", "—", "Sin variaciones", "—", "—"],
            )

        table.resizeRowsToContents()
        layout.addWidget(table)
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _detail_dialog_closed(self) -> None:
        self.detail_dialog = None

    @staticmethod
    def _set_variation_row(
        table: QTableWidget,
        row: int,
        values: list[str],
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
            table.setItem(row, column, item)

    @staticmethod
    def _format_change_value(value) -> str:
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:,.2f}"
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)

    @staticmethod
    def _set_item(row: int, column: int, value: str, history=None) -> None:
        item = QTableWidgetItem(value)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if history is not None:
            item.setData(Qt.ItemDataRole.UserRole, history)
        item.setFont(QFont(item.font()))
        ScrapingHistoryDialog._set_table_item(row, column, item)

    def _set_table_item(self, row: int, column: int, item: QTableWidgetItem) -> None:
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
            if self.detail_dialog is not None:
                self.detail_dialog.close()
            self.db.close()
        finally:
            super().closeEvent(event)
