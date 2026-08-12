import json
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
    """Historial de descargas y versiones del catálogo."""

    catalog_applied = Signal(int)
    APPLY_BACKGROUND = "#b2ebf2"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.db = DBManager()
        self.repository = ScrapingHistoryRepository(self.db)
        self.catalog_load_repository = CatalogLoadRepository(self.db)
        self.detail_dialog: QDialog | None = None
        self.setWindowTitle("Historial de descargas")
        self.resize(1200, 600)
        self._build_ui()
        self.load_history()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Historial de descargas del catálogo")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            [
                "Fecha de descarga",
                "Productos",
                "Nuevos",
                "Actualizados",
                "Sin cambios",
                "Errores",
                "Estado",
                "Detalle",
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
        detail_button = QPushButton("Ver detalle")
        detail_button.clicked.connect(self.show_selected_details)
        buttons.addWidget(detail_button)
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
            self._set_item(row, 0, self._format_datetime(started_at), record)
            self._set_item(row, 1, str(record.processed))
            self._set_item(row, 2, str(record.created))
            self._set_item(row, 3, str(record.updated))
            self._set_item(row, 4, str(record.unchanged))
            self._set_item(row, 5, str(record.errors))
            self._set_status(row, record.load_id)
            self._set_detail_button(row, record.load_id)
            self.table.setRowHeight(row, 44)

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 165)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(5, 70)
        self.table.setColumnWidth(6, 250)
        self.table.setColumnWidth(7, 110)

    def _set_status(self, row: int, load_id: int | None) -> None:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)

        action = "NO_APLICADO"
        applied_at: datetime | None = None
        if load_id is not None:
            try:
                action, timestamp = self.catalog_load_repository.get_catalog_action(
                    int(load_id),
                )
                if timestamp:
                    applied_at = self._parse_datetime(timestamp)
            except sqlite3.Error:
                action = "NO_APLICADO"

        if action == "APLICAR":
            assert load_id is not None
            button = QPushButton("Aplicar")
            button.setProperty("load_id", int(load_id))
            button.setStyleSheet(
                f"QPushButton {{ background-color: {self.APPLY_BACKGROUND}; "
                "font-weight: bold; padding: 6px 18px; }"
            )
            button.setToolTip("Aplicar manualmente esta descarga al catálogo.")
            button.clicked.connect(self.apply_selected_load)
            layout.addWidget(button)
        else:
            if action == "APLICADO" and applied_at is not None:
                text = f"Aplicada — {self._format_datetime(applied_at)}"
            elif action == "APLICADO":
                text = "Aplicada"
            else:
                text = "No aplicada"

            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            font = QFont(label.font())
            font.setBold(True)
            label.setFont(font)
            layout.addWidget(label)

        self.table.setCellWidget(row, 6, container)

    def _set_detail_button(self, row: int, load_id: int | None) -> None:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        button = QPushButton("Ver detalle")
        button.setEnabled(load_id is not None)
        button.setProperty("history_row", row)
        button.clicked.connect(self.show_row_details)
        layout.addWidget(button)
        self.table.setCellWidget(row, 7, container)

    def apply_selected_load(self) -> None:
        button = self.sender()
        load_id = button.property("load_id") if isinstance(button, QPushButton) else None
        if not isinstance(load_id, int):
            return

        try:
            load = self.catalog_load_repository.get_by_id(load_id)
            action, _ = self.catalog_load_repository.get_catalog_action(load_id)
        except sqlite3.Error as error:
            QMessageBox.critical(
                self,
                "Error",
                f"No fue posible consultar la descarga.\n\n{error}",
            )
            return

        if load is None or action != "APLICAR":
            QMessageBox.information(
                self,
                "Descarga no aplicable",
                "La descarga seleccionada ya no puede aplicarse.",
            )
            self.load_history()
            return

        response = QMessageBox.question(
            self,
            "Aplicar catálogo",
            (
                f"¿Desea aplicar la descarga #{load_id} al catálogo?\n\n"
                f"Productos: {int(load['product_count'])}\n\n"
                "La aplicación será manual y quedará registrada con fecha y hora."
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
                f"No fue posible aplicar la descarga.\n\n{error}",
            )
            return

        if not applied:
            QMessageBox.warning(
                self,
                "Descarga no aplicable",
                "La descarga seleccionada ya no puede aplicarse.",
            )
            self.load_history()
            return

        self.load_history()
        self.catalog_applied.emit(load_id)

    def show_row_details(self) -> None:
        button = self.sender()
        if not isinstance(button, QPushButton):
            return
        row = button.property("history_row")
        if isinstance(row, int):
            self.show_details(row, 0)

    def show_selected_details(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.show_details(row, 0)
        else:
            QMessageBox.information(self, "Historial", "Seleccione una descarga.")

    def show_details(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        if item is None:
            return
        history = item.data(Qt.ItemDataRole.UserRole)
        if history is None or history.load_id is None:
            return

        try:
            variations = self.catalog_load_repository.get_load_changes(
                int(history.load_id),
            )
        except sqlite3.Error as error:
            QMessageBox.critical(
                self,
                "Detalle de descarga",
                f"No fue posible obtener las variaciones.\n\n{error}",
            )
            return

        self._show_variation_dialog(history, variations)

    def _show_variation_dialog(self, history, variations: list[dict]) -> None:
        if self.detail_dialog is not None:
            self.detail_dialog.close()

        dialog = QDialog(self)
        self.detail_dialog = dialog
        dialog.setWindowTitle("Detalle de la descarga")
        dialog.resize(1050, 620)
        dialog.setModal(False)
        dialog.finished.connect(self._detail_dialog_closed)
        layout = QVBoxLayout(dialog)

        started_at = self._parse_datetime(history.started_at)
        summary = QLabel(
            f"Descarga: {self._format_datetime(started_at)}    "
            f"Productos: {history.processed}    Nuevos: {history.created}    "
            f"Actualizados: {history.updated}    Sin cambios: {history.unchanged}    "
            f"Errores: {history.errors}",
        )
        summary.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(summary)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["Tipo", "Código", "Producto", "Variación", "Anterior", "Posterior"],
        )
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setWordWrap(True)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for column in (2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)

        row_count = sum(max(len(item["changes"]), 1) for item in variations)
        table.setRowCount(max(row_count, 1))
        current_row = 0
        for item in variations:
            if item["type"] == "NEW":
                self._set_variation_row(
                    table,
                    current_row,
                    [
                        "NUEVO",
                        str(item["code"]),
                        str(item["name"]),
                        "Producto nuevo",
                        "—",
                        "Alta",
                    ],
                )
                current_row += 1
                continue

            for change in item["changes"]:
                self._set_variation_row(
                    table,
                    current_row,
                    [
                        "ACTUALIZADO",
                        str(item["code"]),
                        str(item["name"]),
                        str(change["label"]),
                        self._format_change_value(change["old"]),
                        self._format_change_value(change["new"]),
                    ],
                )
                current_row += 1

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
    def _set_variation_row(table: QTableWidget, row: int, values: list[str]) -> None:
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter
                | (
                    Qt.AlignmentFlag.AlignLeft
                    if column == 2
                    else Qt.AlignmentFlag.AlignCenter
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

    def _set_item(self, row: int, column: int, value: str, history=None) -> None:
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

    def closeEvent(self, event) -> None:
        if self.detail_dialog is not None:
            self.detail_dialog.close()
        self.db.close()
        super().closeEvent(event)
