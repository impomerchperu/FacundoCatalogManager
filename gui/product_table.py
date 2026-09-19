import textwrap
from typing import ClassVar

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
)

from controllers.product_controller import ProductController
from models.product import Product
from services.scraping.category_name_normalizer import split_category_names


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


class ProductImageDelegate(QStyledItemDelegate):
    """Pinta la imagen sobre todo el rectángulo visible de la celda."""

    DEFAULT_SIZE = 160
    IMAGE_ROLE = int(Qt.ItemDataRole.UserRole) + 1

    def paint(self, painter: QPainter, option, index) -> None:
        super().paint(painter, option, index)

        pixmap = index.data(self.IMAGE_ROLE)
        if not isinstance(pixmap, QPixmap) or pixmap.isNull():
            return

        target_size = option.rect.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            return

        scaled = pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        left = max((scaled.width() - target_size.width()) // 2, 0)
        top = max((scaled.height() - target_size.height()) // 2, 0)
        cropped = scaled.copy(
            left,
            top,
            target_size.width(),
            target_size.height(),
        )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(option.rect, cropped)
        painter.restore()

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index,
    ) -> QSize:
        del option, index
        return QSize(self.DEFAULT_SIZE, self.DEFAULT_SIZE)


class ProductTable(QTableWidget):
    """Tabla principal del catálogo de productos."""

    CONTENT_SIDE_PADDING = 4
    CATEGORY_LINE_MAX_LENGTH = 26
    DEFAULT_IMAGE_CELL_SIZE = 160
    IMAGE_SIZE = DEFAULT_IMAGE_CELL_SIZE

    IMAGE_COLUMN = 0
    CODE_COLUMN = 1
    NAME_COLUMN = 2
    DETAIL_COLUMN = 3
    CATEGORY_COLUMN = 4
    STOCK_COLUMN = 5
    PRICE_SAMPLE_COLUMN = 6
    PRICE_HUNDRED_COLUMN = 7
    PRICE_THOUSAND_COLUMN = 8

    MIN_COLUMN_WIDTHS: ClassVar[dict[int, int]] = {
        IMAGE_COLUMN: DEFAULT_IMAGE_CELL_SIZE,
        CODE_COLUMN: 80,
        NAME_COLUMN: 120,
        DETAIL_COLUMN: 180,
        CATEGORY_COLUMN: 110,
        STOCK_COLUMN: 120,
        PRICE_SAMPLE_COLUMN: 105,
        PRICE_HUNDRED_COLUMN: 105,
        PRICE_THOUSAND_COLUMN: 105,
    }

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

    HEADER_LABELS: ClassVar[list[str]] = [
        "Imagen",
        "Código",
        "Nombre",
        "Detalle",
        "Categoría",
        "Stock",
        "Precio\nmuestra",
        "Precio\nciento",
        "Precio\nmillar",
    ]

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
        self.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(self.DEFAULT_IMAGE_CELL_SIZE)
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
                padding: 4px;
                font-size: 16px;
            }
            QHeaderView::section {
                min-height: 64px;
                padding: 4px;
                font-size: 18px;
                font-weight: bold;
                text-align: center;
            }
            """,
        )

    def _setup_header(self) -> None:
        header = ProductHeader(self)
        self.setHorizontalHeader(header)
        self.setItemDelegateForColumn(
            self.IMAGE_COLUMN,
            ProductImageDelegate(self),
        )
        header.sectionClicked.connect(self._handle_header_click)
        header.setStretchLastSection(False)
        header.setDefaultSectionSize(110)
        for column in range(self.columnCount()):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Interactive,
            )
        for column, width in self.MIN_COLUMN_WIDTHS.items():
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
        """Conserva la API de búsqueda sin aplicar resaltado visual."""
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
        self._fit_columns_to_content()
        self._adjust_table_rows()

    def _add_product_row(self, row: int, product: Product) -> None:
        image_item = QTableWidgetItem()
        if product.image_path:
            pixmap = QPixmap(product.image_path)
            if not pixmap.isNull():
                image_item.setData(ProductImageDelegate.IMAGE_ROLE, pixmap)
        self.setItem(row, self.IMAGE_COLUMN, image_item)

        item_code = QTableWidgetItem(product.code)
        item_code.setData(Qt.ItemDataRole.UserRole, product.id)
        item_code.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, self.CODE_COLUMN, item_code)
        self._set_text_item(row, self.NAME_COLUMN, product.name)
        self._set_text_item(row, self.DETAIL_COLUMN, product.description)
        self._set_category_item(row, product.category)
        self._set_stock_widget(row, product)
        self._set_price_item(row, self.PRICE_SAMPLE_COLUMN, product.price_sample)
        self._set_price_item(row, self.PRICE_HUNDRED_COLUMN, product.price_hundred)
        self._set_price_item(row, self.PRICE_THOUSAND_COLUMN, product.price_thousand)

    def _set_text_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setToolTip(text)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        )
        self.setItem(row, column, item)

    def _set_category_item(self, row: int, category: str) -> None:
        """Muestra cada categoría del producto en una línea independiente."""
        self._set_text_item(
            row,
            self.CATEGORY_COLUMN,
            self._format_categories(category),
        )

    @classmethod
    def _format_categories(cls, category: str) -> str:
        categories = split_category_names(category)
        if not categories:
            return "—"

        lines: list[str] = []
        for category_name in categories:
            lines.extend(
                textwrap.wrap(
                    category_name,
                    width=cls.CATEGORY_LINE_MAX_LENGTH,
                    break_long_words=False,
                    break_on_hyphens=False,
                ),
            )
        return "\n".join(lines)

    def _set_stock_widget(self, row: int, product: Product) -> None:
        """Muestra cada color y su stock en una fila dentro de Stock."""
        color_stock = self._ordered_color_stock(product)
        if not color_stock:
            item = NumericTableWidgetItem(str(product.stock), product.stock)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, self.STOCK_COLUMN, item)
            return

        label = QLabel()
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        label.setWordWrap(True)

        rows = [
            "<table width='100%' cellspacing='0' cellpadding='1'>",
        ]
        for color, stock in color_stock:
            rows.append(
                "<tr>"
                f"<td align='left'>{self._escape_html(color)}</td>"
                f"<td align='right'>{stock:,}</td>"
                "</tr>"
            )
        rows.append("</table>")
        label.setText("".join(rows))
        label.setToolTip("\n".join(f"{color}: {stock}" for color, stock in color_stock))
        self.setCellWidget(row, self.STOCK_COLUMN, label)

    @staticmethod
    def _ordered_color_stock(product: Product) -> list[tuple[str, int]]:
        """Devuelve el stock por color conservando el orden recibido."""
        result: list[tuple[str, int]] = []
        seen: set[str] = set()
        for color, stock in product.color_stock.items():
            normalized = str(color).strip()
            key = normalized.casefold()
            if not normalized or key in seen:
                continue
            seen.add(key)
            result.append((normalized, max(int(stock), 0)))
        return result

    @staticmethod
    def _escape_html(value: str) -> str:
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def _set_price_item(self, row: int, column: int, value: float) -> None:
        item = NumericTableWidgetItem(f"S/ {value:,.2f}", value)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter,
        )
        self.setItem(row, column, item)

    def _adjust_table_rows(self) -> None:
        self.resizeRowsToContents()
        image_size = max(
            self.columnWidth(self.IMAGE_COLUMN),
            self.DEFAULT_IMAGE_CELL_SIZE,
        )
        for row in range(self.rowCount()):
            self.setRowHeight(
                row,
                max(image_size, self.rowHeight(row)),
            )

    def _preferred_column_widths(self, header: QHeaderView) -> list[int]:
        self.resizeColumnsToContents()
        return [
            max(
                header.sectionSize(column),
                self.MIN_COLUMN_WIDTHS[column],
            )
            for column in range(self.columnCount())
        ]

    def _fit_columns_to_content(self) -> None:
        if getattr(self, "_is_fitting_columns", False):
            return

        self._is_fitting_columns = True
        try:
            header = self.horizontalHeader()
            preferred_widths = self._preferred_column_widths(header)
            minimum_widths = [
                self.MIN_COLUMN_WIDTHS[column]
                for column in range(self.columnCount())
            ]
            minimum_total = sum(minimum_widths)
            available_width = self.viewport().width()
            target_width = max(available_width, minimum_total)
            widths = self._allocate_column_widths(
                preferred_widths,
                minimum_widths,
                target_width,
                growable_columns=set(range(1, self.columnCount())),
            )

            self.setMinimumWidth(
                minimum_total
                + (2 * self.frameWidth())
                + self.verticalScrollBar().sizeHint().width(),
            )
            for column, width in enumerate(widths):
                header.resizeSection(column, width)
        finally:
            self._is_fitting_columns = False

    @staticmethod
    def _allocate_column_widths(
        preferred_widths: list[int],
        minimum_widths: list[int],
        target_width: int,
        *,
        growable_columns: set[int],
    ) -> list[int]:
        minimum_total = sum(minimum_widths)
        target_width = max(target_width, minimum_total)
        widths = preferred_widths.copy()

        growable_preferred_total = sum(
            preferred_widths[column] for column in growable_columns
        )
        fixed_preferred_total = sum(
            preferred_width
            for column, preferred_width in enumerate(preferred_widths)
            if column not in growable_columns
        )
        growable_minimum_total = sum(
            minimum_widths[column] for column in growable_columns
        )
        growable_target = max(
            target_width - fixed_preferred_total,
            growable_minimum_total,
        )

        if growable_preferred_total <= growable_target:
            extra_width = growable_target - growable_preferred_total
            if growable_preferred_total <= 0:
                return widths

            distributed = 0
            ordered_columns = sorted(growable_columns)
            for position, column in enumerate(ordered_columns):
                if position == len(ordered_columns) - 1:
                    additional = extra_width - distributed
                else:
                    additional = round(
                        extra_width
                        * preferred_widths[column]
                        / growable_preferred_total,
                    )
                    distributed += additional
                widths[column] += additional
            return widths

        reducible_total = sum(
            max(preferred_widths[column] - minimum_widths[column], 0)
            for column in growable_columns
        )
        if reducible_total <= 0:
            return widths

        reduction_target = growable_preferred_total - growable_target
        reduced = 0
        ordered_columns = sorted(growable_columns)
        for position, column in enumerate(ordered_columns):
            room = max(
                preferred_widths[column] - minimum_widths[column],
                0,
            )
            if position == len(ordered_columns) - 1:
                reduction = reduction_target - reduced
            else:
                reduction = round(
                    reduction_target * room / reducible_total,
                )
                reduced += reduction
            widths[column] = max(
                preferred_widths[column] - reduction,
                minimum_widths[column],
            )

        return widths

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if getattr(self, "_is_fitting_columns", False):
            return
        self._fit_columns_to_content()
        self._adjust_table_rows()
