import json
import sqlite3
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
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
from repositories.scraping.scraping_history_repository import ScrapingHistoryRepository


class ScrapingHistoryDialog(QDialog):
    """Historial de descargas ya aplicadas automáticamente."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.db = DBManager()
        self.repository = ScrapingHistoryRepository(self.db)
        self.detail_dialog: QDialog | None = None
        self.setWindowTitle("Historial de descargas")
        self.resize(1450, 620)
        self._build_ui()
        self.load_history()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Historial de descargas aplicadas")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Aplicado", "Procesados", "Nuevos", "Actualizados", "Sin cambios",
            "Eliminados", "Cobertura", "Errores", "Estado", "Detalle",
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
            QMessageBox.critical(self, "Error", f"No fue posible cargar el historial.\n\n{error}")
            return
        self.table.setRowCount(len(history))
        for row, record in enumerate(history):
            applied_at = self._parse_datetime(record.finished_at)
            self._set_item(row, 0, self._format_datetime(applied_at), record.history_id)
            self._set_item(row, 1, str(record.processed))
            self._set_item(row, 2, str(record.created))
            self._set_item(row, 3, str(record.updated))
            self._set_item(row, 4, str(record.unchanged))
            self._set_item(row, 5, str(record.deleted))
            category_summary = getattr(record, "category_summary", []) or []
            category_lines = "\n".join(
                f"• {item.get('category', '')}: {item.get('products', 0)}"
                for item in category_summary
            ) or "Sin desglose por categoría"
            coverage_text = (
                f"E:{record.products_expected} F:{record.products_found} "
                f"U:{record.products_unique} M:{record.products_multiple_categories} "
                f"D:{record.duplicate_occurrences} C:{len(category_summary)}"
            )
            coverage_item = QTableWidgetItem(coverage_text)
            coverage_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            coverage_item.setToolTip(
                "Esperados / Encontrados / Únicos / Múltiples categorías / "
                "Apariciones duplicadas / Categorías\n\n" + category_lines
            )
            self.table.setItem(row, 6, coverage_item)
            self._set_item(row, 7, str(record.errors))
            self._set_item(row, 8, "APLICADO" if record.status == "SUCCESS" else "ERROR")
            self._set_detail_button(row, record.history_id)
            self.table.setRowHeight(row, 44)
        self.table.resizeColumnsToContents()
        for column, width in {0: 165, 1: 85, 2: 75, 3: 95, 4: 95, 5: 85, 6: 250, 7: 70, 8: 95, 9: 110}.items():
            self.table.setColumnWidth(column, width)

    def _set_detail_button(self, row: int, history_id: int | None) -> None:
        container = QHBoxLayout()
        button = QPushButton("Ver detalle")
        button.setEnabled(history_id is not None)
        button.setProperty("history_id", history_id)
        button.clicked.connect(self.show_row_details)
        container.addWidget(button)
        self.table.setCellWidget(row, 9, self._layout_widget(container))

    @staticmethod
    def _layout_widget(layout: QHBoxLayout) -> QWidget:
        widget = QWidget()
        widget.setLayout(layout)
        return widget

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
        item = self.table.item(row, 0)
        if item is None:
            return
        history_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(history_id, int):
            self._show_history_details(history_id)

    def show_details(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        if item is None:
            return
        history_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(history_id, int):
            self._show_history_details(history_id)

    def _show_history_details(self, history_id: int) -> None:
        history = self.repository.get_by_id(history_id)
        if history is None:
            return
        try:
            changes = self.repository.get_changes(history_id)
        except sqlite3.Error as error:
            QMessageBox.critical(self, "Detalle de descarga", f"No fue posible obtener los cambios.\n\n{error}")
            return
        if self.detail_dialog is not None:
            self.detail_dialog.close()
        dialog = QDialog(self)
        self.detail_dialog = dialog
        dialog.setWindowTitle("Detalle de la descarga")
        dialog.resize(1100, 760)
        dialog.setModal(False)
        dialog.finished.connect(lambda: setattr(self, "detail_dialog", None))
        layout = QVBoxLayout(dialog)
        applied_at = self._parse_datetime(history.finished_at)
        summary = QLabel(
            f"Aplicado: {self._format_datetime(applied_at)}    Procesados: {history.processed}    "
            f"Nuevos: {history.created}    Actualizados: {history.updated}    "
            f"Sin cambios: {history.unchanged}    Eliminados: {history.deleted}"
        )
        summary.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(summary)
        expected_gap = max(history.products_expected - history.products_found, 0)
        coverage = QLabel(
            "COBERTURA DEL SCRAPING    "
            f"Esperados en categorías: {history.products_expected}    |    "
            f"Encontrados: {history.products_found}    |    "
            f"Únicos: {history.products_unique}    |    "
            f"En múltiples categorías: {history.products_multiple_categories}    |    "
            f"Apariciones duplicadas: {history.duplicate_occurrences}    |    "
            f"Brecha: {expected_gap}"
        )
        coverage.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        coverage.setStyleSheet("background:#fff3cd; color:#664d03; border:1px solid #ffda6a; border-radius:5px; padding:8px;")
        layout.addWidget(coverage)

        category_summary = getattr(history, "category_summary", []) or []
        category_table = QTableWidget()
        category_table.setColumnCount(3)
        category_table.setHorizontalHeaderLabels(["Categoría", "Productos", "Productos únicos"])
        category_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        category_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        category_table.setRowCount(len(category_summary))
        for row, item in enumerate(category_summary):
            values = [
                str(item.get("category", "")),
                str(item.get("products", 0)),
                str(item.get("unique_products", 0)),
            ]
            for column, value in enumerate(values):
                category_table.setItem(row, column, QTableWidgetItem(value))
        header = category_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        category_title = QLabel(f"PRODUCTOS POR CATEGORÍA ({len(category_summary)} categorías)")
        category_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(category_title)
        layout.addWidget(category_table)

        multiple = getattr(history, "multiple_category_products", []) or []
        multiple_title = QLabel(f"PRODUCTOS EN MÚLTIPLES CATEGORÍAS ({len(multiple)})")
        multiple_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(multiple_title)
        multiple_table = QTableWidget()
        multiple_table.setColumnCount(3)
        multiple_table.setHorizontalHeaderLabels(["Código", "Producto", "Categorías"])
        multiple_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        multiple_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        multiple_table.setRowCount(len(multiple))
        for row, item in enumerate(multiple):
            values = [
                str(item.get("code", "")),
                str(item.get("name", "")),
                ", ".join(item.get("categories", []) or []),
            ]
            for column, value in enumerate(values):
                multiple_table.setItem(row, column, QTableWidgetItem(value))
        multiple_header = multiple_table.horizontalHeader()
        multiple_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        multiple_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        multiple_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(multiple_table)

        if history.products_found:
            relation = (
                "Relación de cobertura: "
                f"{history.products_found} = {history.products_unique} + "
                f"{history.duplicate_occurrences} apariciones duplicadas"
            )
        else:
            relation = "Sin métricas de cobertura disponibles para este registro."
        relation_label = QLabel(relation)
        relation_label.setStyleSheet("padding: 2px 4px; font-style: italic;")
        layout.addWidget(relation_label)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["Tipo", "Código", "Producto", "Campo", "Anterior", "Nuevo"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setWordWrap(True)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for column in (2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        table.setRowCount(max(len(changes), 1))
        for row, change in enumerate(changes):
            change_type = {"NEW": "NUEVO", "UPDATED": "ACTUALIZADO", "DELETED": "ELIMINADO", "CODE_GENERATED": "CÓDIGO GENERADO", "MISSING_CODE": "SIN CÓDIGO"}.get(change["type"], change["type"])
            values = [change_type, str(change["code"]), str(change["name"]), str(change["label"]), self._format_change_value(change["old"]), self._format_change_value(change["new"])]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if change["type"] in {"CODE_GENERATED", "MISSING_CODE"}:
                    item.setBackground(QColor("#fff3cd"))
                    item.setForeground(QColor("#664d03"))
                    item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                elif change["type"] == "DELETED":
                    item.setBackground(QColor("#f8d7da"))
                    item.setForeground(QColor("#842029"))
                table.setItem(row, column, item)
        if not changes:
            table.setItem(0, 0, QTableWidgetItem("—"))
            table.setItem(0, 3, QTableWidgetItem("Sin cambios registrados"))
        table.resizeRowsToContents()
        layout.addWidget(table)
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    @staticmethod
    def _format_change_value(value) -> str:
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:,.2f}"
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)

    def _set_item(self, row: int, column: int, value: str, history_id=None) -> None:
        item = QTableWidgetItem(value)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if history_id is not None:
            item.setData(Qt.ItemDataRole.UserRole, history_id)
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
