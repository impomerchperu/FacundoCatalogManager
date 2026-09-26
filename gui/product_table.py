from typing import ClassVar

from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap, QPixmapCache
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
)

from config.runtime_paths import resolve_data_path
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

    ACTIVE_COLOR = "#d8edf7"

    def __init__(self, parent: QTableWidget) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.active_sections: set[int] = set()
        self.setMinimumHeight(56)
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

    DEFAULT_SIZE = 180
    IMAGE_ROLE = int(Qt.ItemDataRole.UserRole) + 1

    def paint(self, painter: QPainter, option, index) -> None:
        super().paint(painter, option, index)

        image_path = index.data(self.IMAGE_ROLE)
        if not isinstance(image_path, str) or not image_path:
            return

        pixmap = self._load_pixmap(image_path)
        if pixmap.isNull():
            return

        target_size = option.rect.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            return

        scaled = pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = option.rect.x() + max(
            (target_size.width() - scaled.width()) // 2,
            0,
        )
        y = option.rect.y() + max(
            (target_size.height() - scaled.height()) // 2,
            0,
        )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(x, y, scaled)
        painter.restore()

    @staticmethod
    def _load_pixmap(image_path: str) -> QPixmap:
        """Carga imágenes de forma diferida y usa la caché gráfica de Qt."""
        cache_key = f"fcm-product-image:{image_path}"
        pixmap = QPixmap()
        if QPixmapCache.find(cache_key, pixmap):
            return pixmap

        pixmap.load(image_path)
        if not pixmap.isNull():
            QPixmapCache.insert(cache_key, pixmap)
        return pixmap

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index,
    ) -> QSize:
        del option, index
        return QSize(self.DEFAULT_SIZE, self.DEFAULT_SIZE)


class StockColorDelegate(QStyledItemDelegate):
    """Pinta todos los colores del stock dentro de una única celda."""

    STOCK_ROLE = int(Qt.ItemDataRole.UserRole) + 2
    INDICATOR_SIZE = 12
    HORIZONTAL_PADDING = 4
    TEXT_HORIZONTAL_PADDING = 4
    TEXT_GAP = 4
    MIN_LINE_HEIGHT = 24
    TEXT_COLOR = "#173f6d"

    def paint(self, painter: QPainter, option, index) -> None:
        color_stock = index.data(self.STOCK_ROLE)
        painter.save()
        painter.setFont(option.font)
        painter.setPen(QColor(self.TEXT_COLOR))

        if not isinstance(color_stock, list) or not color_stock:
            painter.drawText(
                option.rect.adjusted(
                    self.HORIZONTAL_PADDING,
                    0,
                    -self.HORIZONTAL_PADDING,
                    0,
                ),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter,
                str(index.data(Qt.ItemDataRole.DisplayRole) or ""),
            )
            painter.restore()
            return

        count = len(color_stock)
        for line, entry in enumerate(color_stock):
            if not (
                isinstance(entry, (list, tuple))
                and len(entry) == 2
            ):
                continue

            color = str(entry[0])
            stock = max(int(entry[1]), 0)
            background, indicator = ProductTable._stock_color_style(color)

            top = option.rect.top() + round(
                option.rect.height() * line / count,
            )
            bottom = option.rect.top() + round(
                option.rect.height() * (line + 1) / count,
            )
            line_rect = QRect(
                option.rect.left(),
                top,
                option.rect.width(),
                max(bottom - top, 1),
            )
            painter.fillRect(line_rect, QColor(background))

            indicator_rect = QRect(
                line_rect.left() + self.HORIZONTAL_PADDING,
                line_rect.center().y() - self.INDICATOR_SIZE // 2,
                self.INDICATOR_SIZE,
                self.INDICATOR_SIZE,
            )
            painter.setBrush(QColor(indicator))
            painter.setPen(QColor("#8c99a6"))
            painter.drawEllipse(indicator_rect)

            painter.setPen(QColor(self.TEXT_COLOR))
            metrics = QFontMetrics(painter.font())
            stock_text = f"{stock:,}"
            stock_width = metrics.horizontalAdvance(stock_text)

            stock_rect = QRect(
                line_rect.right()
                - self.TEXT_HORIZONTAL_PADDING
                - stock_width
                + 1,
                line_rect.top(),
                stock_width,
                line_rect.height(),
            )
            color_left = indicator_rect.right() + self.TEXT_GAP + 1
            color_right = stock_rect.left() - self.TEXT_GAP - 1
            color_rect = QRect(
                color_left,
                line_rect.top(),
                max(color_right - color_left + 1, 1),
                line_rect.height(),
            )

            painter.drawText(
                color_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                color,
            )
            painter.drawText(
                stock_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                stock_text,
            )

        painter.restore()

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index,
    ) -> QSize:
        del option
        color_stock = index.data(self.STOCK_ROLE)
        if isinstance(color_stock, list) and color_stock:
            return QSize(
                1,
                len(color_stock) * self.MIN_LINE_HEIGHT,
            )
        return QSize(
            1,
            self.MIN_LINE_HEIGHT,
        )


class ProductTable(QTableWidget):
    """Tabla principal del catálogo de productos."""

    CONTENT_SIDE_PADDING = 4
    TABLE_BACKGROUND = "#f8fbff"
    TABLE_CELL_BACKGROUND = "#fbfdff"
    TABLE_HEADER_BACKGROUND = "#eef5fb"
    TABLE_GRID_COLOR = "#dce7f1"
    TABLE_TEXT_COLOR = "#173f6d"
    TABLE_SELECTION_BACKGROUND = "#dbeeff"
    FONT_FAMILY = "Segoe UI"
    FONT_PIXEL_SIZE = 13
    STOCK_INDICATOR_SIZE = StockColorDelegate.INDICATOR_SIZE
    STOCK_ROW_CONTENT_HORIZONTAL_PADDING = StockColorDelegate.HORIZONTAL_PADDING
    STOCK_TEXT_HORIZONTAL_PADDING = StockColorDelegate.TEXT_HORIZONTAL_PADDING
    STOCK_ROW_CONTENT_GAP = StockColorDelegate.TEXT_GAP
    STOCK_MIN_LINE_HEIGHT = StockColorDelegate.MIN_LINE_HEIGHT
    CATEGORY_FORCED_LINES: ClassVar[dict[str, tuple[str, ...]]] = {
        "Impresoras y Consumible Fotográficas Térmicas": (
            "Impresoras y Consumible",
            "Fotográficas Térmicas",
        ),
    }
    DEFAULT_IMAGE_CELL_SIZE = ProductImageDelegate.DEFAULT_SIZE
    IMAGE_SIZE = DEFAULT_IMAGE_CELL_SIZE
    PROGRESSIVE_RENDER_THRESHOLD = 50
    PROGRESSIVE_RENDER_BATCH_SIZE = 40

    IMAGE_COLUMN = 0
    CODE_COLUMN = 1
    NAME_COLUMN = 2
    DETAIL_COLUMN = 3
    CATEGORY_COLUMN = 4
    STOCK_COLUMN = 5
    PRICE_SAMPLE_COLUMN = 6
    PRICE_HUNDRED_COLUMN = 7
    PRICE_THOUSAND_COLUMN = 8

    STOCK_COLOR_STYLES: ClassVar[dict[str, tuple[str, str]]] = {
        "amarillo": ("#fff7d6", "#f2c94c"),
        "amarillo fluorescente": ("#f5ffd1", "#efff00"),
        "amarillo flurecente": ("#f5ffd1", "#efff00"),
        "amarillo neon": ("#f5ffd1", "#efff00"),
        "amarillo neón": ("#f5ffd1", "#efff00"),
        "azul": ("#e7f1ff", "#2f80ed"),
        "azul claro": ("#e3f1ff", "#6eb6ff"),
        "azul marino": ("#e1e8f7", "#123b6d"),
        "azul oscuro": ("#dfe7ff", "#1d3f91"),
        "azulino": ("#e3ebff", "#4f64d8"),
        "azulino full": ("#e0e6ff", "#3046ff"),
        "azul full": ("#e0e6ff", "#0057ff"),
        "azul rey": ("#e1eaff", "#1747e5"),
        "azul electrico": ("#e0f0ff", "#0077ff"),
        "azul eléctrico": ("#e0f0ff", "#0077ff"),
        "azul petroleo": ("#e0f2f3", "#006b73"),
        "azul petróleo": ("#e0f2f3", "#006b73"),
        "bamboo": ("#f3ead6", "#c8aa6e"),
        "black": ("#ececec", "#1a1a1a"),
        "blanco": ("#f6f8fa", "#ffffff"),
        "brillante": ("#eef4fa", "#c8d2dc"),
        "celeste": ("#e7f7ff", "#43a5e8"),
        "champagne": ("#fff3df", "#e7cfa1"),
        "crema": ("#fff9e8", "#f4e7c3"),
        "cyan": ("#ddfbff", "#00a9c7"),
        "dorado": ("#fff4cc", "#d4af37"),
        "fucsia": ("#ffe1f1", "#ff1493"),
        "fuchsia": ("#ffe1f1", "#ff1493"),
        "gris": ("#f0f3f6", "#8d98a5"),
        "gris gun": ("#e9edf1", "#606a75"),
        "gun": ("#e9edf1", "#606a75"),
        "kraft": ("#f2e5d5", "#b9895e"),
        "lila": ("#f0e7ff", "#c8a2c8"),
        "lila pastel": ("#f3edff", "#bfa7db"),
        "magenta": ("#ffe0f5", "#d600a9"),
        "manila": ("#fff4d0", "#e3c66b"),
        "marron": ("#f3e8dd", "#795548"),
        "marrón": ("#f3e8dd", "#795548"),
        "mate": ("#e8eaed", "#6b7280"),
        "morado": ("#f1e9ff", "#9b51e0"),
        "naranja": ("#fff0df", "#f2994a"),
        "naranja full": ("#ffe9d2", "#ff7a00"),
        "natural": ("#f3eadc", "#cdb892"),
        "negro": ("#edf0f3", "#343a40"),
        "negro full": ("#e6e7e9", "#111111"),
        "pavonado": ("#e4e8ec", "#56616d"),
        "plateado": ("#f1f3f5", "#a7afb8"),
        "plata": ("#f1f3f5", "#a7afb8"),
        "silver": ("#f1f3f5", "#a7afb8"),
        "rojo": ("#ffe8e8", "#eb5757"),
        "rojo full": ("#ffdddd", "#ff1f1f"),
        "rosado": ("#ffeaf4", "#e66aa8"),
        "verde": ("#e7f6ea", "#4caf50"),
        "verde claro": ("#eaf8e9", "#5cbd69"),
        "verde oscuro": ("#e6f4ee", "#2f9e72"),
        "verde oscuro full": ("#dff2e7", "#006b3c"),
        "verde botella": ("#e1f0e7", "#176b45"),
        "verde militar": ("#e9f0dc", "#66743a"),
        "verde agua": ("#def8f3", "#4bbfae"),
        "menta": ("#e0f8ed", "#4fba8a"),
        "verde limon": ("#efffd9", "#a8d500"),
        "verde limón": ("#efffd9", "#a8d500"),
        "verde petroleo": ("#e0f2ee", "#006b5f"),
        "verde petróleo": ("#e0f2ee", "#006b5f"),
        "yellow": ("#fff5b8", "#f2d21b"),
    }
    MIN_COLUMN_WIDTHS: ClassVar[dict[int, int]] = {
        IMAGE_COLUMN: DEFAULT_IMAGE_CELL_SIZE,
        CODE_COLUMN: 80,
        NAME_COLUMN: 120,
        DETAIL_COLUMN: 180,
        CATEGORY_COLUMN: 110,
        STOCK_COLUMN: 1,
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
        "Producto",
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
        self._category_reference_products: list[Product] = []
        self._search_text = ""
        self._render_generation = 0
        self._pending_render_products: list[Product] = []
        self._pending_render_index = 0
        self._rendered_products: list[Product] = []
        self._visible_product_keys: set[int] | None = None
        table_font = QFont(self.FONT_FAMILY)
        table_font.setPixelSize(self.FONT_PIXEL_SIZE)
        self.setFont(table_font)
        self.setColumnCount(len(self.HEADER_LABELS))
        self.setHorizontalHeaderLabels(self.HEADER_LABELS)
        self._setup_table()
        self._setup_header()

    def _setup_table(self) -> None:
        self.setSortingEnabled(False)
        self.setAlternatingRowColors(False)
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
                background-color: #f8fbff;
                gridline-color: #dce7f1;
                selection-background-color: #fbfdff;
                selection-color: #173f6d;
                color: #173f6d;
            }
            QTableWidget::item {
                background-color: #fbfdff;
                padding: 4px;
                font-family: "Segoe UI";
                font-size: 13px;
                color: #173f6d;
            }
            QTableWidget::item:selected {
                background-color: #fbfdff;
                color: #173f6d;
            }
            QHeaderView::section {
                min-height: 56px;
                padding: 4px;
                font-size: 16px;
                font-weight: bold;
                text-align: center;
                background-color: #eef5fb;
                color: #173f6d;
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
        self.setItemDelegateForColumn(
            self.STOCK_COLUMN,
            StockColorDelegate(self),
        )
        header.sectionClicked.connect(self._handle_header_click)
        header.setStretchLastSection(False)
        header.setDefaultSectionSize(110)
        header.setMinimumSectionSize(1)
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
        self._render_products(self._sorted_products())
        self._update_sort_header_labels()

    def _sorted_products(self) -> list[Product]:
        products = list(self._products)
        for column, order in reversed(list(self._sort_states.items())):
            products.sort(
                key=lambda product, selected_column=column: self._product_sort_value(
                    product,
                    selected_column,
                ),
                reverse=order == Qt.SortOrder.DescendingOrder,
            )
        return products

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

    def show_all_rows(self) -> None:
        """Muestra inmediatamente todas las filas ya renderizadas."""
        self._visible_product_keys = None
        for row in range(self.rowCount()):
            self.setRowHidden(row, False)

    def show_only_products(self, products: list[Product]) -> None:
        """Filtra filas existentes sin reconstruir ni recargar la tabla."""
        self._visible_product_keys = {id(product) for product in products}
        for row, product in enumerate(self._rendered_products):
            self.setRowHidden(row, id(product) not in self._visible_product_keys)

    def set_category_reference_products(self, products: list[Product]) -> None:
        """Conserva el ancho de categoría del catálogo completo al filtrar."""
        self._category_reference_products = list(products)
        self._fit_columns_to_content()
        self._adjust_table_rows()

    def load_products(
        self,
        products: list[Product] | None = None,
        *,
        progressive: bool = True,
    ) -> None:
        source = products if products is not None else self.controller.get_products()
        self._products = list(source)
        self._apply_current_sort()


    def _render_products(self, products: list[Product]) -> None:
        self._render_generation += 1
        generation = self._render_generation
        self._pending_render_products = list(products)
        self._pending_render_index = 0

        self.setSortingEnabled(False)
        self.clearContents()
        self._rendered_products = list(products)
        self._max_stock_pair_width = self._calculate_stock_pair_width(products)
        self.setRowCount(len(products))
        if self._visible_product_keys is not None:
            for row in range(self.rowCount()):
                self.setRowHidden(row, True)

        if len(products) <= self.PROGRESSIVE_RENDER_THRESHOLD:
            self._render_rows(0, len(products))
            self._finish_render(generation)
            return

        QTimer.singleShot(
            0,
            lambda generation=generation: self._render_next_batch(generation),
        )

    def _calculate_stock_pair_width(self, products: list[Product]) -> int:
        metrics = QFontMetrics(self.font())
        maximum = 0
        for product in products:
            color_stock = self._ordered_color_stock(product)
            if color_stock:
                for color, stock in color_stock:
                    maximum = max(
                        maximum,
                        self.STOCK_INDICATOR_SIZE
                        + self.STOCK_ROW_CONTENT_GAP
                        + metrics.horizontalAdvance(color)
                        + self.STOCK_ROW_CONTENT_GAP
                        + metrics.horizontalAdvance(f"{stock:,}")
                        + (2 * self.STOCK_ROW_CONTENT_HORIZONTAL_PADDING),
                    )
                continue

            maximum = max(
                maximum,
                metrics.horizontalAdvance(f"{product.stock:,}")
                + (2 * self.STOCK_ROW_CONTENT_HORIZONTAL_PADDING),
            )
        return maximum

    def _render_next_batch(self, generation: int) -> None:
        if generation != self._render_generation:
            return

        total = len(self._pending_render_products)
        start = self._pending_render_index
        if start >= total:
            self._finish_render(generation)
            return

        end = min(
            start + self.PROGRESSIVE_RENDER_BATCH_SIZE,
            total,
        )
        self._render_rows(start, end)
        self._pending_render_index = end

        if end < total:
            QTimer.singleShot(
                0,
                lambda generation=generation: self._render_next_batch(generation),
            )
            return

        QTimer.singleShot(
            0,
            lambda generation=generation: self._finish_render(generation),
        )

    def _render_rows(self, start: int, end: int) -> None:
        self.setUpdatesEnabled(False)
        try:
            for row in range(start, end):
                product = self._pending_render_products[row]
                self._add_product_row(row, product)
                self._set_row_height(row)
                if self._visible_product_keys is not None:
                    self.setRowHidden(
                        row,
                        id(product) not in self._visible_product_keys,
                    )
        finally:
            self.setUpdatesEnabled(True)

    def _finish_render(self, generation: int) -> None:
        if generation != self._render_generation:
            return

        self._fit_columns_to_content()
        self._adjust_table_rows()
        self._pending_render_products = []
        self._pending_render_index = 0

    def _add_product_row(self, row: int, product: Product) -> None:
        image_item = QTableWidgetItem()
        if product.image_path:
            image_path = resolve_data_path(product.image_path)
            image_item.setData(
                ProductImageDelegate.IMAGE_ROLE,
                str(image_path),
            )
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
                cls.CATEGORY_FORCED_LINES.get(
                    category_name,
                    (category_name,),
                ),
            )
        return "\n".join(lines)

    def _set_stock_widget(self, row: int, product: Product) -> None:
        """Configura el stock por color para pintarlo dentro de una única celda."""
        color_stock = self._ordered_color_stock(product)
        item = NumericTableWidgetItem(
            "" if color_stock else str(product.stock),
            product.stock,
        )
        item.setData(StockColorDelegate.STOCK_ROLE, color_stock)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter,
        )
        if color_stock:
            item.setToolTip(
                "\n".join(
                    f"{color}: {stock}" for color, stock in color_stock
                ),
            )
        self.setItem(row, self.STOCK_COLUMN, item)

    @classmethod
    def _stock_color_style(cls, color: str) -> tuple[str, str]:
        """Devuelve fondo e indicador para el color comercial recibido."""
        normalized = " ".join(color.strip().casefold().split())
        style = cls.STOCK_COLOR_STYLES.get(normalized)
        if style is not None:
            return style

        fallback_indicator = "#8fa3b8"
        fallback_background = "#eef3f7"
        qcolor = QColor(color)
        if qcolor.isValid():
            fallback_indicator = qcolor.name().lower()
            fallback_background = qcolor.lighter(185).name().lower()
        return fallback_background, fallback_indicator

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

    def _set_row_height(self, row: int) -> None:
        image_size = max(
            self.columnWidth(self.IMAGE_COLUMN),
            self.DEFAULT_IMAGE_CELL_SIZE,
        )
        row_height = image_size
        stock_item = self.item(row, self.STOCK_COLUMN)
        if stock_item is not None:
            color_stock = stock_item.data(StockColorDelegate.STOCK_ROLE)
            if isinstance(color_stock, list) and color_stock:
                row_height = max(
                    row_height,
                    len(color_stock) * StockColorDelegate.MIN_LINE_HEIGHT,
                )
        self.setRowHeight(row, row_height)

    def _adjust_table_rows(self) -> None:
        for row in range(self.rowCount()):
            self._set_row_height(row)

    def _stock_minimum_width(self) -> int:
        """Garantiza que cada color y cantidad permanezcan en una sola línea."""
        pair_width = getattr(
            self,
            "_max_stock_pair_width",
            0,
        )
        header_width = (
            QFontMetrics(self.font()).horizontalAdvance(
                self.HEADER_LABELS[self.STOCK_COLUMN],
            )
            + (2 * self.CONTENT_SIDE_PADDING)
        )
        return max(
            pair_width,
            header_width,
            1,
        )

    def _category_minimum_width(self) -> int:
        metrics = QFontMetrics(self.font())
        category_width = self.MIN_COLUMN_WIDTHS[self.CATEGORY_COLUMN]
        reference_products = (
            self._category_reference_products
            if self._category_reference_products
            else self._products
        )
        for product in reference_products:
            for line in self._format_categories(product.category).splitlines():
                category_width = max(
                    category_width,
                    metrics.horizontalAdvance(line) + (
                        2 * self.CONTENT_SIDE_PADDING
                    ),
                )
        return category_width

    def _preferred_column_widths(self, header: QHeaderView) -> list[int]:
        self.resizeColumnsToContents()
        minimum_widths = [
            self.MIN_COLUMN_WIDTHS[column]
            for column in range(self.columnCount())
        ]
        minimum_widths[self.CATEGORY_COLUMN] = self._category_minimum_width()
        minimum_widths[self.STOCK_COLUMN] = self._stock_minimum_width()
        preferred_widths = [
            max(
                header.sectionSize(column),
                minimum_widths[column],
            )
            for column in range(self.columnCount())
        ]
        # Stock debe conservar exclusivamente el ancho calculado por su
        # contenido, sin el margen adicional que Qt puede introducir al
        # aplicar resizeColumnsToContents().
        preferred_widths[self.STOCK_COLUMN] = minimum_widths[self.STOCK_COLUMN]
        return preferred_widths

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
            minimum_widths[self.CATEGORY_COLUMN] = self._category_minimum_width()
            minimum_widths[self.STOCK_COLUMN] = self._stock_minimum_width()
            minimum_total = sum(minimum_widths)
            available_width = self.viewport().width()
            target_width = max(available_width, minimum_total)
            widths = self._allocate_column_widths(
                preferred_widths,
                minimum_widths,
                target_width,
                growable_columns=(
                    set(range(1, self.columnCount()))
                    - {self.STOCK_COLUMN}
                ),
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
