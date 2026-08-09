import html
import re
from typing import ClassVar

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QAbstractTextDocumentLayout,
    QPalette,
    QPainter,
    QPixmap,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
)

from controllers.product_controller import ProductController
from models.product import Product


class SearchHighlightDelegate(QStyledItemDelegate):
    """Pinta coincidencias de búsqueda sin perder el comportamiento de la tabla."""

    HIGHLIGHT_COLOR = "#b2ebf2"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.search_text = ""

    def set_search_text(self, text: str) -> None:
        self.search_text = text.strip()

    def paint(self, painter: QPainter, option, index) -> None:
        if not self.search_text:
            super().paint(painter, option, index)
            return
        value = index.data(Qt.ItemDataRole.DisplayRole)
        if value is None:
            super().paint(painter, option, index)
            return
        text = str(value)
        if self.search_text.casefold() not in text.casefold():
            super().paint(painter, option, index)
            return

        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)
        style_option.text = ""
        if style_option.widget is not None:
            style_option.widget.style().drawControl(
                QStyle.ControlElement.CE_ItemViewItem,
                style_option,
                painter,
                style_option.widget,
            )

        highlighted = re.sub(
            re.escape(self.search_text),
            lambda match: (
                f'<span style="background:{self.HIGHLIGHT_COLOR};">'
                f"{html.escape(match.group(0))}</span>"
            ),
            html.escape(text),
            flags=re.IGNORECASE,
        )

        document = QTextDocument()
        document.setDefaultFont(option.font)
        document.setHtml(highlighted)
        document.setTextWidth(max(option.rect.width() - 12, 1))

        context = QAbstractTextDocumentLayout.PaintContext()
        if option.state & QStyle.StateFlag.State_Selected:
            context.palette.setColor(
                QPalette.ColorRole.Text,
                option.palette.color(QPalette.ColorRole.HighlightedText),
            )

        rect = QRectF(option.rect.adjusted(6, 4, -6, -4))
        painter.save()
        painter.setClipRect(rect)
        painter.translate(rect.left(), rect.top())
        document.documentLayout().draw(painter, context)
        painter.restore()


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

    def paintSection(self, painter: QPainter, rect, logical_index: int) -> None:
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
        "Imagen", "Código", "Nombre", "Detalle", "Categoría", "Stock",
        "Colores", "Precio\nmuestra", "Precio\nciento", "Precio\nmillar",
    ]

    COLOR_NAMES: ClassVar[dict[str, str]] = {
        "rojo": "#ef9a9a", "red": "#ef9a9a",
        "azul": "#90caf9", "blue": "#90caf9",
        "verde": "#a5d6a7", "green": "#a5d6a7",
        "amarillo": "#fff59d", "yellow": "#fff59d",
        "naranja": "#ffcc80", "orange": "#ffcc80",
        "rosado": "#f8bbd0", "rosa": "#f8bbd0", "pink": "#f8bbd0",
        "morado": "#ce93d8", "violeta": "#ce93d8", "purple": "#ce93d8",
        "negro": "#616161", "black": "#616161",
        "blanco": "#ffffff", "white": "#ffffff",
        "gris": "#bdbdbd", "gray": "#bdbdbd", "grey": "#bdbdbd",
        "beige": "#d7ccc8", "marrón": "#a1887f", "marron": "#a1887f",
        "brown": "#a1887f", "dorado": "#d4af37", "gold": "#d4af37",
        "plateado": "#cfd8dc", "silver": "#cfd8dc",
        "transparente": "#f5f5f5", "transparent": "#f5f5f5",
    }

    def __init__(self, controller: ProductController) -> None:
        super().__init__()
        self.controller = controller
        self._sort_states: dict[int, Qt.SortOrder] = {}
        self._products: list[Product] = []
        self._search_text = ""
        self._search_delegate = SearchHighlightDelegate(self)
        self.setItemDelegate(self._search_delegate)
        self.setColumnCount(len(self.HEADER_LABELS))
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
            QTableWidget { gridline-color: #d9d9d9; selection-background-color: #cceff1; selection-color: #000000; }
            QTableWidget::item { padding: 6px; font-size: 16px; }
            QHeaderView::section { min-height: 64px; padding: 4px 6px; font-size: 18px; font-weight: bold; text-align: center; }
            """,
        )

    def _setup_header(self) -> None:
        header = ProductHeader(self)
        self.setHorizontalHeader(header)
        header.sectionClicked.connect(self._handle_header_click)
        header.setStretchLastSection(False)
        header.setDefaultSectionSize(135)
        for column in range(self.columnCount()):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Fixed if column == self.IMAGE_COLUMN else QHeaderView.ResizeMode.Interactive,
            )
        widths = {
            self.IMAGE_COLUMN: 180, self.CODE_COLUMN: 110, self.NAME_COLUMN: 230,
            self.DETAIL_COLUMN: 320, self.CATEGORY_COLUMN: 180, self.STOCK_COLUMN: 95,
            self.COLORS_COLUMN: 180, self.PRICE_SAMPLE_COLUMN: 140,
            self.PRICE_HUNDRED_COLUMN: 140, self.PRICE_THOUSAND_COLUMN: 140,
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
                key=lambda product, selected_column=column: self._product_sort_value(product, selected_column),
                reverse=order == Qt.SortOrder.DescendingOrder,
            )
        self._render_products(products)
        self._update_sort_header_labels()

    def _product_sort_value(self, product: Product, column: int):
        values = {
            self.CODE_COLUMN: product.code.casefold(), self.NAME_COLUMN: product.name.casefold(),
            self.DETAIL_COLUMN: product.description.casefold(), self.CATEGORY_COLUMN: product.category.casefold(),
            self.STOCK_COLUMN: product.stock, self.COLORS_COLUMN: ", ".join(product.colors).casefold(),
            self.PRICE_SAMPLE_COLUMN: product.price_sample, self.PRICE_HUNDRED_COLUMN: product.price_hundred,
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
            labels[column] += " ↑" if order == Qt.SortOrder.AscendingOrder else " ↓"
        self.setHorizontalHeaderLabels(labels)
        self.product_header().set_active_sections(set(self._sort_states))

    def set_search_text(self, text: str) -> None:
        self._search_text = text.strip()
        self._search_delegate.set_search_text(self._search_text)
        self.viewport().update()

    def load_products(self, products: list[Product] | None = None) -> None:
        self._products = list(products if products is not None else self.controller.get_products())
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
                image.setPixmap(pixmap.scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.setCellWidget(row, self.IMAGE_COLUMN, image)

        item_code = QTableWidgetItem(product.code)
        item_code.setData(Qt.ItemDataRole.UserRole, product.id)
        item_code.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, self.CODE_COLUMN, item_code)
        self._set_text_item(row, self.NAME_COLUMN, product.name)
        self._set_text_item(row, self.DETAIL_COLUMN, product.description)
        self._set_text_item(row, self.CATEGORY_COLUMN, product.category)

        stock_item = NumericTableWidgetItem(str(product.stock), product.stock)
        stock_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, self.STOCK_COLUMN, stock_item)
        self._set_colors_widget(row, product)
        self._set_price_item(row, self.PRICE_SAMPLE_COLUMN, product.price_sample)
        self._set_price_item(row, self.PRICE_HUNDRED_COLUMN, product.price_hundred)
        self._set_price_item(row, self.PRICE_THOUSAND_COLUMN, product.price_thousand)

    def _set_text_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setToolTip(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.setItem(row, column, item)

    def _set_colors_widget(self, row: int, product: Product) -> None:
        colors = list(product.colors) or list(product.color_stock)
        if not colors:
            item = QTableWidgetItem("—")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, self.COLORS_COLUMN, item)
            return
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        parts = []
        for color in colors:
            stock = product.color_stock.get(color)
            stock_text = f" — {stock}" if stock is not None else ""
            background = self._color_background(color)
            foreground = "#ffffff" if self._is_dark_color(background) else "#000000"
            parts.append(f'<span style="background:{background}; color:{foreground}; padding:2px 5px;">{self._escape_html(color)}{stock_text}</span>')
        label.setText("<br>".join(parts))
        label.setToolTip("\n".join(f"{color}: {product.color_stock[color]}" if color in product.color_stock else color for color in colors))
        self.setCellWidget(row, self.COLORS_COLUMN, label)

    @classmethod
    def _color_background(cls, color: str) -> str:
        key = color.casefold().strip()
        if key in cls.COLOR_NAMES:
            return cls.COLOR_NAMES[key]
        for name, value in cls.COLOR_NAMES.items():
            if name in key:
                return value
        return "#e0e0e0"

    @staticmethod
    def _is_dark_color(color: str) -> bool:
        value = color.lstrip("#")
        if len(value) != 6:
            return False
        red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
        return (red * 299 + green * 587 + blue * 114) < 140000

    @staticmethod
    def _escape_html(value: str) -> str:
        return html.escape(str(value))

    def _set_price_item(self, row: int, column: int, value: float) -> None:
        item = NumericTableWidgetItem(f"S/ {value:,.2f}", value)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        self.setItem(row, column, item)

    def _adjust_table_rows(self) -> None:
        self.resizeRowsToContents()
        for row in range(self.rowCount()):
            self.setRowHeight(row, max(140, min(self.rowHeight(row), 260)))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        available_width = self.viewport().width()
        if available_width <= 0:
            return
        fixed_width = sum(
            self.columnWidth(column)
            for column in (
                self.IMAGE_COLUMN, self.CODE_COLUMN, self.STOCK_COLUMN, self.COLORS_COLUMN,
                self.PRICE_SAMPLE_COLUMN, self.PRICE_HUNDRED_COLUMN, self.PRICE_THOUSAND_COLUMN,
            )
        )
        remaining = max(available_width - fixed_width, 540)
        self.setColumnWidth(self.NAME_COLUMN, int(remaining * 0.29))
        self.setColumnWidth(self.DETAIL_COLUMN, int(remaining * 0.43))
        self.setColumnWidth(self.CATEGORY_COLUMN, max(int(remaining * 0.28), 120))
        self._adjust_table_rows()
