import textwrap
from datetime import datetime
from typing import ClassVar
from zoneinfo import ZoneInfo

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from controllers.product_controller import ProductController
from database.db_manager import DBManager
from exporters.excel_exporter import ExcelExporter
from exporters.pdf_exporter import PDFExporter
from gui.product_dialog import ProductDialog
from gui.product_table import ProductTable
from gui.scraping_dialog import ScrapingDialog
from gui.scraping_history_dialog import ScrapingHistoryDialog
from models.product import Product
from repositories.scraping.catalog_load_repository import CatalogLoadRepository


class MainWindow(QMainWindow):
    """Ventana principal del catálogo."""

    SCRAPING_SCHEDULE: ClassVar[set[tuple[int, int, int]]] = {
        (0, 12, 0),
        (0, 22, 0),
        (1, 12, 0),
        (1, 22, 0),
        (2, 12, 0),
        (2, 22, 0),
        (3, 12, 0),
        (3, 22, 0),
        (4, 12, 0),
        (4, 22, 0),
        (5, 12, 0),
        (5, 22, 0),
    }

    ACTIVE_BUTTON_STYLE = """
        QPushButton:checked {
            background-color: #b2ebf2;
            border: 1px solid #4dd0e1;
            font-weight: bold;
        }
    """

    TOGGLE_FONT_SIZE = 18
    TOGGLE_BUTTON_HORIZONTAL_PADDING = 24
    CATEGORY_FONT_SIZE = 14
    CATEGORY_MIN_FONT_SIZE = 9
    CATEGORY_BUTTON_HORIZONTAL_PADDING = 20
    CATEGORY_MIN_BUTTON_WIDTH = 80
    CATEGORY_MAX_ROWS = 3
    CATEGORY_VERTICAL_SPACING = 2

    def __init__(self) -> None:
        super().__init__()
        self.controller = ProductController()
        self.catalog_load_db = DBManager()
        self.catalog_load_repository = CatalogLoadRepository(self.catalog_load_db)
        self.catalog_load_repository.ensure_initial_applied_load()
        self.catalog_load_repository.restore_latest_applied()
        self.catalog_load_repository.cleanup_expired_history()
        self.setWindowTitle("Facundo Catalog Manager")
        self.resize(1200, 700)

        self.all_products: list[Product] = []
        self.selected_categories: set[str] = set()
        self.stock_only = False
        self.category_buttons: list[QPushButton] = []
        self.categories_visible = False
        self.scraping_dialog: ScrapingDialog | None = None
        self.history_dialog: ScrapingHistoryDialog | None = None
        self.last_scheduled_scraping: tuple[int, int, int] | None = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.create_filter_controls(layout)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar producto...")
        self.search_box.setMinimumHeight(42)
        self.search_box.setStyleSheet(
            "QLineEdit { font-size: 18px; padding: 5px 8px; }",
        )
        self.search_box.textChanged.connect(self.search_products)
        layout.addWidget(self.search_box)

        self.table = ProductTable(self.controller)
        layout.addWidget(self.table)

        counter_layout = QHBoxLayout()
        counter_layout.setContentsMargins(0, 0, 0, 0)
        self.product_counter = QLabel("Mostrando 0 de 0 productos")
        self.product_counter.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        self.product_counter.setStyleSheet(
            "QLabel { font-size: 14px; font-weight: bold; }",
        )
        counter_layout.addWidget(self.product_counter)
        counter_layout.addStretch()
        layout.addLayout(counter_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(6)
        buttons = [
            ("Nuevo", self.new_product),
            ("Editar", self.edit_product),
            ("Eliminar", self.delete_product),
            ("Exportar Excel", self.export_excel),
            ("Exportar PDF", self.export_pdf),
            ("Actualizar catálogo", self.open_scraping),
            ("Historial", self.open_scraping_history),
        ]
        for text, callback in buttons:
            button = QPushButton(text)
            button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            button.clicked.connect(callback)
            buttons_layout.addWidget(button)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        self.refresh_catalog()
        self.start_scraping_scheduler()

    def create_filter_controls(self, layout: QVBoxLayout) -> None:
        filter_layout = QVBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(6)

        top_controls = QHBoxLayout()
        top_controls.setContentsMargins(0, 0, 0, 0)
        top_controls.setSpacing(8)

        self.category_toggle_button = QPushButton("Filtrar Categorías")
        self.category_toggle_button.setCheckable(True)
        self._configure_toggle_button(
            self.category_toggle_button,
            "Filtrar Categorías",
            "Ocultar Categorías",
        )
        self.category_toggle_button.toggled.connect(self.toggle_categories_visibility)
        top_controls.addWidget(self.category_toggle_button)

        self.stock_filter_button = QPushButton("Solo Stock Disponible")
        self.stock_filter_button.setCheckable(True)
        self._configure_toggle_button(
            self.stock_filter_button,
            "Solo Stock Disponible",
        )
        self.stock_filter_button.setToolTip(
            "Mostrar únicamente productos con stock mayor a 0.",
        )
        self.stock_filter_button.toggled.connect(self.toggle_stock_filter)
        top_controls.addWidget(self.stock_filter_button)
        top_controls.addStretch()
        filter_layout.addLayout(top_controls)

        self.category_scroll = QScrollArea()
        self.category_scroll.setWidgetResizable(True)
        self.category_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.category_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self.category_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.category_scroll.setMinimumHeight(0)
        self.category_scroll.setMaximumHeight(220)
        self.category_scroll.setVisible(False)
        filter_layout.addWidget(self.category_scroll)

        self.category_container = QWidget()
        self.category_layout = QGridLayout(self.category_container)
        self.category_layout.setContentsMargins(0, 0, 0, 0)
        self.category_layout.setHorizontalSpacing(6)
        self.category_layout.setVerticalSpacing(self.CATEGORY_VERTICAL_SPACING)
        self.category_scroll.setWidget(self.category_container)

        self.all_categories_button = QPushButton("Todos")
        self.all_categories_button.setCheckable(True)
        self.all_categories_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.all_categories_button.setStyleSheet(
            "QPushButton { padding: 3px 10px; }\n" + self.ACTIVE_BUTTON_STYLE,
        )
        self.all_categories_button.clicked.connect(self.clear_category_filters)
        self.category_buttons = [self.all_categories_button]
        layout.addLayout(filter_layout)

    @classmethod
    def _configure_toggle_button(
        cls,
        button: QPushButton,
        *texts: str,
    ) -> None:
        """Configura el tamaño real de fuente y reserva ambos estados desde el inicio."""
        font = button.font()
        font.setPointSize(cls.TOGGLE_FONT_SIZE)
        button.setFont(font)
        button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        button.setStyleSheet(
            "QPushButton { font-size: 18px; padding: 5px 10px; }\n"
            + cls.ACTIVE_BUTTON_STYLE,
        )
        cls._set_toggle_button_width(button, *texts)

    @classmethod
    def _set_toggle_button_width(
        cls,
        button: QPushButton,
        *texts: str,
    ) -> None:
        """Reserva desde el inicio el ancho necesario para normal y activo."""
        font = button.font()
        metrics = QFontMetrics(font)
        bold_font = QFont(font)
        bold_font.setBold(True)
        bold_metrics = QFontMetrics(bold_font)
        required_width = max(
            max(metrics.horizontalAdvance(text), bold_metrics.horizontalAdvance(text))
            for text in texts
        ) + cls.TOGGLE_BUTTON_HORIZONTAL_PADDING
        button.setFixedWidth(required_width)
        button.setMinimumHeight(42)
        button.setMaximumHeight(42)

    @classmethod
    def _grow_toggle_button_width(cls, button: QPushButton) -> None:
        """Mantiene el ancho correcto al cambiar el texto del estado."""
        if button is cls:
            return
        if button is getattr(button.window(), "category_toggle_button", None):
            cls._set_toggle_button_width(
                button,
                "Filtrar Categorías",
                "Ocultar Categorías",
            )
        elif button is getattr(button.window(), "stock_filter_button", None):
            cls._set_toggle_button_width(button, "Solo Stock Disponible")
        else:
            cls._set_toggle_button_width(button, button.text())

    @classmethod
    def _category_font_for_width(cls, button: QPushButton, text: str, width: int) -> QFont:
        """Reduce la fuente solo cuando es necesario para conservar una sola línea."""
        font = button.font()
        font.setPointSize(cls.CATEGORY_FONT_SIZE)
        bold_font = QFont(font)
        bold_font.setBold(True)
        available = max(20, width - cls.CATEGORY_BUTTON_HORIZONTAL_PADDING)

        while font.pointSize() > cls.CATEGORY_MIN_FONT_SIZE:
            normal_width = QFontMetrics(font).horizontalAdvance(text)
            bold_width = QFontMetrics(bold_font).horizontalAdvance(text)
            if max(normal_width, bold_width) <= available:
                break
            next_size = font.pointSize() - 1
            font.setPointSize(next_size)
            bold_font.setPointSize(next_size)

        return font

    @classmethod
    def _fit_category_button(
        cls,
        button: QPushButton,
        text: str,
        cell_width: int,
    ) -> None:
        """Ajusta cada categoría a una sola línea y al ancho de su celda."""
        font = cls._category_font_for_width(button, text, cell_width)
        button.setFont(font)
        button.setText(text)
        button.setToolTip(text)
        button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        button.setMinimumWidth(0)
        button.setMaximumWidth(cell_width)
        button.setFixedWidth(cell_width)
        button.setFixedHeight(34)

    def toggle_categories_visibility(self, visible: bool) -> None:
        self.categories_visible = visible
        self.category_scroll.setVisible(visible)
        self.category_toggle_button.setText(
            "Ocultar Categorías" if visible else "Filtrar Categorías",
        )
        self._grow_toggle_button_width(self.category_toggle_button)
        QTimer.singleShot(0, self._reflow_category_buttons)

    def refresh_catalog(self) -> None:
        self.all_products = self.controller.get_products()
        self.rebuild_category_filters()
        self.apply_filters()

    @staticmethod
    def _product_categories(product: Product) -> set[str]:
        return {
            category.strip()
            for category in str(product.category).split(",")
            if category.strip()
        }

    def rebuild_category_filters(self) -> None:
        for button in self.category_buttons:
            if button is not self.all_categories_button:
                button.deleteLater()
        self.category_buttons = [self.all_categories_button]

        while self.category_layout.count():
            item = self.category_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        categories = sorted(
            {
                category
                for product in self.all_products
                for category in self._product_categories(product)
            },
            key=str.casefold,
        )
        self.selected_categories.intersection_update(set(categories))

        for category in categories:
            button = QPushButton(category)
            button.setProperty("category_text", category)
            button.setCheckable(True)
            button.setChecked(category in self.selected_categories)
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            button.setStyleSheet(
                "QPushButton { padding: 3px 10px; }\n" + self.ACTIVE_BUTTON_STYLE,
            )
            button.clicked.connect(
                lambda checked, value=category: self.toggle_category(value, checked),
            )
            self.category_buttons.append(button)

        self._update_all_categories_button()
        self._reflow_category_buttons()

    def _reflow_category_buttons(self) -> None:
        if not hasattr(self, "category_layout"):
            return

        while self.category_layout.count():
            item = self.category_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        viewport_width = self.category_scroll.viewport().width()
        if viewport_width <= 1 or not self.category_buttons:
            return

        spacing = self.category_layout.horizontalSpacing()
        available_width = max(viewport_width, 1)
        total_buttons = len(self.category_buttons)
        row_count = min(self.CATEGORY_MAX_ROWS, total_buttons)
        column_count = max(1, (total_buttons + row_count - 1) // row_count)
        column_count = min(column_count, total_buttons)
        column_width = max(
            1,
            (available_width - spacing * (column_count - 1)) // column_count,
        )

        for column in range(column_count):
            self.category_layout.setColumnStretch(column, 1)
        for row in range(row_count):
            self.category_layout.setRowStretch(row, 0)

        for index, button in enumerate(self.category_buttons):
            row = index // column_count
            column = index % column_count
            remaining = total_buttons - row * column_count
            span = 1
            if remaining < column_count:
                span = column_count // remaining
                if column < column_count % remaining:
                    span += 1
                if column >= remaining:
                    continue

            cell_width = column_width * span + spacing * (span - 1)
            text = str(button.property("category_text") or button.text()).replace(
                "\n",
                " ",
            )
            self._fit_category_button(button, text, cell_width)
            self.category_layout.addWidget(button, row, column, 1, span)

        self.category_container.adjustSize()

    def _update_all_categories_button(self) -> None:
        self.all_categories_button.setChecked(not self.selected_categories)
        self.all_categories_button.setText("Todos")

    def clear_category_filters(self) -> None:
        self.selected_categories.clear()
        for button in self.category_buttons:
            if button is not self.all_categories_button:
                button.setChecked(False)
        self._update_all_categories_button()
        if self.categories_visible:
            self._reflow_category_buttons()
        self.apply_filters()

    def toggle_category(self, category: str, checked: bool) -> None:
        if checked:
            self.selected_categories.add(category)
        else:
            self.selected_categories.discard(category)
        self._update_all_categories_button()
        if self.categories_visible:
            self._reflow_category_buttons()
        self.apply_filters()

    def toggle_stock_filter(self, checked: bool) -> None:
        self.stock_only = checked
        self._grow_toggle_button_width(self.stock_filter_button)
        self.apply_filters()

    def apply_filters(self) -> None:
        products = list(self.all_products)
        search_text = self.search_box.text().strip().casefold()
        if search_text:
            products = [
                product
                for product in products
                if self.product_matches_search(product, search_text)
            ]
        if self.selected_categories:
            products = [
                product
                for product in products
                if self.selected_categories.intersection(
                    self._product_categories(product),
                )
            ]
        if self.stock_only:
            products = [product for product in products if product.stock > 0]
        self.table.load_products(products)
        self.table.set_search_text(search_text)
        self.update_product_counter(len(products))

    @staticmethod
    def product_matches_search(product: Product, search_text: str) -> bool:
        values = (
            product.code,
            product.name,
            product.description,
            product.category,
            ", ".join(product.colors),
        )
        return any(search_text in str(value).casefold() for value in values)

    def open_scraping(self) -> None:
        if self.is_scraping_running():
            if self.scraping_dialog is not None:
                if self.scraping_dialog.isMinimized():
                    self.scraping_dialog.showNormal()
                self.scraping_dialog.raise_()
                self.scraping_dialog.activateWindow()
            return
        self.scraping_dialog = ScrapingDialog(self)
        self.scraping_dialog.finished_success.connect(self.scraping_finished)
        self.scraping_dialog.finished.connect(self.scraping_dialog_closed)
        self.scraping_dialog.setModal(False)
        self.scraping_dialog.show()
        self.scraping_dialog.raise_()
        self.scraping_dialog.activateWindow()

    def open_scraping_history(self) -> None:
        if self.history_dialog is not None:
            if self.history_dialog.isMinimized():
                self.history_dialog.showNormal()
            self.history_dialog.raise_()
            self.history_dialog.activateWindow()
            return
        self.history_dialog = ScrapingHistoryDialog(self)
        self.history_dialog.catalog_applied.connect(self.refresh_catalog)
        self.history_dialog.finished.connect(lambda: self._history_closed())
        self.history_dialog.setModal(False)
        self.history_dialog.show()
        self.history_dialog.raise_()
        self.history_dialog.activateWindow()

    def _history_closed(self) -> None:
        self.history_dialog = None

    def scraping_finished(self) -> None:
        if self.scraping_dialog is not None:
            self.scraping_dialog.setWindowTitle("Actualización completada")
            self.scraping_dialog.raise_()
            self.scraping_dialog.activateWindow()

    def scraping_dialog_closed(self) -> None:
        self.scraping_dialog = None

    def is_scraping_running(self) -> bool:
        if self.scraping_dialog is None:
            return False
        thread = self.scraping_dialog.scraping_thread
        return bool(thread is not None and thread.isRunning())

    def start_scraping_scheduler(self) -> None:
        self.scraping_scheduler = QTimer(self)
        self.scraping_scheduler.setInterval(30_000)
        self.scraping_scheduler.timeout.connect(self.check_scraping_schedule)
        self.scraping_scheduler.start()
        self.check_scraping_schedule()

    def check_scraping_schedule(self) -> None:
        now = datetime.now(ZoneInfo("America/Lima")).replace(
            second=0,
            microsecond=0,
        )
        schedule_key = (now.weekday(), now.hour, now.minute)
        if schedule_key not in self.SCRAPING_SCHEDULE:
            return
        if self.last_scheduled_scraping == schedule_key:
            return
        self.last_scheduled_scraping = schedule_key
        if self.is_scraping_running():
            return
        self.open_scraping()
        if self.scraping_dialog is not None:
            QTimer.singleShot(0, self.scraping_dialog.start_scraping)

    def update_product_counter(self, filtered_count: int | None = None) -> None:
        total = len(self.all_products)
        visible = total if filtered_count is None else filtered_count
        self.product_counter.setText(f"Mostrando {visible} de {total} productos")

    def new_product(self) -> None:
        dialog = ProductDialog(self)
        if dialog.exec():
            self.refresh_catalog()

    def edit_product(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Editar", "Seleccione un producto.")
            return
        item = self.table.item(row, 1)
        if item is None:
            return
        product_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(product_id, int):
            return
        product = self.controller.get_product_by_id(product_id)
        if product is None:
            return
        dialog = ProductDialog(self, product)
        if dialog.exec():
            self.refresh_catalog()

    def delete_product(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 1)
        if item is None:
            return
        product_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(product_id, int):
            return
        response = QMessageBox.question(
            self,
            "Confirmar eliminación",
            "¿Desea eliminar este producto?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if response == QMessageBox.StandardButton.Yes:
            self.controller.delete_product(product_id)
            self.refresh_catalog()

    def search_products(self, _text: str) -> None:
        self.apply_filters()

    def export_excel(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Excel",
            "catalogo.xlsx",
            "Excel (*.xlsx)",
        )
        if filename:
            ExcelExporter.export(self.controller.get_products(), filename)

    def export_pdf(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar PDF",
            "catalogo.pdf",
            "PDF (*.pdf)",
        )
        if filename:
            PDFExporter.export(self.controller.get_products(), filename)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.categories_visible:
            QTimer.singleShot(0, self._reflow_category_buttons)

    def closeEvent(self, event) -> None:
        if hasattr(self, "scraping_scheduler"):
            self.scraping_scheduler.stop()
        if self.scraping_dialog is not None:
            self.scraping_dialog.close()
        if self.history_dialog is not None:
            self.history_dialog.close()
        if hasattr(self, "catalog_load_db"):
            self.catalog_load_db.close()
        super().closeEvent(event)
