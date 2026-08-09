from datetime import datetime
from typing import ClassVar
from zoneinfo import ZoneInfo

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
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
        (0, 12, 0), (0, 22, 0),
        (1, 12, 0), (1, 22, 0),
        (2, 12, 0), (2, 22, 0),
        (3, 12, 0), (3, 22, 0),
        (4, 12, 0), (4, 22, 0),
        (5, 12, 0), (5, 22, 0),
    }

    def __init__(self) -> None:
        super().__init__()

        self.controller = ProductController()
        self.catalog_load_db = DBManager()
        self.catalog_load_repository = CatalogLoadRepository(
            self.catalog_load_db,
        )
        self.catalog_load_repository.ensure_initial_applied_load()
        self.catalog_load_repository.restore_latest_applied()

        self.setWindowTitle("Facundo Catalog Manager")
        self.resize(1200, 700)

        self.all_products: list[Product] = []
        self.selected_categories: set[str] = set()
        self.scraping_dialog: ScrapingDialog | None = None
        self.last_scheduled_scraping: tuple[int, int, int] | None = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar producto...")
        self.search_box.textChanged.connect(self.search_products)
        layout.addWidget(self.search_box)

        self.create_filter_controls(layout)
        self.table = ProductTable(self.controller)
        layout.addWidget(self.table)

        self.product_counter = QLabel("Mostrando 0 de 0 productos")
        self.product_counter.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        layout.addWidget(self.product_counter)

        botones = QHBoxLayout()
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
            button.clicked.connect(callback)
            botones.addWidget(button)
        layout.addLayout(botones)

        self.refresh_catalog()
        self.start_scraping_scheduler()

    def create_filter_controls(self, layout: QVBoxLayout) -> None:
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("Categorías:"))
        self.category_layout = category_layout
        layout.addLayout(category_layout)

    def refresh_catalog(self) -> None:
        self.all_products = self.controller.get_products()
        self.rebuild_category_filters()
        self.apply_filters()

    def rebuild_category_filters(self) -> None:
        while self.category_layout.count() > 1:
            item = self.category_layout.takeAt(1)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        categories = sorted(
            {
                product.category.strip()
                for product in self.all_products
                if product.category.strip()
            },
            key=str.casefold,
        )
        available_categories = set(categories)
        self.selected_categories.intersection_update(available_categories)

        for category in categories:
            button = QPushButton(category)
            button.setCheckable(True)
            button.setChecked(category in self.selected_categories)
            button.setStyleSheet(
                """
                QPushButton:checked {
                    background-color: #b2ebf2;
                    border: 1px solid #4dd0e1;
                }
                """,
            )
            button.clicked.connect(
                lambda checked, value=category:
                self.toggle_category(value, checked),
            )
            self.category_layout.addWidget(button)
        self.category_layout.addStretch()

    def toggle_category(self, category: str, checked: bool) -> None:
        if checked:
            self.selected_categories.add(category)
        else:
            self.selected_categories.discard(category)
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
                if product.category in self.selected_categories
            ]

        self.table.load_products(products)
        self.update_product_counter(len(products))

    @staticmethod
    def product_matches_search(product: Product, search_text: str) -> bool:
        values = (
            product.code,
            product.name,
            product.description,
            product.category,
        )
        return any(search_text in str(value).casefold() for value in values)

    def open_scraping(self) -> None:
        """Abre el scraping sin mantenerlo siempre delante del catálogo."""
        if self.is_scraping_running():
            if self.scraping_dialog is not None:
                self.scraping_dialog.activateWindow()
                self.scraping_dialog.raise_()
            return

        self.scraping_dialog = ScrapingDialog()
        self.scraping_dialog.finished_success.connect(self.scraping_finished)
        self.scraping_dialog.finished.connect(self.scraping_dialog_closed)
        self.scraping_dialog.setModal(False)
        self.scraping_dialog.show()

    def open_scraping_history(self) -> None:
        dialog = ScrapingHistoryDialog(self)
        dialog.catalog_applied.connect(self.refresh_catalog)
        dialog.exec()

    def scraping_finished(self) -> None:
        if self.scraping_dialog is not None:
            self.scraping_dialog.setWindowTitle(
                "Actualización completada - catálogo sin cambios",
            )

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

        respuesta = QMessageBox.question(
            self,
            "Confirmar eliminación",
            "¿Desea eliminar este producto?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if respuesta == QMessageBox.StandardButton.Yes:
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
        if not filename:
            return
        ExcelExporter.export(self.controller.get_products(), filename)

    def export_pdf(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar PDF",
            "catalogo.pdf",
            "PDF (*.pdf)",
        )
        if not filename:
            return
        PDFExporter.export(self.controller.get_products(), filename)

    def closeEvent(self, event) -> None:
        if hasattr(self, "scraping_scheduler"):
            self.scraping_scheduler.stop()
        if self.scraping_dialog is not None:
            self.scraping_dialog.close()
        self.catalog_load_db.close()
        super().closeEvent(event)
