from typing import ClassVar

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
)

from controllers.product_controller import ProductController
from models.product import Product


class NumericTableWidgetItem(QTableWidgetItem):
    """Item de tabla que ordena utilizando un valor numérico."""

    def __init__(self, text: str, value: int | float) -> None:
        super().__init__(text)
        self.setData(Qt.ItemDataRole.UserRole, value)

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, QTableWidgetItem):
            self_value = self.data(Qt.ItemDataRole.UserRole)
            other_value = other.data(Qt.ItemDataRole.UserRole)
            if self_value is not None and other_value is not None:
                try:
                    return float(self_value) < float(other_value)
                except (TypeError, ValueError):
                    pass
        return super().__lt__(other)


class ProductHeader(QHeaderView):
    """Encabezado con resaltado de todas las columnas con orden activo."""

    def __init__(self, parent: QTableWidget) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.active_sections: set[int] = set()
        self.setMinimumHeight(64)
        self.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSectionsClickable(True)
        self.setSortIndicatorShown(False)
        self.setTextElideMode(Qt.TextElideMode.ElideNone)

    def set_active_sections(self, sections: set[int]) -> None:
        self.active_sections = set(sections)
        self.viewport().update()

    def paintSection(self, painter: QPainter, rect, logical_index: int) -> None:
        painter.save()
        if logical_index in self.active_sections:
            painter.fillRect(rect, self.palette().highlight())
        painter.restore()
        super().paintSection(painter, rect, logical_index)


class ProductTable(QTableWidget):
    """Tabla principal del catálogo de productos."""

    IMAGE_COLUMN = 0
    CODE_COLUMN = 1
    NAME_COLUMN = 2
    DETAIL_COLUMN = 3
    CATEGORY_COLUMN = 4
    STOCK_COLUMN = 5
    PRICE_SAMPLE_COLUMN = 6
    PRICE_HUNDRED_COLUMN = 7
    PRICE_THOUSAND_COLUMN = 8

    SORTABLE_COLUMNS: ClassVar[set[int]] = {
        CODE_COLUMN,
        NAME_COLUMN,
        DETAIL_COLUMN,
        CATEGORY_COLUMN,
        STOCK_COLUMN,
        PRICE_SAMPLE_COLUMN,
        PRICE_HUNDRED_COLUMN,
        PRICE_THOUSAND_COLUMN,
    }

    NUMERIC_COLUMNS: ClassVar[set[int]] = {
        STOCK_COLUMN,
        PRICE_SAMPLE_COLUMN,
        PRICE_HUNDRED_COLUMN,
        PRICE_THOUSAND_COLUMN,
    }

    HEADER_LABELS: ClassVar[list[str]] = [
        "Imagen",
        "Código",
        "Nombre",
        "Detalle",
        "Categoría",
        "Stock",
        "Precio muestra",
        "Precio ciento",
        "Precio millar",
    ]

    CURRENCY_SYMBOL: ClassVar[str] = "S/"

    def __init__(self, controller: ProductController) -> None:
        super().__init__()

        self.controller = controller
        self._sort_states: dict[int, Qt.SortOrder] = {}
        self._products: list[Product] = []

        self.setColumnCount(9)
        self.setHorizontalHeaderLabels(self.HEADER_LABELS)
        self._setup_table()
        self._setup_header()
        self.load_products()

    def _setup_table(self) -> None:
        self.setSortingEnabled(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setWordWrap(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(140)
        self.setShowGrid(True)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #d9d9d9;
                selection-background-color: #cceff1;
                selection-color: #000000;
            }

            QTableWidget::item {
                padding: 6px;
                font-size: 14px;
            }

            QHeaderView::section {
                min-height: 64px;
                padding: 6px 6px;
                font-size: 18px;
                font-weight: bold;
                text-align: center;
            }
            """,
        )

    def _setup_header(self) -> None:
        header = ProductHeader(self)
        self.setHorizontalHeader(header)
        header.sectionClicked.connect(self._handle_header_click)
        header.setStretchLastSection(False)
        header.setDefaultSectionSize(135)

        for column in range(self.columnCount()):
            resize_mode = (
                QHeaderView.ResizeMode.Fixed
                if column == self.IMAGE_COLUMN
                else QHeaderView.ResizeMode.Interactive
            )
            header.setSectionResizeMode(column, resize_mode)

        self.setColumnWidth(self.IMAGE_COLUMN, 150)
        self.setColumnWidth(self.CODE_COLUMN, 110)
        self.setColumnWidth(self.NAME_COLUMN, 210)
        self.setColumnWidth(self.DETAIL_COLUMN, 300)
        self.setColumnWidth(self.CATEGORY_COLUMN, 160)
        self.setColumnWidth(self.STOCK_COLUMN, 95)
        self.setColumnWidth(self.PRICE_SAMPLE_COLUMN, 135)
        self.setColumnWidth(self.PRICE_HUNDRED_COLUMN, 135)
        self.setColumnWidth(self.PRICE_THOUSAND_COLUMN, 135)

    def _handle_header_click(self, column: int) -> None:
        """Ciclo por columna: descendente, ascendente y desactivado."""
        if column not in self.SORTABLE_COLUMNS:
            return

        current = self._sort_states.get(column)
        if current is None:
            self._sort_states[column] = Qt.SortOrder.DescendingOrder
        elif current == Qt.SortOrder.DescendingOrder:
            self._sort_states[column] = Qt.SortOrder.AscendingOrder
        else:
            del self._sort_states[column]

        self._apply_current_sort()

    def _apply_current_sort(self) -> None:
        products = list(self._products)
        if self._sort_states:
            for column in self._sort_states:
                reverse = (
                    self._sort_states[column]
                    == Qt.SortOrder.DescendingOrder
                )
                products.sort(
                    key=lambda product, selected_column=column:
                    self._product_sort_value(product, selected_column),
                    reverse=reverse,
                )

        self._render_products(products)
        self._update_sort_header_labels()

    def _product_sort_value(self, product: Product, column: int):
        values = {
            self.CODE_COLUMN: product.code.casefold(),
            self.NAME_COLUMN: product.name.casefold(),
            self.DETAIL_COLUMN: product.description.casefold(),
            self.CATEGORY_COLUMN: product.category.casefold(),
            self.STOCK_COLUMN: product.stock,
            self.PRICE_SAMPLE_COLUMN: product.price_sample,
            self.PRICE_HUNDRED_COLUMN: product.price_hundred,
            self.PRICE_THOUSAND_COLUMN: product.price_thousand,
        }
        return values[column]

    def product_header(self) -> ProductHeader:
        header = self.horizontalHeader()
        if not isinstance(header, ProductHeader):
            raise TypeError(
                "El encabezado de ProductTable debe ser ProductHeader.",
            )
        return header

    def _update_sort_header_labels(self) -> None:
        labels = self.HEADER_LABELS.copy()
        for column, order in self._sort_states.items():
            arrow = " ↑" if order == Qt.SortOrder.AscendingOrder else " ↓"
            labels[column] += arrow

        self.setHorizontalHeaderLabels(labels)
        self.product_header().set_active_sections(set(self._sort_states))

    def load_products(self, productos: list[Product] | None = None) -> None:
        """Carga los productos y conserva los filtros de orden activos."""
        if productos is None:
            productos = self.controller.get_products()

        self._products = list(productos)
        self._apply_current_sort()

    def _render_products(self, products: list[Product]) -> None:
        self.setSortingEnabled(False)
        self.clearContents()
        self.setRowCount(len(products))

        for fila, producto in enumerate(products):
            self._add_product_row(fila, producto)

        self._adjust_table_rows()

    def _add_product_row(self, fila: int, producto: Product) -> None:
        image = QLabel()
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setMinimumSize(134, 134)

        if producto.image_path:
            pixmap = QPixmap(producto.image_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    128,
                    128,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                image.setPixmap(pixmap)

        self.setCellWidget(fila, self.IMAGE_COLUMN, image)

        item_code = QTableWidgetItem(producto.code)
        item_code.setData(Qt.ItemDataRole.UserRole, producto.id)
        item_code.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(fila, self.CODE_COLUMN, item_code)

        name_item = QTableWidgetItem(producto.name)
        name_item.setToolTip(producto.name)
        name_item.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        )
        self.setItem(fila, self.NAME_COLUMN, name_item)

        detail_item = QTableWidgetItem(producto.description)
        detail_item.setToolTip(producto.description)
        detail_item.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        )
        self.setItem(fila, self.DETAIL_COLUMN, detail_item)

        category_item = QTableWidgetItem(producto.category)
        category_item.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        )
        self.setItem(fila, self.CATEGORY_COLUMN, category_item)

        stock_item = NumericTableWidgetItem(str(producto.stock), producto.stock)
        stock_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(fila, self.STOCK_COLUMN, stock_item)

        self._set_price_item(
            fila,
            self.PRICE_SAMPLE_COLUMN,
            producto.price_sample,
        )
        self._set_price_item(
            fila,
            self.PRICE_HUNDRED_COLUMN,
            producto.price_hundred,
        )
        self._set_price_item(
            fila,
            self.PRICE_THOUSAND_COLUMN,
            producto.price_thousand,
        )

    def _set_price_item(self, row: int, column: int, value: float) -> None:
        item = NumericTableWidgetItem(
            f"S/ {value:,.2f}",
            value,
        )
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self.setItem(row, column, item)

    def _adjust_table_rows(self) -> None:
        """Ajusta el alto al contenido, manteniendo límites razonables."""
        self.resizeRowsToContents()
        for row in range(self.rowCount()):
            height = max(140, min(self.rowHeight(row), 220))
            self.setRowHeight(row, height)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)

        available_width = self.viewport().width()
        if available_width <= 0:
            return

        fixed_width = (
            self.columnWidth(self.IMAGE_COLUMN)
            + self.columnWidth(self.CODE_COLUMN)
            + self.columnWidth(self.STOCK_COLUMN)
            + self.columnWidth(self.PRICE_SAMPLE_COLUMN)
            + self.columnWidth(self.PRICE_HUNDRED_COLUMN)
            + self.columnWidth(self.PRICE_THOUSAND_COLUMN)
        )

        remaining_width = max(available_width - fixed_width, 600)

        name_width = int(remaining_width * 0.27)
        detail_width = int(remaining_width * 0.43)
        category_width = max(int(remaining_width * 0.30), 120)

        self.setColumnWidth(self.NAME_COLUMN, name_width)
        self.setColumnWidth(self.DETAIL_COLUMN, detail_width)
        self.setColumnWidth(self.CATEGORY_COLUMN, category_width)
