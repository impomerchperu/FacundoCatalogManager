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

    def __init__(
        self,
        text: str,
        value: int | float,
    ) -> None:
        super().__init__(text)

        self.setData(
            Qt.ItemDataRole.UserRole,
            value,
        )

    def __lt__(
        self,
        other: QTableWidgetItem,
    ) -> bool:
        if isinstance(other, QTableWidgetItem):
            self_value = self.data(
                Qt.ItemDataRole.UserRole,
            )

            other_value = other.data(
                Qt.ItemDataRole.UserRole,
            )

            if (
                self_value is not None
                and other_value is not None
            ):
                try:
                    return float(self_value) < float(other_value)
                except (TypeError, ValueError):
                    pass

        return super().__lt__(other)


class ProductHeader(QHeaderView):
    """Encabezado con resaltado de la columna de ordenamiento activa."""

    def __init__(
        self,
        parent: QTableWidget,
    ) -> None:
        super().__init__(
            Qt.Orientation.Horizontal,
            parent,
        )

        self.active_section = -1

        self.setMinimumHeight(56)

        self.setDefaultAlignment(
            Qt.AlignmentFlag.AlignCenter,
        )

        self.setSectionsClickable(True)

        # El indicador nativo se desactiva porque ProductTable
        # dibuja el indicador ↑/↓ directamente en el texto.
        self.setSortIndicatorShown(False)

    def set_active_section(
        self,
        section: int,
    ) -> None:
        """Establece la sección activa del encabezado."""

        self.active_section = section

        self.viewport().update()

    def paintSection(
        self,
        painter: QPainter,
        rect,
        logical_index: int,
    ) -> None:
        """Pinta la sección activa antes del renderizado normal."""

        painter.save()

        if logical_index == self.active_section:
            painter.fillRect(
                rect,
                self.palette().highlight(),
            )

        painter.restore()

        super().paintSection(
            painter,
            rect,
            logical_index,
        )


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

    def __init__(
        self,
        controller: ProductController,
    ) -> None:
        super().__init__()

        self.controller = controller

        self._sort_column: int | None = None
        self._sort_order = Qt.SortOrder.AscendingOrder

        self.setColumnCount(9)

        self.setHorizontalHeaderLabels(
            self.HEADER_LABELS,
        )

        self._setup_table()
        self._setup_header()

        self.load_products()

    def _setup_table(self) -> None:
        """Configura el comportamiento y presentación de la tabla."""

        self.setSortingEnabled(False)

        self.setAlternatingRowColors(True)

        self.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )

        self.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )

        self.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )

        self.setWordWrap(True)

        self.verticalHeader().setVisible(False)

        self.verticalHeader().setDefaultSectionSize(76)

        self.setShowGrid(True)

        self.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel,
        )

        self.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel,
        )

        self.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #d9d9d9;
                selection-background-color: #cceff1;
                selection-color: #000000;
            }

            QTableWidget::item {
                padding: 6px;
            }

            QHeaderView::section {
                min-height: 56px;
                padding: 8px 6px;
                font-size: 13px;
                font-weight: bold;
                text-align: center;
            }
            """,
        )

    def _setup_header(self) -> None:
        """Configura el encabezado interactivo de la tabla."""

        header = ProductHeader(self)

        self.setHorizontalHeader(header)

        header.setSectionsClickable(True)

        header.sectionClicked.connect(
            self._handle_header_click,
        )

        header.setStretchLastSection(False)

        for column in range(self.columnCount()):
            if column == self.IMAGE_COLUMN:
                resize_mode = QHeaderView.ResizeMode.Fixed
            else:
                resize_mode = QHeaderView.ResizeMode.Interactive

            header.setSectionResizeMode(
                column,
                resize_mode,
            )

        self.setColumnWidth(
            self.IMAGE_COLUMN,
            82,
        )

        self.setColumnWidth(
            self.CODE_COLUMN,
            105,
        )

        self.setColumnWidth(
            self.NAME_COLUMN,
            190,
        )

        self.setColumnWidth(
            self.DETAIL_COLUMN,
            300,
        )

        self.setColumnWidth(
            self.CATEGORY_COLUMN,
            150,
        )

        self.setColumnWidth(
            self.STOCK_COLUMN,
            90,
        )

        self.setColumnWidth(
            self.PRICE_SAMPLE_COLUMN,
            125,
        )

        self.setColumnWidth(
            self.PRICE_HUNDRED_COLUMN,
            125,
        )

        self.setColumnWidth(
            self.PRICE_THOUSAND_COLUMN,
            125,
        )

    def _handle_header_click(
        self,
        column: int,
    ) -> None:
        """Alterna el orden al hacer clic en un encabezado."""

        if column not in self.SORTABLE_COLUMNS:
            return

        if self._sort_column == column:
            if (
                self._sort_order
                == Qt.SortOrder.AscendingOrder
            ):
                self._sort_order = (
                    Qt.SortOrder.DescendingOrder
                )
            else:
                self._sort_order = (
                    Qt.SortOrder.AscendingOrder
                )
        else:
            self._sort_column = column
            self._sort_order = Qt.SortOrder.AscendingOrder

        self._apply_current_sort()

    def _apply_current_sort(self) -> None:
        """Aplica el ordenamiento actualmente seleccionado."""

        if self._sort_column is None:
            return

        sorting_enabled = self.isSortingEnabled()

        self.setSortingEnabled(False)

        self.sortItems(
            self._sort_column,
            self._sort_order,
        )

        header = self.product_header()

        header.set_active_section(
            self._sort_column,
        )

        self._update_sort_header_labels()

        self.setSortingEnabled(
            sorting_enabled,
        )

    def product_header(self) -> ProductHeader:
        """Devuelve el encabezado especializado del catálogo."""

        header = self.horizontalHeader()

        if not isinstance(header, ProductHeader):
            raise TypeError(
                "El encabezado de ProductTable debe ser ProductHeader.",
            )

        return header

    def _update_sort_header_labels(self) -> None:
        """Actualiza los indicadores visuales de ordenamiento."""

        labels = self.HEADER_LABELS.copy()

        if self._sort_column in self.SORTABLE_COLUMNS:
            arrow = (
                " ↑"
                if self._sort_order
                == Qt.SortOrder.AscendingOrder
                else " ↓"
            )

            labels[self._sort_column] += arrow

        self.setHorizontalHeaderLabels(
            labels,
        )

    def load_products(
        self,
        productos: list[Product] | None = None,
    ) -> None:
        """Carga los productos en la tabla."""

        sorting_enabled = self.isSortingEnabled()

        self.setSortingEnabled(False)

        if productos is None:
            productos = self.controller.get_products()

        self.clearContents()

        self.setRowCount(
            len(productos),
        )

        for fila, producto in enumerate(productos):
            self._add_product_row(
                fila,
                producto,
            )

        self.setSortingEnabled(
            sorting_enabled,
        )

        self._adjust_table_rows()

        self._restore_sort_state()

    def _restore_sort_state(self) -> None:
        """Restaura el ordenamiento después de recargar la tabla."""

        if self._sort_column is None:
            self._clear_sort_indicator()
            return

        self._apply_current_sort()

    def _clear_sort_indicator(self) -> None:
        """Limpia el resaltado del encabezado."""

        header = self.product_header()

        header.set_active_section(
            -1,
        )

        self._update_sort_header_labels()

    def _add_product_row(
        self,
        fila: int,
        producto: Product,
    ) -> None:
        """Agrega un producto completo a una fila."""

        image = QLabel()

        image.setAlignment(
            Qt.AlignmentFlag.AlignCenter,
        )

        image.setMinimumSize(
            70,
            70,
        )

        if producto.image_path:
            pixmap = QPixmap(
                producto.image_path,
            )

            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    64,
                    64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

                image.setPixmap(
                    pixmap,
                )

        self.setCellWidget(
            fila,
            self.IMAGE_COLUMN,
            image,
        )

        item_code = QTableWidgetItem(
            producto.code,
        )

        item_code.setData(
            Qt.ItemDataRole.UserRole,
            producto.id,
        )

        item_code.setTextAlignment(
            Qt.AlignmentFlag.AlignCenter,
        )

        self.setItem(
            fila,
            self.CODE_COLUMN,
            item_code,
        )

        name_item = QTableWidgetItem(
            producto.name,
        )

        name_item.setToolTip(
            producto.name,
        )

        name_item.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter
            | Qt.AlignmentFlag.AlignLeft,
        )

        self.setItem(
            fila,
            self.NAME_COLUMN,
            name_item,
        )

        detail_item = QTableWidgetItem(
            producto.description,
        )

        detail_item.setToolTip(
            producto.description,
        )

        detail_item.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter
            | Qt.AlignmentFlag.AlignLeft,
        )

        self.setItem(
            fila,
            self.DETAIL_COLUMN,
            detail_item,
        )

        category_item = QTableWidgetItem(
            producto.category,
        )

        category_item.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter
            | Qt.AlignmentFlag.AlignLeft,
        )

        self.setItem(
            fila,
            self.CATEGORY_COLUMN,
            category_item,
        )

        stock_item = NumericTableWidgetItem(
            str(producto.stock),
            producto.stock,
        )

        stock_item.setTextAlignment(
            Qt.AlignmentFlag.AlignCenter,
        )

        self.setItem(
            fila,
            self.STOCK_COLUMN,
            stock_item,
        )

        price_sample_item = NumericTableWidgetItem(
            f"{producto.price_sample:.2f}",
            producto.price_sample,
        )

        price_sample_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter,
        )

        self.setItem(
            fila,
            self.PRICE_SAMPLE_COLUMN,
            price_sample_item,
        )

        price_hundred_item = NumericTableWidgetItem(
            f"{producto.price_hundred:.2f}",
            producto.price_hundred,
        )

        price_hundred_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter,
        )

        self.setItem(
            fila,
            self.PRICE_HUNDRED_COLUMN,
            price_hundred_item,
        )

        price_thousand_item = NumericTableWidgetItem(
            f"{producto.price_thousand:.2f}",
            producto.price_thousand,
        )

        price_thousand_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter,
        )

        self.setItem(
            fila,
            self.PRICE_THOUSAND_COLUMN,
            price_thousand_item,
        )

    def _adjust_table_rows(self) -> None:
        """Ajusta las filas al contenido sin deformar la tabla."""

        for fila in range(self.rowCount()):
            self.setRowHeight(
                fila,
                76,
            )

    def resizeEvent(self, event) -> None:
        """Redistribuye el espacio cuando cambia el tamaño de la ventana."""

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

        remaining_width = max(
            available_width - fixed_width,
            600,
        )

        name_width = int(
            remaining_width * 0.27,
        )

        detail_width = int(
            remaining_width * 0.43,
        )

        category_width = max(
            int(remaining_width * 0.30),
            120,
        )

        self.setColumnWidth(
            self.NAME_COLUMN,
            name_width,
        )

        self.setColumnWidth(
            self.DETAIL_COLUMN,
            detail_width,
        )

        self.setColumnWidth(
            self.CATEGORY_COLUMN,
            category_width,
        )
