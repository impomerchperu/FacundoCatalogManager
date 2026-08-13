import html
from typing import ClassVar

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
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

    ACTIVE_COLOR = "#b2ebf2"

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

    def paintSection(self, painter, rect, logical_index: int) -> None:
        painter.save()
        if logical_index in self.active_sections:
            painter.fillRect(rect, self.ACTIVE_COLOR)
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
    COLORS_COLUMN = 6
    PRICE_SAMPLE_COLUMN = 7
    PRICE_HUNDRED_COLUMN = 8
    PRICE_THOUSAND_COLUMN = 9

    SORTABLE_COLUMNS: ClassVar[set[int]] = {
        CODE_COLUMN,
        NAME_COLUMN,
        DETAIL_COLUMN,
        CATEGORY_COLUMN,
        STOCK_COLUMN,
        COLORS_COLUMN,
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
        "Colores",
        "Precio\nmuestra",
        "Precio\nciento",
        "Precio\nmillar",
    ]

    COLOR_NAMES: ClassVar[dict[str, str]] = {
        "rojo": "#ef9a9a", "red": "#ef9a9a",
        "azul": "#90caf9", "blue": "#90caf9",
        "verde": "#a5d6a7", "green": "#a5d6a7",
        "amarillo": "#fff59d", "yellow": "#fff59d",
        "naranja": "#ffcc80", "orange": "#ffcc80",
        "rosado": "#f8bbd0", "rosa": "#f8bbd0", "pink": "#f8bbd0",
        "morado": "#ce93d8", "violeta": "#ce93d8", "purple": "#ce93d8",
        "negro": "#616161", "black": "#616161", "blanco": "#ffffff",
        "white": "#ffffff", "gris": "#bdbdbd", "gray": "#bdbdbd",
        "grey": "#bdbdbd", "beige": "#d7ccc8", "marrón": "#a1887f",
        "marron": "#a1887f", "brown": "#a1887f", "dorado": "#d4af37",
        "gold": "#d4af37", "plateado": "#cfd8dc", "silver": "#cfd8dc",
        "transparente": "#f5f5f5", "transparent": "#f5f5f5",
    }

    def __init__(self, controller: ProductController) -> None:
        super().__init__()
        self.controller = controller
        self._sort_states: dict[int, Qt.SortOrder] = {}
        self._products: list[Product] = []
        self._search_text = ""
        self.setColumnCount(len(self.HEADER_LABELS))
        self.setHorizontalHeaderLabels(self.HEADER_LABELS)
        self._setup_table()
        self._setup_header()

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
                font-size: 16px;
            }
            QHeaderView::section {
                min-height: 64px;
                padding: 4px 6px;
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
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)

        widths = {
            self.IMAGE_COLUMN: 180,
            self.CODE_COLUMN: 120,
            self.NAME_COLUMN: 260,
            self.DETAIL_COLUMN: 300,
            self.CATEGORY_COLUMN: 220,
            self.STOCK_COLUMN: 100,
            self.COLORS_COLUMN: 220,
            self.PRICE_SAMPLE_COLUMN: 140,
            self.PRICE_HUNDRED_COLUMN: 140,
            self.PRICE_THOUSAND_COLUMN: 140,
        }
        for column, width in widths.items():
            self.setColumnWidth(column, width)

    def _handle_header_click(self, column: int) -> None:
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
        for column, order in reversed(list(self._sort_states.items())):
            products.sort(
                key=lambda product, selected_column=column: self._product_sort_value(
                    product,
                    selected_column,
                ),
                reverse=order == Qt.SortOrder.DescendingOrder,
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
            self.COLORS_COLUMN: ", ".join(product.colors).casefold(),
            self.PRICE_SAMPLE_COLUMN: product.price_sample,
            self.PRICE_HUNDRED_COLUMN: product.price_hundred,
            self.PRICE_THOUSAND_COLUMN: product.price_thousand,
        }
        return values[column]

    def product_header(self) -> ProductHeader:
        header = self.horizontalHeader()
        if not isinstance(header, ProductHeader):
            raise TypeError("El encabezado de ProductTable debe ser ProductHeader.")
        return header

    def _update_sort_header_labels(self) -> None:
        labels = self.HEADER_LABELS.copy()
        for column, order in self._sort_states.items():
            labels[column] += (
                " ↑" if order == Qt.SortOrder.AscendingOrder else " ↓"
            )
        self.setHorizontalHeaderLabels(labels)
        self.product_header().set_active_sections(set(self._sort_states))

    def set_search_text(self, text: str) -> None:
        self._search_text = text.strip()

    def load_products(self, products: list[Product] | None = None) -> None:
        source = products if products is not None else self.controller.get_products()
        self._products = list(source)
        self._apply_current_sort()

    def _render_products(self, products: list[Product]) -> None:
        self.setSortingEnabled(False)
        self.clearContents()
        self.setRowCount(len(products))
        for row, product in enumerate(products):
            self._add_product_row(row, product)
        self._adjust_table_rows()

    def _add_product_row(self, row: int, product: Product) -> None:
        image = QLabel()
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setMinimumSize(164, 164)
        if product.image_path:
            pixmap = QPixmap(product.image_path)
            if not pixmap.isNull():
                image.setPixmap(
                    pixmap.scaled(
                        160,
                        160,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    ),
                )
        self.setCellWidget(row, self.IMAGE_COLUMN, image)

        values = [
            product.code,
            product.name,
            self._format_detail(product.description),
            product.category,
            str(product.stock),
            self._format_colors(product.colors),
            f"{product.price_sample:,.2f}",
            f"{product.price_hundred:,.2f}",
            f"{product.price_thousand:,.2f}",
        ]
        columns = [
            self.CODE_COLUMN,
            self.NAME_COLUMN,
            self.DETAIL_COLUMN,
            self.CATEGORY_COLUMN,
            self.STOCK_COLUMN,
            self.COLORS_COLUMN,
            self.PRICE_SAMPLE_COLUMN,
            self.PRICE_HUNDRED_COLUMN,
            self.PRICE_THOUSAND_COLUMN,
        ]
        numeric_columns = {
            self.STOCK_COLUMN,
            self.PRICE_SAMPLE_COLUMN,
            self.PRICE_HUNDRED_COLUMN,
            self.PRICE_THOUSAND_COLUMN,
        }
        for column, value in zip(columns, values, strict=True):
            if column in numeric_columns:
                numeric_value = (
                    product.stock
                    if column == self.STOCK_COLUMN
                    else self._price_for_column(product, column)
                )
                item = NumericTableWidgetItem(value, numeric_value)
            else:
                item = QTableWidgetItem(value)
            if column == self.CODE_COLUMN:
                item.setData(Qt.ItemDataRole.UserRole, product.product_id)
            self.setItem(row, column, item)

    @staticmethod
    def _price_for_column(product: Product, column: int) -> float:
        if column == ProductTable.PRICE_SAMPLE_COLUMN:
            return product.price_sample
        if column == ProductTable.PRICE_HUNDRED_COLUMN:
            return product.price_hundred
        return product.price_thousand

    @staticmethod
    def _format_detail(value: str) -> str:
        return html.unescape(str(value or ""))

    @staticmethod
    def _format_colors(colors: list[str]) -> str:
        return ", ".join(str(color) for color in colors)

    def _adjust_table_rows(self) -> None:
        self.resizeRowsToContents()
        for row in range(self.rowCount()):
            self.setRowHeight(row, max(self.rowHeight(row), 170))
