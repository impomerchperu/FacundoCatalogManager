import json
import re
import sqlite3
from datetime import datetime
from html import escape
from math import ceil
from typing import Callable, ClassVar

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QResizeEvent, QTextDocument
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.db_manager import DBManager
from repositories.scraping.scraping_history_repository import ScrapingHistoryRepository


class _HistoryDetailDialog(QDialog):
    """Dialog secundario con reajuste de sus tablas al redimensionar."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._resize_handler: Callable[[], None] | None = None
        self._resize_timer_active = False

    def set_resize_handler(self, handler: Callable[[], None]) -> None:
        self._resize_handler = handler

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._resize_handler is None or self._resize_timer_active:
            return
        self._resize_timer_active = True
        QTimer.singleShot(0, self._run_resize_handler)

    def _run_resize_handler(self) -> None:
        self._resize_timer_active = False
        if self._resize_handler is not None and self.isVisible():
            self._resize_handler()


class ScrapingHistoryDialog(QDialog):
    """Historial de descargas y versiones del catálogo."""

    FONT_FAMILY = "Segoe UI"
    TEXT_COLOR = "#173f6d"
    BODY_FONT_SIZE = 13
    TITLE_FONT_SIZE = 16
    BUTTON_HEIGHT = 34
    APPLIED_BACKGROUND = "#b2ebf2"
    CONTENT_SIDE_PADDING = 4
    DETAIL_CHANGE_VALUE_VERTICAL_PADDING = 8
    DETAIL_CHANGE_ROW_HEIGHT_BUFFER = 2
    DETAIL_CHANGE_SELECTION_FRAME_VERTICAL_CLEARANCE = 4
    DETAIL_CHANGE_DIALOG_WIDTH = 1100
    DETAIL_CHANGE_MIN_DIALOG_WIDTH = 820
    DETAIL_CHANGE_FIXED_COLUMN_WIDTHS: ClassVar[dict[int, int]] = {
        0: 100,
        1: 110,
        3: 150,
    }
    DETAIL_CHANGE_PRODUCT_MAX_LINES = 2
    DETAIL_CHANGE_PRODUCT_MIN_WIDTH = 220
    DETAIL_CHANGE_PRODUCT_MAX_WIDTH = 300
    DETAIL_CHANGE_VALUE_MIN_WIDTH = 180
    DETAIL_CHANGE_VALUE_MAX_WIDTH = 300
    DETAIL_CHANGE_TABLE_TARGET_WIDTH = 1040
    DETAIL_DETAIL_MARGIN = 32
    DETAIL_DETAIL_MIN_HEIGHT = 600
    CHANGE_TYPE_LABELS: ClassVar[dict[str, str]] = {
        "UPDATED": "ACTUALIZADO",
        "NEW": "NUEVO",
        "DELETED": "ELIMINADO",
        "CODE_GENERATED": "CÓDIGO GENERADO",
    }
    DELTA_INCREASE_COLOR = "#188038"
    DELTA_DECREASE_COLOR = "#d93025"
    PRICE_FIELD_LABELS: ClassVar[dict[str, str]] = {
        "price": "precio",
        "price_sample": "muestra",
        "price_hundred": "ciento",
        "price_thousand": "millar",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.db = DBManager()
        self.repository = ScrapingHistoryRepository(self.db)
        self.detail_dialog: QDialog | None = None
        self._is_fitting_columns = False
        self._initial_fit_timer = QTimer(self)
        self._initial_fit_timer.setSingleShot(True)
        self._initial_fit_timer.timeout.connect(self._fit_table_to_content)
        self.setWindowTitle("Historial de descargas")
        self.resize(940, 660)
        self._build_ui()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._center_on_parent()
        self.raise_()
        self.activateWindow()
        self.load_history()
        # El primer cálculo puede ocurrir antes de que Qt termine de activar
        # el layout de la tabla; repetirlo con un QTimer propio garantiza que
        # la ventana quede dimensionada con las geometrías finales al abrirse.
        self._initial_fit_timer.start(0)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        self.setStyleSheet(
            "QDialog {"
            f' font-family: "{self.FONT_FAMILY}";'
            f" color: {self.TEXT_COLOR};"
            "}"
            " QLabel {"
            f' font-family: "{self.FONT_FAMILY}";'
            f" font-size: {self.BODY_FONT_SIZE}px;"
            f" color: {self.TEXT_COLOR};"
            "}"
            " QTableWidget {"
            " background-color: #fbfdff;"
            " gridline-color: #dce7f1;"
            f" color: {self.TEXT_COLOR};"
            " selection-background-color: #fbfdff;"
            f" selection-color: {self.TEXT_COLOR};"
            "}"
            " QTableWidget::item {"
            " padding: 4px;"
            f' font-family: "{self.FONT_FAMILY}";'
            f" font-size: {self.BODY_FONT_SIZE}px;"
            "}"
            " QTableWidget::item:selected {"
            " background-color: #fbfdff;"
            f" color: {self.TEXT_COLOR};"
            "}"
            " QHeaderView::section {"
            " padding: 4px;"
            f' font-family: "{self.FONT_FAMILY}";'
            f" font-size: {self.BODY_FONT_SIZE}px;"
            " font-weight: bold;"
            " background-color: #eef5fb;"
            f" color: {self.TEXT_COLOR};"
            "}"
            " QPushButton {"
            f' font-family: "{self.FONT_FAMILY}";'
            f" font-size: {self.BODY_FONT_SIZE}px;"
            f" color: {self.TEXT_COLOR};"
            " background-color: #fbfdff;"
            " border: 1px solid #cbddea;"
            " border-radius: 4px;"
            " padding: 0px 10px;"
            f" min-height: {self.BUTTON_HEIGHT}px;"
            f" max-height: {self.BUTTON_HEIGHT}px;"
            "}"
            " QPushButton:hover { background-color: #eef5fb; }"
            " QPushButton:pressed { background-color: #dbeeff; }"
        )
        title = QLabel("Historial de descargas y versiones del catálogo")
        title_font = QFont(self.FONT_FAMILY)
        title_font.setPixelSize(self.TITLE_FONT_SIZE)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Fecha de descarga",
                "Duración",
                "Procesados",
                "Nuevos",
                "Actualizados",
                "Sin cambios",
                "Eliminados",
                "Estado",
                "Detalle",
            ],
        )
        self.table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.table.cellDoubleClicked.connect(self.show_details)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for column in range(self.table.columnCount()):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Interactive,
            )

        side_padding = self.CONTENT_SIDE_PADDING
        self.table.setStyleSheet(
            f"QHeaderView::section {{ padding-left: {side_padding}px; "
            f"padding-right: {side_padding}px; }}"
            f"QTableWidget::item {{ padding-left: {side_padding}px; "
            f"padding-right: {side_padding}px; }}"
        )

        layout.addWidget(self.table)

    def load_history(self) -> None:
        if not self.isVisible():
            return
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
            self._set_item(row, 1, self._format_datetime(started_at))
            self._set_item(row, 2, duration)
            self._set_item(row, 3, str(record.processed))
            self._set_item(row, 4, str(record.created))
            self._set_item(row, 5, str(record.updated))
            self._set_item(row, 6, str(record.unchanged))
            self._set_item(row, 7, str(record.deleted))
            self._set_status_item(row, 8, record)
            self._set_detail_button(row, record.history_id)
            self.table.setRowHeight(row, 48)

        self._fit_table_to_content()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, "table") and not self._is_fitting_columns:
            self._fit_table_to_content(expand_window=False)

    def _fit_table_to_content(self, *, expand_window: bool = True) -> None:
        if self._is_fitting_columns:
            return

        layout = self.layout()
        if layout is None:
            return

        header = self.table.horizontalHeader()
        self._is_fitting_columns = True
        try:
            self._prepare_column_resize_modes(header)
            minimum_widths = self._calculate_minimum_column_widths(header)
            content_width = sum(minimum_widths)
            required_width = self._calculate_required_window_width(
                content_width,
                layout.contentsMargins(),
            )
            self.setMinimumWidth(required_width)
            if expand_window:
                self.resize(required_width, self.height())

            available_width = max(self.table.viewport().width(), content_width)
            widths = self._distribute_extra_width(minimum_widths, available_width)
            for column, width in enumerate(widths):
                header.resizeSection(column, width)
        finally:
            self._is_fitting_columns = False

    def _prepare_column_resize_modes(self, header: QHeaderView) -> None:
        for column in range(self.table.columnCount()):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Interactive,
            )
        self.table.resizeColumnsToContents()

    def _calculate_minimum_column_widths(
        self,
        header: QHeaderView,
    ) -> list[int]:
        padding = 2 * self.CONTENT_SIDE_PADDING
        minimum_widths = []
        for column in range(self.table.columnCount()):
            width = max(header.sectionSize(column), 1)
            for row in range(self.table.rowCount()):
                widget = self.table.cellWidget(row, column)
                if widget is not None:
                    width = max(width, widget.sizeHint().width())
            minimum_widths.append(width + padding)
        return minimum_widths

    def _calculate_required_window_width(
        self,
        content_width: int,
        margins,
    ) -> int:
        frame_width = 2 * self.table.frameWidth()
        vertical_scrollbar = (
            self.table.verticalScrollBar().width()
            if self.table.verticalScrollBar().isVisible()
            else 0
        )
        return (
            content_width
            + frame_width
            + vertical_scrollbar
            + margins.left()
            + margins.right()
        )

    def _distribute_extra_width(
        self,
        minimum_widths: list[int],
        available_width: int,
    ) -> list[int]:
        content_width = sum(minimum_widths)
        extra_width = available_width - content_width
        widths = minimum_widths.copy()
        if extra_width <= 0 or content_width <= 0:
            return widths

        distributed = 0
        for column, minimum_width in enumerate(minimum_widths):
            if column == len(minimum_widths) - 1:
                additional = extra_width - distributed
            else:
                additional = round(
                    extra_width * minimum_width / content_width,
                )
                distributed += additional
            widths[column] += additional
        return widths

    @classmethod
    def _status_text(cls, record) -> str:
        if record.status != "SUCCESS":
            return "ERROR"
        applied_at = getattr(record, "applied_at", None)
        if applied_at is None:
            return "NO APLICADO"
        return f"APLICADO\n{cls._format_datetime(cls._parse_datetime(applied_at))}"

    def _set_status_item(self, row: int, column: int, record) -> None:
        is_success = record.status == "SUCCESS"
        applied_at = getattr(record, "applied_at", None)
        is_applied = is_success and applied_at is not None

        item = QTableWidgetItem(self._status_text(record))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if is_applied:
            item.setToolTip(
                "Esta versión está actualmente aplicada al catálogo."
            )
            item.setBackground(QColor(self.APPLIED_BACKGROUND))
        elif is_success:
            item.setToolTip(
                "La descarga fue exitosa, pero esta versión ya no es la "
                "actualmente aplicada."
            )
        else:
            item.setToolTip(
                "La descarga terminó con error y no fue aplicada."
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
        self.table.setCellWidget(row, 9, container)

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

        dialog = _HistoryDetailDialog(self)
        self.detail_dialog = dialog
        dialog.setWindowTitle("Detalle de la descarga")
        dialog.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        dialog.setSizeGripEnabled(True)
        screen = dialog.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            available_width = max(
                480,
                available.width() - self.DETAIL_DETAIL_MARGIN,
            )
            initial_width = min(
                self.DETAIL_CHANGE_DIALOG_WIDTH,
                available_width,
            )
            initial_height = min(
                800,
                max(400, available.height() - self.DETAIL_DETAIL_MARGIN),
            )
            dialog.setMinimumSize(
                min(self.DETAIL_CHANGE_MIN_DIALOG_WIDTH, available_width),
                min(self.DETAIL_DETAIL_MIN_HEIGHT, initial_height),
            )
            dialog.resize(initial_width, initial_height)
        else:
            dialog.setMinimumSize(
                self.DETAIL_CHANGE_MIN_DIALOG_WIDTH,
                self.DETAIL_DETAIL_MIN_HEIGHT,
            )
            dialog.resize(self.DETAIL_CHANGE_DIALOG_WIDTH, 800)
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
        coverage.setWordWrap(False)
        coverage.setStyleSheet(
            "background:#fff3cd; color:#664d03; border:1px solid #ffda6a; "
            "border-radius:5px; padding:8px;"
        )
        layout.addWidget(coverage)
        self._size_detail_dialog_for_coverage(dialog, coverage)

        multiple = getattr(history, "multiple_category_products", []) or []
        valid_multiple = [item for item in multiple if isinstance(item, dict)]
        multiple_title = QLabel(
            f"PRODUCTOS EN MÚLTIPLES CATEGORÍAS ({len(valid_multiple)})",
        )
        multiple_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(multiple_title)

        multiple_table = QTableWidget()
        multiple_table.setColumnCount(3)
        multiple_table.setWordWrap(True)
        multiple_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        multiple_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        multiple_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        multiple_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
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
        multiple_table.verticalHeader().setVisible(True)
        multiple_table.verticalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignCenter,
        )
        multiple_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents,
        )
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

        display_changes = self._prepare_change_rows(changes)
        changes_title = QLabel(
            f"CAMBIOS DETECTADOS ({len(changes)} cambios · "
            f"{len(display_changes)} filas)",
        )
        changes_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(changes_title)

        table = self._build_changes_table(display_changes)
        layout.addWidget(table)

        dialog.set_resize_handler(
            lambda: self._fit_detail_tables(
                dialog,
                multiple_table,
                table,
            )
        )
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        QTimer.singleShot(
            0,
            lambda: self._fit_detail_tables(
                dialog,
                multiple_table,
                table,
            ),
        )

    def _build_changes_table(self, changes: list[dict]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["Tipo", "Código", "Producto", "Variación", "Anterior", "Nuevo"],
        )
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setWordWrap(True)
        table.setTextElideMode(Qt.TextElideMode.ElideNone)
        table.setAlternatingRowColors(False)
        table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )

        vertical_header = table.verticalHeader()
        vertical_header.setVisible(True)
        vertical_header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        vertical_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        vertical_header.setMinimumWidth(32)

        header = table.horizontalHeader()
        self._configure_change_table_columns(header)

        table.setRowCount(max(len(changes), 1))
        if changes:
            for row, change in enumerate(changes):
                type_text = self._change_type_text(change.get("type"))
                product_name = str(change.get("name", ""))
                values = [
                    type_text,
                    str(change.get("code", "")),
                    self._format_product_name_for_table(product_name),
                    str(change.get("variation", "")),
                ]
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setToolTip(
                        product_name if column == 2 else value
                    )
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter
                        if column in (0, 1)
                        else (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    )
                    if column == 0:
                        font = QFont(item.font())
                        font.setBold(True)
                        item.setFont(font)
                    table.setItem(row, column, item)

                self._set_change_value_cell(table, row, 4, str(change.get("old", "")))
                self._set_change_value_cell(
                    table,
                    row,
                    5,
                    str(change.get("new", "")),
                    rich_text=str(change.get("new_html", "")),
                )
        else:
            item = QTableWidgetItem("Sin cambios de campos registrados")
            item.setToolTip(item.text())
            table.setItem(0, 0, item)

        self._configure_change_table_columns(header)
        table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        return table

    def _fit_detail_tables(
        self,
        dialog: QDialog,
        multiple_table: QTableWidget,
        changes_table: QTableWidget,
    ) -> None:
        self._fit_multiple_category_table(dialog, multiple_table)
        self._fit_changes_table_to_dialog(dialog, changes_table)

    def _fit_multiple_category_table(
        self,
        dialog: QDialog,
        table: QTableWidget,
    ) -> None:
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        table.resizeRowsToContents()
        header_height = max(header.height(), header.sizeHint().height())
        rows_height = sum(
            max(
                table.rowHeight(row),
                table.sizeHintForRow(row),
            )
            for row in range(table.rowCount())
        )
        frame_height = 2 * table.frameWidth()
        scrollbar_height = (
            table.horizontalScrollBar().height()
            if table.horizontalScrollBar().isVisible()
            else 0
        )
        required_height = (
            header_height
            + rows_height
            + frame_height
            + scrollbar_height
            + 2
        )

        max_height = self._available_detail_table_height(dialog, table)
        if required_height <= max_height:
            table.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
            )
            table.setFixedHeight(required_height)
        else:
            table.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded,
            )
            table.setFixedHeight(max_height)

    def _fit_changes_table_to_dialog(
        self,
        dialog: QDialog,
        table: QTableWidget,
    ) -> None:
        header = table.horizontalHeader()
        fixed_columns = self.DETAIL_CHANGE_FIXED_COLUMN_WIDTHS
        for column in range(table.columnCount()):
            header.setSectionResizeMode(
                column,
                (
                    QHeaderView.ResizeMode.ResizeToContents
                    if column in fixed_columns
                    else QHeaderView.ResizeMode.Stretch
                ),
            )
        table.resizeColumnsToContents()

        table_width = table.viewport().width()
        fixed_width = sum(
            header.sectionSize(column)
            for column in fixed_columns
        )
        flexible_columns = [2, 4, 5]
        flexible_width = max(
            table_width - fixed_width,
            3 * 120,
        )
        base_flexible = flexible_width // len(flexible_columns)
        remainder = flexible_width - base_flexible * len(flexible_columns)
        for index, column in enumerate(flexible_columns):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Stretch,
            )
            header.resizeSection(
                column,
                base_flexible + (1 if index < remainder else 0),
            )

        table.resizeRowsToContents()
        self._fit_change_table_row_heights(table)
        header_height = max(header.height(), header.sizeHint().height())
        rows_height = sum(
            max(
                table.rowHeight(row),
                table.sizeHintForRow(row),
            )
            for row in range(table.rowCount())
        )
        frame_height = 2 * table.frameWidth()
        horizontal_scrollbar_height = (
            table.horizontalScrollBar().height()
            if table.horizontalScrollBar().isVisible()
            else 0
        )
        required_height = (
            header_height
            + rows_height
            + frame_height
            + horizontal_scrollbar_height
            + 2
        )
        max_height = self._available_detail_table_height(dialog, table)
        table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if required_height > max_height
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        table.setFixedHeight(min(required_height, max_height))

    def _fit_change_table_row_heights(self, table: QTableWidget) -> None:
        # El encabezado vertical en ResizeToContents vuelve a imponer la
        # altura calculada por Qt y descarta la holgura necesaria para que el
        # marco de selección quede separado del texto. Desde aquí las filas
        # quedan bajo control explícito de este ajuste.
        vertical_header = table.verticalHeader()
        vertical_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        for row in range(table.rowCount()):
            required_height = table.sizeHintForRow(row)
            for column in (4, 5):
                widget = table.cellWidget(row, column)
                if not isinstance(widget, QLabel):
                    continue
                column_width = table.columnWidth(column)
                if column_width <= 0:
                    continue
                required_height = max(
                    required_height,
                    self._measure_change_value_height(widget, column_width),
                )

            # La fila debe contener el marco de selección con la misma
            # holgura visual arriba y abajo del contenido.
            target_height = (
                required_height
                + 2 * self.DETAIL_CHANGE_SELECTION_FRAME_VERTICAL_CLEARANCE
            )
            table.setRowHeight(row, target_height)

            # Qt puede normalizar la altura de una sección en el primer
            # cálculo. Reaplicar solo la diferencia garantiza que la reserva
            # vertical solicitada sea la altura efectiva de la fila.
            actual_height = table.rowHeight(row)
            if actual_height < target_height:
                table.setRowHeight(
                    row,
                    target_height + target_height - actual_height,
                )

    def _measure_change_value_height(
        self,
        widget: QLabel,
        column_width: int,
    ) -> int:
        margins = widget.contentsMargins()
        content_width = max(
            column_width - margins.left() - margins.right(),
            1,
        )

        document = QTextDocument()
        document.setDefaultFont(widget.font())
        document.setDocumentMargin(0)
        document.setTextWidth(content_width)
        document.setHtml(widget.text())
        rendered_height = ceil(document.documentLayout().documentSize().height())

        minimum_height = self._minimum_change_value_label_height(widget)
        return max(
            rendered_height
            + margins.top()
            + margins.bottom()
            + self.DETAIL_CHANGE_ROW_HEIGHT_BUFFER,
            minimum_height,
        )

    @staticmethod
    def _available_detail_table_height(
        dialog: QDialog,
        table: QTableWidget,
    ) -> int:
        maximum_height = dialog.height()
        screen = dialog.screen() or QApplication.primaryScreen()
        if screen is not None:
            maximum_height = min(
                maximum_height,
                screen.availableGeometry().height(),
            )
        layout = dialog.layout()
        if layout is None or maximum_height <= 0:
            return max(160, table.sizeHint().height())

        non_table_height = 0
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if widget is None or widget is table:
                continue
            non_table_height += widget.sizeHint().height()

        spacing = layout.spacing() * max(layout.count() - 1, 0)
        margins = layout.contentsMargins()
        available = (
            maximum_height
            - non_table_height
            - spacing
            - margins.top()
            - margins.bottom()
        )
        return max(160, available)

    def _size_detail_dialog_for_coverage(
        self,
        dialog: QDialog,
        coverage: QLabel,
    ) -> None:
        screen = dialog.screen() or QApplication.primaryScreen()
        layout = dialog.layout()
        if screen is None or layout is None:
            return

        margins = layout.contentsMargins()
        coverage.setWordWrap(False)
        coverage.adjustSize()
        required_width = (
            coverage.sizeHint().width()
            + margins.left()
            + margins.right()
            + 8
        )
        available_width = (
            screen.availableGeometry().width() - self.DETAIL_DETAIL_MARGIN
        )

        if required_width <= available_width:
            dialog.setMinimumWidth(
                max(self.DETAIL_CHANGE_MIN_DIALOG_WIDTH, required_width)
            )
            if dialog.width() < required_width:
                dialog.resize(required_width, dialog.height())
            return

        coverage.setWordWrap(True)
        coverage.setMinimumWidth(
            max(320, available_width - margins.left() - margins.right() - 2)
        )
        dialog.setMinimumWidth(
            min(
                max(self.DETAIL_CHANGE_MIN_DIALOG_WIDTH, 320),
                available_width,
            )
        )

    @classmethod
    def _format_product_name_for_table(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return "—"
        font = QFont(cls.FONT_FAMILY)
        font.setPixelSize(cls.BODY_FONT_SIZE)
        metrics = QFontMetrics(font)

        words = text.split()
        if len(words) <= 1:
            return text

        best_split = None
        best_width = None
        for split_index in range(1, len(words)):
            first = " ".join(words[:split_index])
            second = " ".join(words[split_index:])
            width = max(metrics.horizontalAdvance(first), metrics.horizontalAdvance(second))
            if best_width is None or width < best_width:
                best_width = width
                best_split = split_index

        if best_split is None or best_width is None:
            return text
        if best_width <= cls.DETAIL_CHANGE_PRODUCT_MAX_WIDTH:
            return "\n".join(
                [
                    " ".join(words[:best_split]),
                    " ".join(words[best_split:]),
                ]
            )
        return text

    def _set_change_value_cell(
        self,
        table: QTableWidget,
        row: int,
        column: int,
        value: str,
        *,
        rich_text: str = "",
    ) -> None:
        if not rich_text and column == 5:
            rich_text = self._format_delta_value_html(value)
        if not rich_text:
            rich_text = self._format_plain_value_html(value)

        label = QLabel()
        label.setMargin(0)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setText(rich_text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setContentsMargins(
            self.CONTENT_SIDE_PADDING,
            4,
            self.CONTENT_SIDE_PADDING,
            4,
        )
        label.setToolTip(value.replace("\n", " · "))
        font = QFont(self.FONT_FAMILY)
        font.setPixelSize(self.BODY_FONT_SIZE)
        label.setFont(font)
        label.setStyleSheet(
            f'font-family: "{self.FONT_FAMILY}"; '
            f"font-size: {self.BODY_FONT_SIZE}px; "
            f"color: {self.TEXT_COLOR};"
        )
        label.setMinimumHeight(self._minimum_change_value_label_height(label))
        table.setCellWidget(row, column, label)

    def _minimum_change_value_label_height(self, label: QLabel) -> int:
        line_count = max(label.text().count("<br>") + 1, 1)
        line_height = label.fontMetrics().lineSpacing()
        return (
            line_count * line_height
            + label.contentsMargins().top()
            + label.contentsMargins().bottom()
            + self.DETAIL_CHANGE_ROW_HEIGHT_BUFFER
        )

    @staticmethod
    def _format_plain_value_html(value: str) -> str:
        return "<br>".join(escape(line) for line in str(value or "").split("\n"))

    @classmethod
    def _format_delta_value_html(cls, value: str) -> str:
        lines = str(value or "").split("\n")
        html_lines = []
        pattern = re.compile(r"(\([+-](?:s/)?[0-9][0-9,]*(?:\.[0-9]+)?\))$")
        has_delta = False

        for line in lines:
            escaped_line = escape(line)
            match = pattern.search(escaped_line)
            if match is None:
                html_lines.append(escaped_line)
                continue

            has_delta = True
            prefix = escaped_line[:match.start(1)]
            delta_text = escaped_line[match.start(1):]
            sign = "+" if delta_text.startswith("(+") else "-"
            color = cls.DELTA_INCREASE_COLOR if sign == "+" else cls.DELTA_DECREASE_COLOR
            html_lines.append(
                f'{prefix}<span style="color:{color}; font-weight:600;">{delta_text}</span>'
            )

        return "<br>".join(html_lines) if has_delta else ""

    @classmethod
    def _configure_change_table_columns(cls, header: QHeaderView) -> None:
        for column in range(6):
            header.setSectionResizeMode(
                column,
                (
                    QHeaderView.ResizeMode.ResizeToContents
                    if column in cls.DETAIL_CHANGE_FIXED_COLUMN_WIDTHS
                    else QHeaderView.ResizeMode.Stretch
                ),
            )

    @classmethod
    def _change_type_text(cls, value) -> str:
        normalized = str(value or "").strip().upper()
        return cls.CHANGE_TYPE_LABELS.get(normalized, normalized)
    @classmethod
    def _prepare_change_rows(cls, changes: list[dict]) -> list[dict]:
        grouped: dict[tuple[str, str, str], dict] = {}
        order: list[tuple[str, str, str]] = []

        for change in changes:
            change_type = str(change.get("type", "")).strip().upper()
            code = str(change.get("code", "")).strip()
            name = str(change.get("name", "")).strip()
            key = (change_type, code.casefold(), name.casefold())
            if key not in grouped:
                grouped[key] = {
                    "type": change_type,
                    "code": code,
                    "name": name,
                    "entries": [],
                    "stock": None,
                    "color_stock": None,
                    "prices": {},
                    "category": None,
                }
                order.append(key)

            field = str(change.get("field", "")).strip().casefold()
            specialized_fields = {
                "stock": "stock",
                "color_stock": "color_stock",
                "category": "category",
            }
            target = specialized_fields.get(field)
            if target is not None:
                grouped[key][target] = change
            elif field in cls.PRICE_FIELD_LABELS:
                grouped[key]["prices"][field] = change
            else:
                grouped[key]["entries"].append(change)

        rows = []
        for key in order:
            group = grouped[key]
            stock_entry = cls._build_stock_entry(
                group["stock"],
                group["color_stock"],
            )
            cls._append_optional_row(rows, group, stock_entry)

            if group["prices"]:
                cls._append_optional_row(
                    rows,
                    group,
                    cls._build_price_entry(group["prices"]),
                )

            if group["category"] is not None:
                cls._append_optional_row(
                    rows,
                    group,
                    cls._build_category_entry(group["category"]),
                )

            rows.extend(
                cls._row_from_entry(group, cls._entry_from_change(change))
                for change in group["entries"]
            )
        return sorted(
            rows,
            key=lambda row: cls._alphanumeric_sort_key(row.get("code", "")),
        )

    @staticmethod
    def _alphanumeric_sort_key(value) -> tuple[tuple[int, object], ...]:
        parts = re.split(r"(\d+)", str(value or "").strip().casefold())
        return tuple(
            (1, int(part)) if part.isdigit() else (0, part)
            for part in parts
            if part
        )

    @staticmethod
    def _append_optional_row(rows: list[dict], group: dict, entry) -> None:
        if entry is not None:
            rows.append(ScrapingHistoryDialog._row_from_entry(group, entry))

    @classmethod
    def _entry_from_change(cls, change: dict):
        return (
            str(change.get("label", change.get("field", ""))),
            cls._display_value(change.get("old")),
            cls._display_value(change.get("new")),
            "",
            "plain",
        )

    @staticmethod
    def _row_from_entry(group: dict, entry: tuple[str, str, str, str, str]):
        variation, old_value, new_value, new_html, kind = entry
        return {
            "type": group["type"],
            "code": group["code"],
            "name": group["name"],
            "variation": variation,
            "old": old_value,
            "new": new_value,
            "new_html": new_html,
            "kind": kind,
        }
    @classmethod
    def _build_stock_entry(cls, stock_change, color_stock_change):
        if stock_change is None and color_stock_change is None:
            return None

        stock_data = stock_change if isinstance(stock_change, dict) else {}
        color_stock_data = color_stock_change if isinstance(color_stock_change, dict) else {}
        old_color_stock = cls._as_color_stock(color_stock_data.get("old"))
        new_color_stock = cls._as_color_stock(color_stock_data.get("new"))

        if old_color_stock or new_color_stock:
            changed_colors = [
                color
                for color in set(old_color_stock) | set(new_color_stock)
                if not cls._values_equal(
                    old_color_stock.get(color),
                    new_color_stock.get(color),
                )
            ]
            if changed_colors:
                old_text, new_text, new_html = cls._format_stock_values(
                    old_color_stock,
                    new_color_stock,
                )
                variation = (
                    "Stock por color"
                    if max(len(old_color_stock), len(new_color_stock)) > 1
                    else "Stock"
                )
                return (variation, old_text, new_text, new_html, "stock")

        old_value = stock_data.get("old")
        new_value = stock_data.get("new")
        if cls._values_equal(old_value, new_value):
            return None
        new_amount = cls._numeric_stock(new_value)
        old_amount = cls._numeric_stock(old_value)
        delta = (
            new_amount - old_amount
            if new_amount is not None and old_amount is not None
            else None
        )
        return (
            "Stock",
            cls._format_stock_scalar(old_value),
            cls._format_delta_text(
                cls._format_stock_scalar(new_value),
                delta,
            ),
            cls._format_stock_scalar_html(old_value, new_value),
            "stock",
        )

    @classmethod
    def _format_stock_values(cls, old_stock: dict, new_stock: dict):
        old_lines = []
        new_lines = []
        new_html_lines = []
        colors = sorted(
            set(old_stock) | set(new_stock),
            key=lambda item: str(item).casefold(),
        )
        for color in colors:
            old_value = old_stock.get(color)
            new_value = new_stock.get(color)
            if cls._values_equal(old_value, new_value):
                continue

            old_amount = cls._numeric_stock(old_value)
            new_amount = cls._numeric_stock(new_value)
            old_text = cls._format_stock_number(old_amount)
            new_text = cls._format_stock_number(new_amount)
            old_lines.append(f"{color}: {old_text}")
            delta = (
                new_amount - old_amount
                if old_amount is not None and new_amount is not None
                else (
                    new_amount
                    if old_amount is None and new_amount is not None
                    else (
                        -old_amount
                        if old_amount is not None and new_amount is None
                        else None
                    )
                )
            )
            base_new_line = f"{color}: {new_text}"
            new_lines.append(
                cls._format_delta_text(base_new_line, delta)
            )
            new_html_lines.append(
                cls._format_delta_line(
                    base_new_line,
                    delta,
                    prefix_length=len(f"{color}: "),
                )
            )
        return (
            "\n".join(old_lines) if old_lines else "—",
            "\n".join(new_lines) if new_lines else "—",
            "<br>".join(new_html_lines) if new_html_lines else "—",
        )

    @classmethod
    def _format_stock_scalar_html(cls, old_value, new_value) -> str:
        new_amount = cls._numeric_stock(new_value)
        old_amount = cls._numeric_stock(old_value)
        if new_amount is None:
            return escape(cls._format_stock_scalar(new_value))
        delta = new_amount - old_amount if old_amount is not None else None
        return cls._format_delta_line(cls._format_stock_scalar(new_value), delta)

    @classmethod
    def _format_stock_scalar(cls, value) -> str:
        return cls._format_stock_number(cls._numeric_stock(value))

    @staticmethod
    def _format_stock_number(value: int | None) -> str:
        return f"{value:,}" if value is not None else "—"

    @classmethod
    def _format_delta_text(
        cls,
        text: str,
        delta,
        *,
        currency: bool = False,
    ) -> str:
        if delta is None or delta == 0:
            return text
        if currency:
            return f"{text} ({'+' if delta > 0 else '-'}s/{abs(delta):.2f})"
        return f"{text} ({delta:+d})"

    @classmethod
    def _build_price_entry(cls, changes: dict[str, dict]):
        changed_prices = {}
        for field, change in changes.items():
            if not isinstance(change, dict):
                continue
            if not cls._values_equal(change.get("old"), change.get("new")):
                changed_prices[field] = change

        if not changed_prices:
            return None

        if len(changed_prices) == 1 and "price" in changed_prices:
            change = changed_prices["price"]
            return (
                "Precio",
                cls._display_value(change.get("old")),
                cls._display_value(change.get("new")),
                "",
                "price",
            )

        old_lines = []
        new_lines = []
        new_html_lines = []
        for field, label in cls.PRICE_FIELD_LABELS.items():
            change = changed_prices.get(field)
            if change is None:
                continue
            old_amount = cls._numeric_price(change.get("old"))
            new_amount = cls._numeric_price(change.get("new"))
            old_text = cls._format_currency(old_amount)
            new_text = cls._format_currency(new_amount)
            old_lines.append(f"{label}: {old_text}")
            delta = (
                new_amount - old_amount
                if new_amount is not None and old_amount is not None
                else None
            )
            base_new_line = f"{label}: {new_text}"
            new_lines.append(
                cls._format_delta_text(
                    base_new_line,
                    delta,
                    currency=True,
                )
            )
            new_html_lines.append(
                cls._format_delta_line(
                    base_new_line,
                    delta,
                    delta_suffix="currency",
                    prefix_length=len(f"{label}: "),
                )
            )

        variation = "Precio" if len(changed_prices) == 1 else "Precios"
        return (
            variation,
            "\n".join(old_lines),
            "\n".join(new_lines),
            "<br>".join(new_html_lines),
            "price",
        )

    @classmethod
    def _build_category_entry(cls, change: dict):
        old_value = change.get("old")
        new_value = change.get("new")
        if cls._values_equal(old_value, new_value):
            return None
        return (
            "Categoría",
            cls._format_category_value(old_value),
            cls._format_category_value(new_value),
            "",
            "category",
        )

    @classmethod
    def _format_category_value(cls, value) -> str:
        return "\n".join(cls._split_categories(value)) or "—"

    @staticmethod
    def _split_categories(value) -> list[str]:
        from services.scraping.category_name_normalizer import split_category_names
        categories = split_category_names(value)
        if categories:
            return categories
        text = str(value or "").strip()
        return [text] if text else []

    @staticmethod
    def _values_equal(old_value, new_value) -> bool:
        if isinstance(old_value, (int, float)) and isinstance(
            new_value,
            (int, float),
        ):
            return float(old_value) == float(new_value)
        return old_value == new_value

    @staticmethod
    def _numeric_price(value) -> float | None:
        if isinstance(value, bool):
            return float(int(value))
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_currency(value: float | None) -> str:
        return f"s/{value:.2f}" if value is not None else "—"

    @classmethod
    def _format_delta_line(cls, text: str, delta, *, delta_suffix: str = "stock", prefix_length: int = 0) -> str:
        escaped_text = escape(text)
        if delta is None or delta == 0:
            return escaped_text
        if delta_suffix == "currency":
            sign_text = f"{'+' if delta > 0 else '-'}s/{abs(delta):.2f}"
        else:
            sign_text = f"{delta:+d}"
        color = cls.DELTA_INCREASE_COLOR if delta > 0 else cls.DELTA_DECREASE_COLOR
        base_length = prefix_length if prefix_length > 0 else len(text)
        base = escape(text[:base_length])
        suffix = escape(text[base_length:])
        return f'{base}{suffix} <span style="color:{color}; font-weight:600;">({escape(sign_text)})</span>'
    @classmethod
    def _format_stock_new_value(
        cls,
        old_value,
        new_value,
        *,
        by_color: bool = False,
    ) -> str:
        if by_color:
            old_stock = cls._as_color_stock(old_value)
            new_stock = cls._as_color_stock(new_value)
            colors = sorted(
                set(old_stock) | set(new_stock),
                key=lambda item: str(item).casefold(),
            )
            lines = []
            for color in colors:
                old_amount = cls._numeric_stock(old_stock.get(color))
                new_amount = cls._numeric_stock(new_stock.get(color))
                if cls._values_equal(
                    old_stock.get(color),
                    new_stock.get(color),
                ):
                    continue
                delta = (
                    new_amount - old_amount
                    if old_amount is not None and new_amount is not None
                    else (
                        new_amount
                        if old_amount is None and new_amount is not None
                        else (
                            -old_amount
                            if old_amount is not None and new_amount is None
                            else None
                        )
                    )
                )
                base = (
                    str(new_amount)
                    if new_amount is not None
                    else "—"
                )
                lines.append(
                    f"{color}: {cls._format_delta_text(base, delta)}"
                )
            return "\n".join(lines) if lines else "—"

        old_amount = cls._numeric_stock(old_value)
        new_amount = cls._numeric_stock(new_value)
        if cls._values_equal(old_value, new_value):
            return "—"
        delta = (
            new_amount - old_amount
            if new_amount is not None and old_amount is not None
            else None
        )
        base = str(new_amount) if new_amount is not None else "—"
        return cls._format_delta_text(base, delta)

    @staticmethod
    def _numeric_stock(value) -> int | None:
        if isinstance(value, bool):
            return int(value)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_color_stock(value) -> dict:
        if not isinstance(value, dict):
            return {}
        return {
            str(color).strip(): stock
            for color, stock in value.items()
            if str(color).strip()
        }

    @staticmethod
    def _single_color_stock_value(value):
        if len(value) == 1:
            return next(iter(value.values()))
        return None

    def _detail_dialog_closed(self) -> None:
        self.detail_dialog = None

    @staticmethod
    def _display_value(value) -> str:
        if isinstance(value, dict):
            if not value:
                return "—"
            lines = []
            for key in sorted(value, key=lambda item: str(item).casefold()):
                rendered = value[key]
                if isinstance(rendered, (dict, list)):
                    rendered_text = json.dumps(
                        rendered,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                else:
                    rendered_text = str(rendered)
                lines.append(f"{key}: {rendered_text}")
            return "\n".join(lines)
        if isinstance(value, list):
            return ", ".join(str(item) for item in value) if value else "—"
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
        self._initial_fit_timer.stop()
        try:
            if self.detail_dialog is not None:
                self.detail_dialog.close()
            self.db.close()
        finally:
            super().closeEvent(event)
