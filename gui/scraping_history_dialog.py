from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from database.db_manager import DBManager
from repositories.scraping.scraping_history_repository import ScrapingHistoryRepository


class ScrapingHistoryDialog(QDialog):
    """Historial de descargas: solo productos nuevos y cambios detectados."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.db = DBManager()
        self.repository = ScrapingHistoryRepository(self.db)
        self.setWindowTitle("Historial de descargas")
        self.resize(1150, 650)
        self._build_ui()
        self.load_history()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Historial de descargas del catálogo")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "Fecha y hora",
                "Procesados",
                "Nuevos",
                "Actualizados",
                "Errores",
                "Estado",
            ],
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.show_details)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        refresh = QPushButton("Actualizar")
        refresh.clicked.connect(self.load_history)
        layout.addWidget(refresh)

    def load_history(self) -> None:
        try:
            history = self.repository.get_latest(100)
        except (RuntimeError, ValueError) as error:
            message = f"No fue posible cargar el historial.\n\n{error}"
            QMessageBox.critical(self, "Historial", message)
            return

        self.table.setRowCount(len(history))
        for row, record in enumerate(history):
            self._set_item(
                row,
                0,
                self._format_datetime(record.started_at),
                record.history_id,
            )
            self._set_item(row, 1, str(record.processed))
            self._set_item(row, 2, str(record.created))
            self._set_item(row, 3, str(record.updated))
            self._set_item(row, 4, str(record.errors))
            self._set_status(row, record.status)
            self.table.setRowHeight(row, 40)

    def _set_status(self, row: int, status: str) -> None:
        item = QTableWidgetItem("Completada" if status == "SUCCESS" else "Con errores")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont(item.font())
        font.setBold(True)
        item.setFont(font)
        self.table.setItem(row, 5, item)

    def show_details(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        if item is None:
            return
        history_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(history_id, int):
            return

        try:
            changes = self.repository.get_changes(history_id)
        except (RuntimeError, ValueError) as error:
            message = f"No fue posible obtener los cambios.\n\n{error}"
            QMessageBox.critical(self, "Detalle", message)
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Detalle de cambios")
        dialog.resize(1100, 620)
        layout = QVBoxLayout(dialog)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["Tipo", "Código", "Producto", "Campo", "Anterior", "Nuevo"],
        )
        table.setRowCount(len(changes))
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for row_index, change in enumerate(changes):
            values = (
                "NUEVO" if change["type"] == "NEW" else "ACTUALIZADO",
                change["code"],
                change["name"],
                change["label"] or "Producto nuevo",
                self._format_value(change["old"]),
                self._format_value(change["new"]),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                alignment = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                item.setTextAlignment(alignment)
                if column == 0:
                    font = QFont(item.font())
                    font.setBold(True)
                    item.setFont(font)
                table.setItem(row_index, column, item)

        if not changes:
            table.setRowCount(1)
            table.setItem(0, 0, QTableWidgetItem("SIN CAMBIOS"))
            table.setSpan(0, 0, 1, 6)

        table.resizeRowsToContents()
        layout.addWidget(table)
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        dialog.exec()

    def _set_item(self, row: int, column: int, value: str, user_data=None) -> None:
        item = QTableWidgetItem(value)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if user_data is not None:
            item.setData(Qt.ItemDataRole.UserRole, user_data)
        self.table.setItem(row, column, item)

    @staticmethod
    def _format_value(value) -> str:
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:.2f}"
        if isinstance(value, (dict, list)):
            import json

            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        return value.astimezone().strftime("%d/%m/%Y %H:%M:%S")

    def closeEvent(self, event) -> None:
        self.db.close()
        super().closeEvent(event)
