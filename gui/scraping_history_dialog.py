import json
import sqlite3
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
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
from repositories.scraping.scraping_history_repository import ScrapingHistoryRepository


class ScrapingHistoryDialog(QDialog):
    """Historial de descargas aplicadas automáticamente al catálogo."""

    APPLIED_BACKGROUND = "#b2ebf2"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.db = DBManager()
        self.repository = ScrapingHistoryRepository(self.db)
        self.detail_dialog: QDialog | None = None
        self.setWindowTitle("Historial de descargas")
        self.resize(940, 660)
        self._build_ui()
        QTimer.singleShot(0, self.load_history)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._center_on_parent()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(0, self.load_history)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Historial de descargas aplicadas")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Fecha y duración",
                "Procesados",
                "Nuevos",
                "Actualizados",
                "Sin cambios",
                "Eliminados",
                "Estado",
                "Detalle",
            ],
        )
        self.table.verticalHeader().setVisible(False)
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
            history = self.repository.get_all()
        except (sqlite3.Error, TypeError, ValueError, KeyError) as error:
            self.table.setRowCount(1)
            self.table.setItem(
                0,
                0,
                QTableWidgetItem("No se pudo cargar el historial"),
            )
            self.table.setItem(0, 1, QTableWidgetItem(str(error)))
            return

        self.table.setRowCount(len(history))
        for row, record in enumerate(history):
            started_at = self._parse_datetime(record.started_at)
            finished_at = self._parse_datetime(record.finished_at)
            duration = self._format_duration(started_at, finished_at)

            self._set_item(row, 0, str(record.history_id), record.history_id)
            self._set_item(
                row,
                1,
                f"{self._format_datetime(started_at)}\n{duration}",
            )
            self._set_item(row, 2, str(record.processed))
            self._set_item(row, 3, str(record.created))
            self._set_item(row, 4, str(record.updated))
            self._set_item(row, 5, str(record.unchanged))
            self._set_item(row, 6, str(record.deleted))
            self._set_status_item(row, 7, record)
            self._set_detail_button(row, record.history_id)
            self.table.setRowHeight(row, 44)

        self.table.resizeColumnsToContents()
        widths = {
            0: 70,
            1: 255,
            2: 80,
            3: 70,
            4: 95,
            5: 90,
            6: 85,
            7: 85,
            8: 110,
        }
        for column, width in widths.items():
            self.table.setColumnWidth(column, width)
        self._fit_window_to_table()

    @staticmethod
    def _status_text(record) -> str:
        if record.status != "SUCCESS":
            return "ERROR"
        applied_at = ScrapingHistoryDialog._parse_datetime(
            getattr(record, "applied_at", None) or record.finished_at,
        )
        return f"APLICADO\n{ScrapingHistoryDialog._format_datetime(applied_at)}"

    def _set_status_item(self, row: int, column: int, record) -> None:
        item = QTableWidgetItem(self._status_text(record))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setToolTip(
            "La descarga fue aplicada al catálogo."
            if record.status == "SUCCESS"
            else "La descarga terminó con error y no fue aplicada.",
        )
        font = QFont(item.font())
        font.setBold(True)
        item.setFont(font)
        self.table.setItem(row, column, item)

    def _set_detail_button(self, row: int, history_id: int | None) -> None:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        button = QPushButton("Ver detalle")
        button.setEnabled(history_id is not None)
        button.setProperty("history_id", history_id)
        button.clicked.connect(self.show_row_details)
        layout.addWidget(button)
        self.table.setCellWidget(row, 8, container)

    def _fit_window_to_table(self) -> None:
        header = self.table.horizontalHeader()
        table_width = header.length() + self.table.frameWidth() * 2
        if self.table.verticalScrollBar().isVisible():
            table_width += self.table.verticalScrollBar().sizeHint().width()

        layout = self.layout()
        if layout is None:
            return
        margins = layout.contentsMargins()
        width = table_width + margins.left() + margins.right()
        self.resize(max(width, 1), self.height())
        self._center_on_parent()

    def _center_on_parent(self) -> None:
        parent = self.parentWidget()
        if isinstance(parent, QWidget) and parent.isWindow():
            center = parent.frameGeometry().center()
        else:
            screen = self.screen() or QApplication.primaryScreen()
            if screen is None:
                return
            center = screen.availableGeometry().center()
        frame = self.frameGeometry()
        frame.moveCenter(center)
        self.move(frame.topLeft())

    def show_row_details(self) -> None:
        button = self.sender()
        if not isinstance(button, QPushButton):
            return
        history_id = button.property("history_id")
        if isinstance(history_id, int):
            self._show_history_details(history_id)

    def show_selected_details(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Historial", "Seleccione una descarga.")
            return
        self.show_details(row, 0)

    def show_details(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        if item is None:
            return
        history_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(history_id, int):
            self._show_history_details(history_id)

    def _show_history_details(self, history_id: int) -> None:
        try:
            history = self.repository.get_by_id(history_id)
            if history is None:
                QMessageBox.warning(
                    self,
                    "Detalle de descarga",
                    f"No existe el registro de historial #{history_id}.",
                )
                return
            changes = self.repository.get_changes(history_id)
        except (sqlite3.Error, TypeError, ValueError, KeyError) as error:
            QMessageBox.critical(
                self,
                "Detalle de descarga",
                f"No fue posible obtener el detalle.\n\n{error}",
            )
            return

        if self.detail_dialog is not None:
            self.detail_dialog.close()

        dialog = QDialog(self)
        self.detail_dialog = dialog
        dialog.setWindowTitle("Detalle de la descarga")
        dialog.resize(1200, 800)
        dialog.setModal(False)
        dialog.finished.connect(self._detail_dialog_closed)
        layout = QVBoxLayout(dialog)

        started_at = self._parse_datetime(history.started_at)
        finished_at = self._parse_datetime(history.finished_at)
        duration = self._format_duration(started_at, finished_at)
        application_text = (
            self._format_datetime(self._parse_datetime(history.applied_at))
            if history.applied_at is not None
            else "No aplicada"
        )

        summary = QLabel(
            f"ID: {history.history_id}    "
            f"Inicio: {self._format_datetime(started_at)}    "
            f"Fin: {self._format_datetime(finished_at)}    "
            f"Aplicación: {application_text}    "
            f"Duración: {duration}\n"
            f"Procesados: {history.processed}    Nuevos: {history.created}    "
            f"Actualizados: {history.updated}    Sin cambios: {history.unchanged}    "
            f"Eliminados: {history.deleted}    Errores: {history.errors}",
        )
        summary.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(summary)

        expected_gap = max(history.products_expected - history.products_found, 0)
        coverage = QLabel(
            "COBERTURA DEL SCRAPING    "
            f"Categorías: {history.categories_processed}    |    "
            f"Esperados: {history.products_expected}    |    "
            f"Encontrados: {history.products_found}    |    "
            f"Únicos: {history.products_unique}    |    "
            f"Múltiples categorías: {history.products_multiple_categories}    |    "
            f"Apariciones duplicadas: {history.duplicate_occurrences}    |    "
            f"Brecha: {expected_gap}",
        )
        coverage.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        coverage.setStyleSheet(
            "background:#fff3cd; color:#664d03; border:1px solid #ffda6a; "
            "border-radius:5px; padding:8px;"
        )
        layout.addWidget(coverage)

        category_summary = getattr(history, "category_summary", []) or []
        valid_categories = [
            item for item in category_summary if isinstance(item, dict)
        ]
        category_title = QLabel(
            f"PRODUCTOS POR CATEGORÍA ({len(valid_categories)} categorías)",
        )
        category_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(category_title)

        category_table = QTableWidget()
        category_table.setColumnCount(3)
        category_table.setHorizontalHeaderLabels(
            ["Categoría", "Productos", "Productos únicos"],
        )
        category_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        category_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        category_table.setRowCount(len(valid_categories))
        for row, item in enumerate(valid_categories):
            values = [
                str(item.get("category", "")),
                str(item.get("products", 0)),
                str(item.get("unique_products", 0)),
            ]
            for column, value in enumerate(values):
                category_table.setItem(row, column, QTableWidgetItem(value))
        category_header = category_table.horizontalHeader()
        category_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        category_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        category_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(category_table)

        multiple = getattr(history, "multiple_category_products", []) or []
        valid_multiple = [item for item in multiple if isinstance(item, dict)]
        multiple_title = QLabel(
            f"PRODUCTOS EN MÚLTIPLES CATEGORÍAS ({len(valid_multiple)})",
        )
        multiple_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(multiple_title)

        multiple_table = QTableWidget()
        multiple_table.setColumnCount(3)
        multiple_table.setHorizontalHeaderLabels(
            ["Código", "Producto", "Categorías"],
        )
        multiple_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        multiple_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        multiple_table.setRowCount(len(valid_multiple))
        for row, item in enumerate(valid_multiple):
            categories = item.get("categories", []) or []
            values = [
                str(item.get("code", "")),
                str(item.get("name", "")),
                ", ".join(str(category) for category in categories),
            ]
            for column, value in enumerate(values):
                multiple_table.setItem(row, column, QTableWidgetItem(value))
        multiple_header = multiple_table.horizontalHeader()
        multiple_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        multiple_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        multiple_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(multiple_table)

        relation = (
            "Relación de cobertura: "
            f"{history.products_found} = {history.products_unique} + "
            f"{history.duplicate_occurrences} apariciones duplicadas"
            if history.products_found
            else "Sin métricas de cobertura disponibles para este registro."
        )
        relation_label = QLabel(relation)
        relation_label.setStyleSheet("padding: 2px 4px; font-style: italic;")
        layout.addWidget(relation_label)

        changes_title = QLabel(f"CAMBIOS DETECTADOS ({len(changes)})")
        changes_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(changes_title)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["Tipo", "Código", "Producto", "Campo", "Anterior", "Nuevo"],
        )
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setWordWrap(True)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for column in (2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)

        table.setRowCount(max(len(changes), 1))
        if changes:
            for row, change in enumerate(changes):
                values = [
                    str(change.get("type", "")),
                    str(change.get("code", "")),
                    str(change.get("name", "")),
                    str(change.get("label", change.get("field", ""))),
                    self._display_value(change.get("old")),
                    self._display_value(change.get("new")),
                ]
                for column, value in enumerate(values):
                    table.setItem(row, column, QTableWidgetItem(value))
        else:
            table.setItem(
                0,
                0,
                QTableWidgetItem("Sin cambios de campos registrados"),
            )
        layout.addWidget(table)

        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(dialog.close)
        close_layout.addWidget(close_button)
        layout.addLayout(close_layout)

        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _detail_dialog_closed(self) -> None:
        self.detail_dialog = None

    @staticmethod
    def _display_value(value) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        if value is None:
            return "—"
        return str(value)

    def _set_item(self, row: int, column: int, text: str, user_data=None) -> None:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if user_data is not None:
            item.setData(Qt.ItemDataRole.UserRole, user_data)
        item.setToolTip(text)
        self._set_table_item(row, column, item)

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
