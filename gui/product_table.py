import re
import unicodedata
from typing import ClassVar

from PySide6.QtCore import QPointF, QRect, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QFontMetricsF,
    QPainter,
    QPalette,
    QPixmap,
    QPixmapCache,
    QTextLayout,
    QTextOption,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from config.runtime_paths import resolve_data_path
from controllers.product_controller import ProductController
from gui.product_category_delegate import ProductCategoryDelegate
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


class PriceDelegate(QStyledItemDelegate):
    """Editor numérico que mantiene visible la moneda durante la edición."""

    def createEditor(self, parent, option, index) -> QWidget:
        del option, index
        editor = QWidget(parent)
        layout = QHBoxLayout(editor)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(3)
        currency = QLabel("S/", editor)
        currency.setStyleSheet("color: #173f6d;")
        value = QLineEdit(editor)
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value.setPlaceholderText("0.00")
        layout.addWidget(currency)
        layout.addWidget(value, 1)
        editor.setFocusProxy(value)
        return editor

    def setEditorData(self, editor: QWidget, index) -> None:
        value = editor.findChild(QLineEdit)
        if value is None:
            return
        numeric = index.data(Qt.ItemDataRole.UserRole)
        try:
            number = float(numeric)
        except (TypeError, ValueError):
            number = 0.0
        value.setText(f"{number:.2f}")
        value.selectAll()

    def setModelData(self, editor: QWidget, model, index) -> None:
        value = editor.findChild(QLineEdit)
        if value is None:
            return
        raw = value.text().strip().replace("S/", "").strip()
        normalized = raw.replace(" ", "")
        if "," in normalized and "." in normalized:
            normalized = normalized.replace(",", "")
        elif "," in normalized:
            normalized = normalized.replace(",", ".")
        try:
            number = max(float(normalized), 0.0)
        except ValueError:
            model.setData(index, f"S/ {raw}", Qt.ItemDataRole.EditRole)
            return
        model.setData(index, f"S/ {number:,.2f}", Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor: QWidget, option, index) -> None:
        del index
        editor.setGeometry(option.rect)


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

    DEFAULT_SIZE = 144
    IMAGE_ROLE = int(Qt.ItemDataRole.UserRole) + 1
    GALLERY_ROLE = int(Qt.ItemDataRole.UserRole) + 3
    ACTIVE_INDEX_ROLE = int(Qt.ItemDataRole.UserRole) + 4

    def paint(self, painter: QPainter, option, index) -> None:
        super().paint(painter, option, index)

        gallery = index.data(self.GALLERY_ROLE)
        image_path = index.data(self.IMAGE_ROLE)
        active_index = index.data(self.ACTIVE_INDEX_ROLE)
        if isinstance(gallery, list) and gallery:
            try:
                active_index = int(active_index)
            except (TypeError, ValueError):
                active_index = 0
            active_index %= len(gallery)
            selected = gallery[active_index]
            if isinstance(selected, dict):
                image_path = selected.get(
                    "image_path",
                    selected.get("path", image_path),
                )
                if isinstance(image_path, str):
                    image_path = str(resolve_data_path(image_path))
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
        if isinstance(gallery, list) and len(gallery) > 1:
            try:
                active_index = int(active_index) % len(gallery)
            except (TypeError, ValueError):
                active_index = 0
            painter.setPen(QColor("#173f6d"))
            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            painter.drawText(
                option.rect.adjusted(6, 0, -6, -6),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                "<",
            )
            painter.drawText(
                option.rect.adjusted(6, 0, -6, -6),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
                ">",
            )
            painter.drawText(
                option.rect.adjusted(0, 0, 0, -6),
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
                f"{active_index + 1}/{len(gallery)}",
            )
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
    """Pinta y edita cada línea de stock por color dentro de una celda."""

    STOCK_ROLE = int(Qt.ItemDataRole.UserRole) + 2

    def createEditor(self, parent, option, index) -> QWidget:
        del option
        color_stock = index.data(self.STOCK_ROLE)
        if isinstance(color_stock, list) and color_stock:
            return QPlainTextEdit(parent)
        editor = QLineEdit(parent)
        editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return editor

    def setEditorData(self, editor: QWidget, index) -> None:
        color_stock = index.data(self.STOCK_ROLE)
        if isinstance(editor, QPlainTextEdit):
            entries = color_stock if isinstance(color_stock, list) else []
            editor.setPlainText(
                "\n".join(
                    f"{entry[0]}: {entry[1]}"
                    for entry in entries
                    if isinstance(entry, (list, tuple)) and len(entry) == 2
                )
            )
            return
        if isinstance(editor, QLineEdit):
            editor.setText(str(index.data(Qt.ItemDataRole.DisplayRole) or "0"))
            editor.selectAll()

    def setModelData(self, editor: QWidget, model, index) -> None:
        if isinstance(editor, QPlainTextEdit):
            value = editor.toPlainText()
        elif isinstance(editor, QLineEdit):
            value = editor.text().strip()
        else:
            return
        model.setData(index, value, Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor: QWidget, option, index) -> None:
        del index
        editor.setGeometry(option.rect)
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


class ProductDetailDelegate(QStyledItemDelegate):
    """Renderiza el detalle con interlineado compacto y ajuste de texto."""

    HORIZONTAL_PADDING = 4
    VERTICAL_PADDING = 2
    LINE_SPACING_REDUCTION = 1

    @classmethod
    def _layout_text(
        cls,
        text: str,
        font: QFont,
        width: int,
    ) -> tuple[list[tuple[QTextLayout, float]], int]:
        metrics = QFontMetricsF(font)
        line_height = max(
            metrics.height() - cls.LINE_SPACING_REDUCTION,
            1.0,
        )
        layouts: list[tuple[QTextLayout, float]] = []
        total_height = 0.0
        paragraphs = text.splitlines() or [text]
        for paragraph in paragraphs:
            layout = QTextLayout(paragraph, font)
            text_option = QTextOption()
            text_option.setWrapMode(QTextOption.WrapMode.WordWrap)
            layout.setTextOption(text_option)
            line_top = 0.0
            last_line_top = 0.0
            last_line_height = line_height
            layout.beginLayout()
            while True:
                line = layout.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(max(width, 1))
                last_line_top = line_top
                line.setPosition(QPointF(0, line_top))
                last_line_height = line.height()
                line_top += max(
                    line.height() - cls.LINE_SPACING_REDUCTION,
                    1.0,
                )
            layout.endLayout()
            paragraph_height = (
                last_line_top + last_line_height
                if line_top > 0
                else line_height
            )
            layouts.append((layout, total_height))
            total_height += paragraph_height
        return layouts, round(total_height)

    @classmethod
    def content_height(cls, text: str, font: QFont, width: int) -> int:
        if not text:
            return 0
        _, height = cls._layout_text(text, font, width)
        return height

    def paint(self, painter: QPainter, option, index) -> None:
        styled_option = QStyleOptionViewItem(option)
        self.initStyleOption(styled_option, index)
        text = styled_option.text
        styled_option.text = ""

        widget = styled_option.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            styled_option,
            painter,
            widget,
        )
        if not text:
            return

        text_width = max(
            styled_option.rect.width() - (2 * self.HORIZONTAL_PADDING),
            1,
        )
        layouts, _ = self._layout_text(
            text,
            styled_option.font,
            text_width,
        )
        painter.save()
        painter.setPen(styled_option.palette.color(QPalette.ColorRole.Text))
        for layout, top_offset in layouts:
            layout.draw(
                painter,
                QPointF(
                    styled_option.rect.left() + self.HORIZONTAL_PADDING,
                    styled_option.rect.top()
                    + self.VERTICAL_PADDING
                    + top_offset,
                ),
            )
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        width = max(
            option.rect.width() - (2 * self.HORIZONTAL_PADDING),
            self.HORIZONTAL_PADDING,
        )
        if width <= self.HORIZONTAL_PADDING:
            line_count = max(text.count("\n") + 1, 1)
            height = (
                QFontMetricsF(option.font).height()
                - self.LINE_SPACING_REDUCTION
            ) * line_count
        else:
            height = self.content_height(text, option.font, width)
        base = super().sizeHint(option, index)
        return QSize(
            base.width(),
            max(round(height) + 2 * self.VERTICAL_PADDING, base.height()),
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
    DEFAULT_PRICE_COLUMN_WIDTH = 110
    FIXED_PRICE_COLUMN_WIDTH = 88
    DETAIL_FIELD_LABELS: ClassVar[dict[str, str]] = {
        "color": "Color",
        "codigo": "Código",
        "código": "Código",
        "producto": "Producto",
        "nombre": "Nombre",
        "categoria": "Categoría",
        "categoría": "Categoría",
        "stock": "Stock",
        "existencia": "Stock",
        "precio": "Precio",
        "precio muestra": "Precio muestra",
        "precio por muestra": "Precio muestra",
        "precio ciento": "Precio ciento",
        "precio por ciento": "Precio ciento",
        "precio millar": "Precio millar",
        "precio por millar": "Precio millar",
        "potencia": "Potencia",
        "dimensiones": "Dimensiones",
        "peso unitario": "Peso Unitario",
        "uso recomendado": "Uso Recomendado",
        "empaque individual": "Empaque Individual",
        "cantidad por caja": "Cantidad por Caja",
        "dimensiones caja": "Dimensiones Caja",
        "cubicaje por caja": "Cubicaje por Caja",
        "peso neto por caja": "Peso neto por caja",
        "peso bruto por caja": "Peso bruto por caja",
        "voltaje": "Voltaje",
        "material": "Material",
        "modelo": "Modelo",
        "capacidad": "Capacidad",
        "tipo": "Tipo",
        "tamaño de impresión": "Tamaño de impresión",
        "area de impresion": "Área de impresión",
        "área de impresión": "Área de impresión",
        "tamaño": "Tamaño",
        "gramaje": "Gramaje",
        "resolucion": "Resolución",
        "resolución": "Resolución",
        "velocidad": "Velocidad",
        "temperatura": "Temperatura",
        "presion": "Presión",
        "presión": "Presión",
        "ancho": "Ancho",
        "largo": "Largo",
        "altura": "Altura",
        "alto": "Alto",
        "peso": "Peso",
        "frecuencia": "Frecuencia",
        "formato": "Formato",
        "presentacion": "Presentación",
        "presentación": "Presentación",
        "marca": "Marca",
        "compatibilidad": "Compatibilidad",
        "contenido": "Contenido",
        "incluye": "Incluye",
        "empaque": "Empaque",
        "medida": "Medida",
        "alimentacion": "Alimentación",
        "alimentación": "Alimentación",
        "tiempo": "Tiempo",
        "diametro": "Diámetro",
        "diámetro": "Diámetro",
        "espesor": "Espesor",
        "acabado": "Acabado",
        "funcion": "Función",
        "función": "Función",
        "funciones": "Funciones",
        "uso": "Uso",
        "aplicacion": "Aplicación",
        "aplicación": "Aplicación",
        "area de trabajo": "Área de trabajo",
        "área de trabajo": "Área de trabajo",
        "color de impresion": "Color de impresión",
        "color de impresión": "Color de impresión",
        "cubicaje": "Cubicaje",
        "resistencia": "Resistencia",
        "empaque por caja": "Empaque por caja",
        "unidades por caja": "Unidades por caja",
        "cantidad": "Cantidad",
        "unidad": "Unidad",
        "peso neto": "Peso neto",
        "peso bruto": "Peso bruto",
    }
    DETAIL_FIELD_LABEL_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"(?<!\w)("
        + "|".join(
            re.escape(label)
            for label in sorted(DETAIL_FIELD_LABELS, key=len, reverse=True)
        )
        + r")\s*:",
        re.IGNORECASE,
    )
    CATEGORY_REFERENCE_TEXT = "Enmicadoras / Laminadoras"
    CATEGORY_SOURCE_ROLE = int(Qt.ItemDataRole.UserRole) + 50
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
        IMAGE_COLUMN: IMAGE_SIZE,
        CODE_COLUMN: 80,
        NAME_COLUMN: 120,
        DETAIL_COLUMN: 180,
        CATEGORY_COLUMN: 110,
        STOCK_COLUMN: 1,
        PRICE_SAMPLE_COLUMN: 88,
        PRICE_HUNDRED_COLUMN: 88,
        PRICE_THOUSAND_COLUMN: 88,
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
        self._sort_states: dict[int, Qt.SortOrder] = {
            self.CATEGORY_COLUMN: Qt.SortOrder.AscendingOrder,
        }
        self._default_category_sort_active = True
        self._stable_code_width: int | None = None
        self._products: list[Product] = []
        self._category_reference_products: list[Product] = []
        self._search_text = ""
        self._render_generation = 0
        self._pending_render_products: list[Product] = []
        self._pending_render_index = 0
        self._rendered_products: list[Product] = []
        self._visible_product_keys: set[int] | None = None
        self._preferred_widths_cache: list[int] | None = None
        self._active_image_indices: dict[str, int] = {}
        self._gallery_overrides: dict[str, list[dict]] = {}
        self._row_by_code: dict[str, int] = {}
        self._rendering = False
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
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed,
        )
        self.setWordWrap(True)
        self.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_image_context_menu)
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
            self.DETAIL_COLUMN,
            ProductDetailDelegate(self),
        )
        self.setItemDelegateForColumn(
            self.STOCK_COLUMN,
            StockColorDelegate(self),
        )
        price_delegate = PriceDelegate(self)
        for column in (
            self.PRICE_SAMPLE_COLUMN,
            self.PRICE_HUNDRED_COLUMN,
            self.PRICE_THOUSAND_COLUMN,
        ):
            self.setItemDelegateForColumn(column, price_delegate)
        self.category_delegate = ProductCategoryDelegate(self)
        self.setItemDelegateForColumn(
            self.CATEGORY_COLUMN,
            self.category_delegate,
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

    def _show_image_context_menu(self, position) -> None:
        index = self.indexAt(position)
        if not index.isValid() or index.column() != self.IMAGE_COLUMN:
            return
        item = self.item(index.row(), self.IMAGE_COLUMN)
        if item is None:
            return
        gallery = item.data(ProductImageDelegate.GALLERY_ROLE)
        if not isinstance(gallery, list) or not gallery:
            return
        active = item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE)
        try:
            active_index = int(active) % len(gallery)
        except (TypeError, ValueError):
            active_index = 0
        selected = gallery[active_index]
        if not isinstance(selected, dict):
            return

        code_item = self.item(index.row(), self.CODE_COLUMN)
        if code_item is None:
            return
        product_id = code_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(product_id, int):
            return

        product = (
            self._rendered_products[index.row()]
            if 0 <= index.row() < len(self._rendered_products)
            else None
        )
        if product is None or product.id != product_id:
            return

        selected_url = str(selected.get("url", "") or "").strip()
        persisted = next(
            (
                image
                for image in list(getattr(product, "gallery_images", []) or [])
                if isinstance(image, dict)
                and str(image.get("url", "") or "").strip().casefold()
                == selected_url.casefold()
            ),
            None,
        )
        persisted_image = persisted if isinstance(persisted, dict) else None

        menu = QMenu(self)
        use_action = menu.addAction("Usar como imagen principal")
        use_action.setEnabled(persisted_image is not None)
        if persisted_image is None:
            use_action.setToolTip(
                "Primero apruebe la nueva galería desde Revisión de imágenes."
            )
        chosen = menu.exec(self.viewport().mapToGlobal(position))
        if chosen is not use_action or persisted_image is None:
            return

        product.image_url = str(persisted_image.get("url", "") or "")
        product.image_path = str(
            persisted_image.get(
                "image_path",
                persisted_image.get("path", ""),
            )
            or ""
        )
        product.image_hash = str(
            persisted_image.get(
                "image_hash",
                persisted_image.get("hash", ""),
            )
            or ""
        )
        self.controller.update_product(product)
        self._products = [
            product if item is self._rendered_products[index.row()] else item
            for item in self._products
        ]
        self._rendered_products[index.row()] = product
        self._set_active_image(index.row(), active_index)

    def _handle_header_click(self, column: int) -> None:
        if column not in self.SORTABLE_COLUMNS:
            return
        current = self._sort_states.get(column)
        if current is None:
            self._sort_states[column] = Qt.SortOrder.DescendingOrder
        elif current == Qt.SortOrder.DescendingOrder:
            self._sort_states[column] = Qt.SortOrder.AscendingOrder
        elif (
            column == self.CATEGORY_COLUMN
            and self._default_category_sort_active
            and len(self._sort_states) == 1
        ):
            self._sort_states[column] = Qt.SortOrder.DescendingOrder
        else:
            del self._sort_states[column]
        self._default_category_sort_active = False
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

    @staticmethod
    def _natural_sort_key(value: str) -> tuple[tuple[int, str], ...]:
        normalized = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
            .casefold()
        )
        parts: list[tuple[int, str]] = []
        for token in re.split(r"(\d+)", normalized):
            if not token:
                continue
            if token.isdigit():
                normalized = token.lstrip("0") or "0"
                parts.append(
                    (1, f"{len(normalized):08d}:{normalized}"),
                )
            else:
                parts.append((0, token))
        return tuple(parts)

    def _product_sort_value(self, product: Product, column: int):
        if column == self.CATEGORY_COLUMN:
            return (
                self._natural_sort_key(product.category),
                self._natural_sort_key(product.code),
            )
        values = {
            self.CODE_COLUMN: product.code.casefold(),
            self.NAME_COLUMN: product.name.casefold(),
            self.DETAIL_COLUMN: product.description.casefold(),
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

        current_labels = [
            item.text() if item is not None else ""
            for item in (
                self.horizontalHeaderItem(column)
                for column in range(self.columnCount())
            )
        ]
        labels_changed = current_labels != labels

        self.setHorizontalHeaderLabels(labels)
        if labels_changed:
            self._preferred_widths_cache = None

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

    def set_category_editor_options(self, categories: list[str]) -> None:
        self.category_delegate.set_categories(categories)

    def set_category_reference_products(self, products: list[Product]) -> None:
        """Conserva el ancho de categoría del catálogo completo al filtrar."""
        self._category_reference_products = list(products)
        self._preferred_widths_cache = None
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
        self._rendering = True
        self._render_generation += 1
        generation = self._render_generation
        self._preferred_widths_cache = None
        self._pending_render_products = list(products)
        self._pending_render_index = 0

        self.setSortingEnabled(False)
        self.clearContents()
        self._rendered_products = list(products)
        self._row_by_code = {
            str(product.code).strip().casefold(): row
            for row, product in enumerate(products)
            if str(product.code).strip()
        }
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
        self._rendering = False

    def _add_product_row(self, row: int, product: Product) -> None:
        image_item = QTableWidgetItem()
        gallery = self._product_gallery(product)
        code_key = str(product.code).strip().casefold()
        persisted_urls = {
            str(image.get("url", "") or "").strip().casefold()
            for image in gallery
            if isinstance(image, dict)
        }
        for option in self._gallery_overrides.get(code_key, []):
            url = str(option.get("url", "") or "").strip()
            if url and url.casefold() not in persisted_urls:
                gallery.append(dict(option))
                persisted_urls.add(url.casefold())
        active_index = self._active_image_indices.get(
            str(product.code).strip().casefold(),
            0,
        )
        if gallery:
            active_index %= len(gallery)
            selected = gallery[active_index]
            image_path = str(
                selected.get("image_path", selected.get("path", ""))
                if isinstance(selected, dict)
                else ""
            )
        else:
            image_path = product.image_path
        image_item.setData(ProductImageDelegate.GALLERY_ROLE, gallery)
        image_item.setData(ProductImageDelegate.ACTIVE_INDEX_ROLE, active_index)
        if image_path:
            image_item.setData(
                ProductImageDelegate.IMAGE_ROLE,
                str(resolve_data_path(image_path)),
            )
        image_item.setFlags(
            image_item.flags() & ~Qt.ItemFlag.ItemIsEditable
        )
        self.setItem(row, self.IMAGE_COLUMN, image_item)

        item_code = QTableWidgetItem(product.code)
        item_code.setData(Qt.ItemDataRole.UserRole, product.id)
        item_code.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, self.CODE_COLUMN, item_code)
        self._set_text_item(row, self.NAME_COLUMN, product.name)
        detail = self._format_detail(product)
        self._set_text_item(row, self.DETAIL_COLUMN, detail)
        detail_item = self.item(row, self.DETAIL_COLUMN)
        if detail_item is not None:
            detail_item.setTextAlignment(
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            )
        self._set_category_item(row, product.category)
        self._set_stock_widget(row, product)
        self._set_price_item(row, self.PRICE_SAMPLE_COLUMN, product.price_sample)
        self._set_price_item(row, self.PRICE_HUNDRED_COLUMN, product.price_hundred)
        self._set_price_item(row, self.PRICE_THOUSAND_COLUMN, product.price_thousand)

    @staticmethod
    def _product_gallery(product: Product) -> list[dict]:
        gallery = [
            dict(image)
            for image in list(getattr(product, "gallery_images", []) or [])
            if isinstance(image, dict)
        ]
        if gallery:
            return gallery
        if product.image_path:
            return [
                {
                    "url": product.image_url,
                    "image_path": product.image_path,
                    "image_hash": product.image_hash,
                    "position": 1,
                    "source": "primary",
                }
            ]
        return []

    def set_gallery_overrides(self, overrides: dict[str, list[dict]]) -> None:
        """Actualiza galerías descargadas en vivo sin reconstruir las filas."""
        normalized = {
            str(code).strip().casefold(): [
                dict(option)
                for option in list(images or [])
                if isinstance(option, dict)
                and str(
                    option.get("path", option.get("image_path", ""))
                    or ""
                ).strip()
            ]
            for code, images in (overrides or {}).items()
            if str(code).strip()
        }
        previous_codes = set(self._gallery_overrides)
        self._gallery_overrides = normalized
        changed = False
        for code in previous_codes | set(normalized):
            options = normalized.get(code, [])
            row = self._row_by_code.get(code)
            if row is None:
                continue
            item = self.item(row, self.IMAGE_COLUMN)
            if item is None:
                continue
            gallery = self._product_gallery(self._rendered_products[row])
            seen = {
                str(image.get("url", "") or "").strip().casefold()
                for image in gallery
                if isinstance(image, dict)
            }
            changed_for_row = False
            for option in options:
                url = str(option.get("url", "") or "").strip()
                if not url or url.casefold() in seen:
                    continue
                gallery.append(dict(option))
                seen.add(url.casefold())
                changed_for_row = True
            current_gallery = item.data(ProductImageDelegate.GALLERY_ROLE)
            current_urls = [
                str(image.get("url", "") or "").strip().casefold()
                for image in list(current_gallery or [])
                if isinstance(image, dict)
            ]
            next_urls = [
                str(image.get("url", "") or "").strip().casefold()
                for image in gallery
                if isinstance(image, dict)
            ]
            if current_urls == next_urls and not changed_for_row:
                continue
            changed = True
            active_index = item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE)
            try:
                active_index = int(active_index) % len(gallery)
            except (TypeError, ValueError):
                active_index = 0
            item.setData(ProductImageDelegate.GALLERY_ROLE, gallery)
            item.setData(ProductImageDelegate.ACTIVE_INDEX_ROLE, active_index)
            self._set_image_item_path(item, gallery, active_index)
        if changed:
            self.viewport().update()

    @staticmethod
    def _set_image_item_path(
        item: QTableWidgetItem,
        gallery: list[dict],
        active_index: int,
    ) -> None:
        if not gallery:
            item.setData(ProductImageDelegate.IMAGE_ROLE, "")
            return
        selected = gallery[active_index]
        image_path = str(
            selected.get("image_path", selected.get("path", ""))
            if isinstance(selected, dict)
            else ""
        ).strip()
        item.setData(
            ProductImageDelegate.IMAGE_ROLE,
            str(resolve_data_path(image_path)) if image_path else "",
        )

    def mousePressEvent(self, event) -> None:
        position = event.position().toPoint()
        index = self.indexAt(position)
        if (
            event.button() == Qt.MouseButton.LeftButton
            and index.isValid()
            and index.column() == self.IMAGE_COLUMN
        ):
            item = self.item(index.row(), self.IMAGE_COLUMN)
            if item is None:
                super().mousePressEvent(event)
                return
            gallery = item.data(ProductImageDelegate.GALLERY_ROLE)
            if isinstance(gallery, list) and len(gallery) > 1:
                rect = self.visualRect(index)
                active = item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE)
                try:
                    active_index = int(active)
                except (TypeError, ValueError):
                    active_index = 0
                if position.x() <= rect.left() + 34:
                    self._set_active_image(index.row(), active_index - 1)
                    event.accept()
                    return
                if position.x() >= rect.right() - 34:
                    self._set_active_image(index.row(), active_index + 1)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def _set_active_image(self, row: int, active_index: int) -> None:
        item = self.item(row, self.IMAGE_COLUMN)
        if item is None:
            return
        gallery = item.data(ProductImageDelegate.GALLERY_ROLE)
        if not isinstance(gallery, list) or not gallery:
            return
        active_index %= len(gallery)
        item.setData(ProductImageDelegate.ACTIVE_INDEX_ROLE, active_index)
        self._set_image_item_path(item, gallery, active_index)
        if 0 <= row < len(self._rendered_products):
            code = str(self._rendered_products[row].code).strip().casefold()
            if code:
                self._active_image_indices[code] = active_index
        self.viewport().update()

    @staticmethod
    def _detail_comparison_key(value: str) -> str:
        normalized = (
            unicodedata.normalize("NFKD", str(value))
            .encode("ascii", "ignore")
            .decode("ascii")
            .casefold()
        )
        return re.sub(r"[^\w]+", " ", normalized).strip()

    @staticmethod
    def _correct_detail_spelling(value: str) -> str:
        replacements = {
            "flurecente": "fluorescente",
            "fluorecente": "fluorescente",
            "carton": "cartón",
        }
        corrected = value
        for incorrect, correct in replacements.items():
            corrected = re.sub(
                rf"\b{incorrect}\b",
                lambda match, replacement=correct: (
                    replacement.capitalize()
                    if match.group().istitle()
                    else replacement.upper()
                    if match.group().isupper()
                    else replacement
                ),
                corrected,
                flags=re.IGNORECASE,
            )
        return corrected

    @classmethod
    def _format_detail(cls, product: Product) -> str:
        """Ordena los atributos del detalle y quita duplicados de la fila."""
        raw = cls._correct_detail_spelling(str(product.description or ""))
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        raw = re.sub(r"[ \t]+", " ", raw).strip()
        if not raw:
            return ""

        matches = list(cls.DETAIL_FIELD_LABEL_PATTERN.finditer(raw))
        if not matches:
            lines = []
            for candidate in raw.splitlines():
                cleaned = re.sub(r"[ \t.;]+$", "", candidate.strip())
                if cleaned:
                    lines.append(cleaned)
            return "\n".join(lines)

        lines: list[str] = []
        prefix = raw[: matches[0].start()].strip(" \t\r\n.;")
        if prefix:
            lines.append(re.sub(r"[ \t.;]+$", "", prefix))

        for index, match in enumerate(matches):
            next_start = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(raw)
            )
            alias = match.group(1).casefold()
            label = cls.DETAIL_FIELD_LABELS.get(alias, match.group(1).strip())
            value = raw[match.end() : next_start]
            value = re.sub(r"^[ \t\r\n.;]+", "", value)
            value = re.sub(r"[ \t\r\n.;]+$", "", value)
            value = re.sub(r"\s+", " ", value).strip()
            if not value or cls._detail_field_duplicates_row(
                label,
                value,
                product,
            ):
                continue
            lines.append(f"{label}: {value}".rstrip(" ."))

        return "\n".join(line for line in lines if line.strip())

    @classmethod
    def _detail_field_duplicates_row(
        cls,
        label: str,
        value: str,
        product: Product,
    ) -> bool:
        label_key = cls._detail_comparison_key(label)
        value_key = cls._detail_comparison_key(value)

        if label_key == "color":
            row_colors = {
                cls._detail_comparison_key(color)
                for color in product.color_stock
            }
            described_colors = [
                cls._detail_comparison_key(color)
                for color in re.split(r"\s*[,;/]\s*", value)
                if color.strip()
            ]
            return bool(row_colors and described_colors) and all(
                color in row_colors for color in described_colors
            )
        if label_key in {"codigo"}:
            return value_key == cls._detail_comparison_key(product.code)
        if label_key in {"producto", "nombre"}:
            return value_key == cls._detail_comparison_key(product.name)
        if label_key in {"categoria"}:
            categories = {
                cls._detail_comparison_key(category)
                for category in split_category_names(product.category)
            }
            categories.add(cls._detail_comparison_key(product.category))
            return value_key in categories
        if label_key == "stock":
            digits = re.sub(r"[^0-9]", "", value)
            try:
                return bool(digits) and int(digits) == product.stock
            except ValueError:
                return False

        price_fields = {
            "precio": (product.price_sample, product.price_hundred, product.price_thousand),
            "precio muestra": (product.price_sample,),
            "precio ciento": (product.price_hundred,),
            "precio millar": (product.price_thousand,),
        }
        expected_prices = price_fields.get(label_key)
        if expected_prices is not None:
            normalized_number = value.replace(",", "").replace("S/", "").strip()
            try:
                number = float(normalized_number)
            except ValueError:
                return False
            return any(abs(number - price) < 0.005 for price in expected_prices)
        return False

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
        item = self.item(row, self.CATEGORY_COLUMN)
        if item is not None:
            item.setData(self.CATEGORY_SOURCE_ROLE, category)

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
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, self.STOCK_COLUMN, item)

    @classmethod
    def _stock_color_style(cls, color: str) -> tuple[str, str]:
        """Devuelve fondo e indicador para el color comercial recibido."""
        normalized = " ".join(color.strip().casefold().split())
        style = cls.STOCK_COLOR_STYLES.get(normalized)
        if style is not None:
            return style

        qcolor = QColor(color)
        if qcolor.isValid():
            return qcolor.lighter(185).name().lower(), qcolor.name().lower()

        # Nombres personalizados reciben una tonalidad determinista, para que
        # cambiar el nombre del color actualice tanto el círculo como el fondo.
        hue = sum((index + 1) * ord(char) for index, char in enumerate(normalized))
        indicator = QColor.fromHsv(hue % 360, 145, 210)
        return indicator.lighter(185).name().lower(), indicator.name().lower()

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
        detail_item = self.item(row, self.DETAIL_COLUMN)
        if detail_item is not None and detail_item.text():
            detail_height = ProductDetailDelegate.content_height(
                detail_item.text(),
                self.font(),
                max(self.columnWidth(self.DETAIL_COLUMN) - 8, 1),
            ) + (2 * ProductDetailDelegate.VERTICAL_PADDING)
            row_height = max(row_height, detail_height)

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
        return max(
            self.MIN_COLUMN_WIDTHS[self.CATEGORY_COLUMN],
            metrics.horizontalAdvance(self.CATEGORY_REFERENCE_TEXT)
            + (2 * self.CONTENT_SIDE_PADDING),
        )

    def _preferred_column_widths(self, header: QHeaderView) -> list[int]:
        cached = self._preferred_widths_cache
        if cached is None:
            self.resizeColumnsToContents()
            minimum_widths = [
                self.MIN_COLUMN_WIDTHS[column]
                for column in range(self.columnCount())
            ]
            minimum_widths[self.CATEGORY_COLUMN] = self._category_minimum_width()
            minimum_widths[self.IMAGE_COLUMN] = self.IMAGE_SIZE
            minimum_widths[self.STOCK_COLUMN] = self._stock_minimum_width()
            preferred_widths = [
                max(
                    header.sectionSize(column),
                    minimum_widths[column],
                )
                for column in range(self.columnCount())
            ]
            if self._stable_code_width is None and self._rendered_products:
                self._stable_code_width = max(
                    header.sectionSize(self.CODE_COLUMN),
                    minimum_widths[self.CODE_COLUMN],
                )
            preferred_widths[self.CODE_COLUMN] = (
                self._stable_code_width
                if self._stable_code_width is not None
                else minimum_widths[self.CODE_COLUMN]
            )
            preferred_widths[self.IMAGE_COLUMN] = self.IMAGE_SIZE
            price_savings = 0
            for price_column in (
                self.PRICE_SAMPLE_COLUMN,
                self.PRICE_HUNDRED_COLUMN,
                self.PRICE_THOUSAND_COLUMN,
            ):
                fixed_price_width = self.FIXED_PRICE_COLUMN_WIDTH
                price_savings += max(
                    self.DEFAULT_PRICE_COLUMN_WIDTH - fixed_price_width,
                    0,
                )
                preferred_widths[price_column] = fixed_price_width
            preferred_widths[self.CATEGORY_COLUMN] = (
                minimum_widths[self.CATEGORY_COLUMN]
            )
            preferred_widths[self.DETAIL_COLUMN] += price_savings
            # Stock debe conservar exclusivamente el ancho calculado por su
            # contenido, sin el margen adicional que Qt puede introducir al
            # aplicar resizeColumnsToContents().
            preferred_widths[self.STOCK_COLUMN] = minimum_widths[self.STOCK_COLUMN]
            self._preferred_widths_cache = preferred_widths
            cached = preferred_widths
        return cached.copy()

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
            if self._stable_code_width is not None:
                minimum_widths[self.CODE_COLUMN] = self._stable_code_width
            minimum_total = sum(minimum_widths)
            available_width = self.viewport().width()
            target_width = max(available_width, minimum_total)
            widths = self._allocate_column_widths(
                preferred_widths,
                minimum_widths,
                target_width,
                growable_columns={self.DETAIL_COLUMN},
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
