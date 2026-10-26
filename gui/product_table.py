import html
import re
import unicodedata
from typing import ClassVar

from PySide6.QtCore import QEvent, QPointF, QRect, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QFontMetricsF,
    QHelpEvent,
    QImageReader,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
    QPixmapCache,
    QTextCharFormat,
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
    QToolTip,
    QWidget,
)

from config.runtime_paths import resolve_data_path
from controllers.product_controller import ProductController
from gui.product_category_delegate import ProductCategoryDelegate
from models.product import Product
from models.product_image_gallery import normalize_product_gallery
from models.scraping.detail_description_policy import normalize_detail_text
from services.scraping.category_name_normalizer import (
    display_category_name,
    split_category_names,
)


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


class ProductCellDelegate(QStyledItemDelegate):
    """Quita el marco de enfoque nativo y conserva el borde de selección propio."""

    def initStyleOption(
        self,
        option: QStyleOptionViewItem,
        index,
    ) -> None:
        super().initStyleOption(option, index)
        option.state &= ~QStyle.StateFlag.State_HasFocus

    def paint_item_background(self, painter, option, index) -> None:
        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)
        style_option.text = ""
        widget = style_option.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            style_option,
            painter,
            widget,
        )

    def paint(self, painter, option, index) -> None:
        # Preserve ordinary cell text (notably Código) while removing the
        # native focus rectangle from the style option before drawing.
        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)
        widget = style_option.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            style_option,
            painter,
            widget,
        )


class PriceDelegate(ProductCellDelegate):
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

    def paint(self, painter: QPainter, option, index) -> None:
        """Render the price on one line, even when the cell is narrow."""
        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)
        text = style_option.text
        style_option.text = ""
        widget = style_option.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            style_option,
            painter,
            widget,
        )

        painter.save()
        painter.setFont(style_option.font)
        painter.setPen(style_option.palette.color(QPalette.ColorRole.Text))
        text_rect = style_option.rect.adjusted(4, 0, -4, 0)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter
            | Qt.AlignmentFlag.AlignVCenter
            | Qt.TextFlag.TextSingleLine,
            text,
        )
        painter.restore()


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


class ProductCodeCategoryDelegate(ProductCellDelegate):
    """Muestra el código y sus categorías relacionadas en una sola celda."""

    CATEGORY_SOURCE_ROLE = int(Qt.ItemDataRole.UserRole) + 50
    CATEGORY_COLUMN = 4
    HORIZONTAL_PADDING = 6
    VERTICAL_PADDING = 6
    LINE_GAP = 3
    CATEGORY_FONT_SIZE = 11

    @staticmethod
    def _category_text(index) -> str:
        category_index = index.sibling(index.row(), ProductCodeCategoryDelegate.CATEGORY_COLUMN)
        return str(
            category_index.data(Qt.ItemDataRole.DisplayRole)
            or category_index.data(ProductCodeCategoryDelegate.CATEGORY_SOURCE_ROLE)
            or "—"
        )

    def paint(self, painter: QPainter, option, index) -> None:
        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)
        style_option.text = ""
        style = (
            style_option.widget.style()
            if style_option.widget is not None
            else QApplication.style()
        )
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            style_option,
            painter,
            style_option.widget,
        )

        code = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        categories = self._category_text(index)
        content_rect = option.rect.adjusted(
            self.HORIZONTAL_PADDING,
            self.VERTICAL_PADDING,
            -self.HORIZONTAL_PADDING,
            -self.VERTICAL_PADDING,
        )
        code_font = QFont(option.font)
        code_font.setBold(True)
        category_font = QFont(option.font)
        category_font.setBold(False)
        category_font.setPixelSize(self.CATEGORY_FONT_SIZE)

        painter.save()
        painter.setFont(code_font)
        painter.setPen(QColor("#173f6d"))
        code_height = QFontMetrics(code_font).height()
        painter.drawText(
            QRect(
                content_rect.left(),
                content_rect.top(),
                content_rect.width(),
                code_height + 1,
            ),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            code,
        )

        painter.setFont(category_font)
        painter.setPen(QColor("#64748b"))
        category_rect = QRect(
            content_rect.left(),
            content_rect.top() + code_height + self.LINE_GAP,
            content_rect.width(),
            max(content_rect.height() - code_height - self.LINE_GAP, 1),
        )
        painter.drawText(
            category_rect,
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap,
            categories,
        )
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        width = max(option.rect.width() - 2 * self.HORIZONTAL_PADDING, 80)
        category_font = QFont(option.font)
        category_font.setPixelSize(self.CATEGORY_FONT_SIZE)
        category_metrics = QFontMetrics(category_font)
        category_bounds = category_metrics.boundingRect(
            QRect(0, 0, width, 1000),
            Qt.TextFlag.TextWordWrap,
            self._category_text(index),
        )
        code_font = QFont(option.font)
        code_font.setBold(True)
        code_height = QFontMetrics(code_font).height()
        return QSize(
            112,
            self.VERTICAL_PADDING * 2
            + code_height
            + self.LINE_GAP
            + max(category_bounds.height(), category_metrics.height()),
        )


class ProductNameCategoryDelegate(ProductCodeCategoryDelegate):
    """Muestra el nombre y sus categorías centrados en la misma celda."""

    HORIZONTAL_PADDING = 8
    VERTICAL_PADDING = 8
    LINE_GAP = 4
    CATEGORY_FONT_SIZE = 11
    PREFERRED_WIDTH = 170 + (2 * HORIZONTAL_PADDING)

    @classmethod
    def _wrapped_height(cls, text: str, font: QFont, width: int) -> int:
        metrics = QFontMetrics(font)
        bounds = metrics.boundingRect(
            QRect(0, 0, max(width, 1), 1000),
            Qt.TextFlag.TextWordWrap,
            text or " ",
        )
        return max(bounds.height(), metrics.height())

    @classmethod
    def content_height(
        cls,
        name: str,
        categories: str,
        font: QFont,
        width: int,
    ) -> int:
        content_width = max(width - (2 * cls.HORIZONTAL_PADDING), 1)
        name_font = QFont(font)
        name_font.setBold(True)
        category_font = QFont(font)
        category_font.setPixelSize(cls.CATEGORY_FONT_SIZE)
        name_height = cls._wrapped_height(name, name_font, content_width)
        category_height = cls._wrapped_height(
            categories or "—",
            category_font,
            content_width,
        )
        return (
            (2 * cls.VERTICAL_PADDING)
            + name_height
            + cls.LINE_GAP
            + category_height
        )

    def paint(self, painter: QPainter, option, index) -> None:
        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)
        style_option.text = ""
        style = (
            style_option.widget.style()
            if style_option.widget is not None
            else QApplication.style()
        )
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            style_option,
            painter,
            style_option.widget,
        )

        name = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        categories = self._category_text(index)
        content_rect = option.rect.adjusted(
            self.HORIZONTAL_PADDING,
            self.VERTICAL_PADDING,
            -self.HORIZONTAL_PADDING,
            -self.VERTICAL_PADDING,
        )
        name_font = QFont(option.font)
        name_font.setBold(True)
        category_font = QFont(option.font)
        category_font.setBold(False)
        category_font.setPixelSize(self.CATEGORY_FONT_SIZE)

        content_width = max(content_rect.width(), 1)
        name_height = self._wrapped_height(name, name_font, content_width)
        category_height = self._wrapped_height(
            categories or "—",
            category_font,
            content_width,
        )
        group_height = name_height + self.LINE_GAP + category_height
        top = content_rect.top() + max(
            (content_rect.height() - group_height) // 2,
            0,
        )

        painter.save()
        painter.setFont(name_font)
        painter.setPen(QColor("#173f6d"))
        painter.drawText(
            QRect(content_rect.left(), top, content_width, name_height),
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
            | Qt.TextFlag.TextWordWrap,
            name,
        )
        category_rect = QRect(
            content_rect.left(),
            top + name_height + self.LINE_GAP,
            content_width,
            category_height,
        )
        painter.setFont(category_font)
        painter.setPen(QColor("#64748b"))
        painter.drawText(
            category_rect,
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
            | Qt.TextFlag.TextWordWrap,
            categories or "—",
        )
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        width = option.rect.width() or self.PREFERRED_WIDTH
        height = self.content_height(
            str(index.data(Qt.ItemDataRole.DisplayRole) or ""),
            self._category_text(index),
            option.font,
            width,
        )
        return QSize(self.PREFERRED_WIDTH, height)


class ProductImageDelegate(ProductCellDelegate):
    """Dibuja la imagen principal a escala proporcional y sus miniaturas."""

    MAIN_IMAGE_WIDTH = 144
    MIN_PRIMARY_IMAGE_DISPLAY_SIZE = 144
    THUMBNAIL_HEIGHT = 34
    THUMBNAIL_STRIP_HEIGHT = 34
    THUMBNAIL_GAP = 0
    THUMBNAIL_PADDING = 0
    # Keep a single table-grid pixel visible on every outer edge.
    CELL_HORIZONTAL_PADDING = 1
    CELL_VERTICAL_PADDING = 1
    GRIDLINE_RIGHT_ALLOWANCE = 1
    GRIDLINE_BOTTOM_ALLOWANCE = 1
    DEFAULT_SIZE = (
        MAIN_IMAGE_WIDTH
        + (2 * CELL_HORIZONTAL_PADDING)
        + GRIDLINE_RIGHT_ALLOWANCE
    )
    # Reserve 144 px for the main preview and room for the thumbnail strip.
    # This keeps portrait previews from being reduced merely to make room for
    # the alternatives along the bottom of the cell.
    DEFAULT_HEIGHT = (
        MIN_PRIMARY_IMAGE_DISPLAY_SIZE
        + THUMBNAIL_STRIP_HEIGHT
        + THUMBNAIL_GAP
        + (2 * CELL_VERTICAL_PADDING)
        + GRIDLINE_BOTTOM_ALLOWANCE
    )
    MAX_VISIBLE_THUMBNAILS = 4
    IMAGE_ROLE = int(Qt.ItemDataRole.UserRole) + 1
    GALLERY_ROLE = int(Qt.ItemDataRole.UserRole) + 3
    ACTIVE_INDEX_ROLE = int(Qt.ItemDataRole.UserRole) + 4
    THUMBNAIL_START_ROLE = int(Qt.ItemDataRole.UserRole) + 5
    _image_size_cache: ClassVar[dict[str, QSize]] = {}

    @classmethod
    def main_image_size(
        cls,
        image_path: str,
        display_width: int | None = None,
    ) -> QSize:
        """Return the image's proportional size at the fixed base display width."""
        del display_width
        display_width = cls.MAIN_IMAGE_WIDTH
        resolved = str(resolve_data_path(image_path)) if image_path else ""
        if not resolved:
            return QSize(cls.MAIN_IMAGE_WIDTH, cls.MAIN_IMAGE_WIDTH)

        cache_key = resolved
        cached = cls._image_size_cache.get(cache_key)
        if cached is not None:
            return QSize(cached)

        cached_pixmap = QPixmap()
        if QPixmapCache.find(f"fcm-product-image:{resolved}", cached_pixmap):
            source_size = cached_pixmap.size()
        else:
            # Read image metadata only; row sizing should not decode all catalog images.
            source_size = QImageReader(resolved).size()
        if source_size.width() <= 0 or source_size.height() <= 0:
            return QSize(display_width, display_width)

        size = QSize(
            display_width,
            max(
                round(source_size.height() * display_width / source_size.width()),
                1,
            ),
        )
        cls._image_size_cache[cache_key] = QSize(size)
        return size

    @classmethod
    def main_image_height(
        cls,
        image_path: str,
        display_width: int | None = None,
    ) -> int:
        return cls.main_image_size(image_path, display_width).height()

    @classmethod
    def thumbnail_layout(
        cls,
        rect: QRect,
        image_count: int,
        thumbnail_start: int = 0,
        *,
        active_index: int = 0,
        main_height: int | None = None,
        thumbnail_top: int | None = None,
    ) -> tuple[list[tuple[int, QRect]], QRect | None, QRect | None, int]:
        """Lay out thumbnails in gallery order; the active index affects only paint."""
        del active_index
        strip_top = (
            thumbnail_top
            if thumbnail_top is not None
            else rect.top()
            + (
                main_height
                if main_height is not None
                else cls.MAIN_IMAGE_WIDTH
            )
        )
        thumbnail_indexes = list(range(max(image_count, 0)))
        thumbnail_count = len(thumbnail_indexes)
        if thumbnail_count == 0:
            return [], None, None, strip_top

        thumbnail_height = cls.THUMBNAIL_HEIGHT
        gap = cls.THUMBNAIL_GAP
        left_arrow = None
        right_arrow = None

        if thumbnail_count > cls.MAX_VISIBLE_THUMBNAILS:
            visible_count = cls.MAX_VISIBLE_THUMBNAILS
            arrow_width = min(12, max(rect.width() // 10, 1))
            left_arrow = QRect(
                rect.left(),
                strip_top,
                arrow_width,
                thumbnail_height,
            )
            right_arrow = QRect(
                rect.right() - arrow_width + 1,
                strip_top,
                arrow_width,
                thumbnail_height,
            )
            left = left_arrow.right() + 1 + gap
            right = right_arrow.left() - 1 - gap
            available_width = max(right - left + 1, 1)
            tile_width = max(
                (
                    available_width
                    - gap * (visible_count - 1)
                ) // visible_count,
                1,
            )
            max_start = max(thumbnail_count - visible_count, 0)
            start = max(0, min(thumbnail_start, max_start))
            visible_indices = thumbnail_indexes[start : start + visible_count]
            tiles = [
                (
                    image_index,
                    QRect(
                        left + position * (tile_width + gap),
                        strip_top,
                        tile_width,
                        thumbnail_height,
                    ),
                )
                for position, image_index in enumerate(visible_indices)
            ]
            return tiles, left_arrow, right_arrow, strip_top

        tile_width = max(
            (
                max(rect.width(), 1)
                - gap * (cls.MAX_VISIBLE_THUMBNAILS - 1)
            ) // cls.MAX_VISIBLE_THUMBNAILS,
            1,
        )
        group_width = thumbnail_count * tile_width + gap * (thumbnail_count - 1)
        left = rect.left() + max((rect.width() - group_width) // 2, 0)
        tiles = [
            (
                image_index,
                QRect(
                    left + position * (tile_width + gap),
                    strip_top,
                    tile_width,
                    thumbnail_height,
                ),
            )
            for position, image_index in enumerate(thumbnail_indexes)
        ]
        return tiles, left_arrow, right_arrow, strip_top

    @staticmethod
    def _active_index(gallery: list, value: object) -> int:
        if not gallery:
            return 0
        if isinstance(value, int):
            return value % len(gallery)
        if isinstance(value, str):
            try:
                return int(value) % len(gallery)
            except ValueError:
                return 0
        return 0

    @staticmethod
    def _selected_path(gallery: list, active_index: int, fallback: object) -> str:
        if gallery and isinstance(gallery[active_index], dict):
            selected = gallery[active_index]
            path = selected.get("image_path", selected.get("path", fallback))
            if isinstance(path, str) and path.strip():
                return str(resolve_data_path(path))
        return str(fallback or "")

    @classmethod
    def cell_content_rect(cls, rect: QRect) -> QRect:
        """Return the drawable cell area without covering the grid lines."""
        horizontal_inset = min(
            cls.CELL_HORIZONTAL_PADDING,
            max((rect.width() - 1) // 2, 0),
        )
        vertical_inset = min(
            cls.CELL_VERTICAL_PADDING,
            max((rect.height() - 1) // 2, 0),
        )
        return QRect(
            rect.left() + horizontal_inset,
            rect.top() + vertical_inset,
            max(rect.width() - (2 * horizontal_inset), 1),
            max(rect.height() - (2 * vertical_inset), 1),
        )

    @staticmethod
    def fitted_image_rect(source_size: QSize, available_rect: QRect) -> QRect:
        """Calculate a centered, aspect-preserving image rect inside a cell."""
        if (
            source_size.width() <= 0
            or source_size.height() <= 0
            or available_rect.width() <= 0
            or available_rect.height() <= 0
        ):
            return QRect()
        scaled_size = source_size.scaled(
            available_rect.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        return QRect(
            available_rect.left()
            + (available_rect.width() - scaled_size.width()) // 2,
            available_rect.top()
            + (available_rect.height() - scaled_size.height()) // 2,
            scaled_size.width(),
            scaled_size.height(),
        )

    def _paint_main_preview(
        self,
        painter: QPainter,
        rect: QRect,
        image_path: str,
    ) -> QRect:
        if rect.width() <= 0 or rect.height() <= 0 or not image_path:
            return QRect()
        pixmap = self._load_pixmap(str(resolve_data_path(image_path)))
        if pixmap.isNull():
            return QRect()
        image_rect = self.fitted_image_rect(pixmap.size(), rect)
        if image_rect.isEmpty():
            return QRect()
        scaled = pixmap.scaled(
            image_rect.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        image_rect = QRect(
            rect.left() + (rect.width() - scaled.width()) // 2,
            rect.top() + (rect.height() - scaled.height()) // 2,
            scaled.width(),
            scaled.height(),
        )
        painter.drawPixmap(image_rect.topLeft(), scaled)
        return image_rect

    @classmethod
    def main_image_layout(
        cls,
        rect: QRect,
        image_path: str,
        *,
        has_thumbnails: bool,
    ) -> tuple[QRect, int]:
        """Center the main preview and anchor alternatives directly beneath it."""
        content_rect = cls.cell_content_rect(rect)
        preview_width = cls.MAIN_IMAGE_WIDTH
        resolved = str(resolve_data_path(image_path)) if image_path else ""
        pixmap = cls._load_pixmap(resolved) if resolved else QPixmap()
        if pixmap.isNull() or pixmap.width() <= 0:
            preview_size = QSize(preview_width, preview_width)
        else:
            preview_size = QSize(
                preview_width,
                max(
                    round(pixmap.height() * preview_width / pixmap.width()),
                    1,
                ),
            )
        group_height = preview_size.height()
        if has_thumbnails:
            group_height += cls.THUMBNAIL_GAP + cls.THUMBNAIL_STRIP_HEIGHT
        group_top = content_rect.top() + max(
            (content_rect.height() - group_height) // 2,
            0,
        )
        # The image column is sized to the preview plus a one-pixel gridline
        # inset. Do not center in an odd-width item rect: integer rounding can
        # move the image onto the left gridline.
        image_rect = QRect(
            rect.left() + cls.CELL_HORIZONTAL_PADDING,
            group_top,
            preview_size.width(),
            preview_size.height(),
        )
        thumbnail_top = image_rect.bottom() + 1 + cls.THUMBNAIL_GAP
        return image_rect, thumbnail_top

    @classmethod
    def thumbnail_strip_top(
        cls,
        rect: QRect,
        image_path: str = "",
        *,
        has_thumbnails: bool = True,
    ) -> int:
        """Return the centered strip position immediately under the main image."""
        return cls.main_image_layout(
            rect,
            image_path,
            has_thumbnails=has_thumbnails,
        )[1]

    def _paint_thumbnail_strip(
        self,
        painter: QPainter,
        rect: QRect,
        gallery: list,
        active_index: int,
        thumbnail_start: int,
        thumbnail_top: int,
    ) -> None:
        tiles, left_arrow, right_arrow, _ = self.thumbnail_layout(
            rect,
            len(gallery),
            thumbnail_start,
            active_index=active_index,
            thumbnail_top=thumbnail_top,
        )
        for image_index, tile_rect in tiles:
            image = gallery[image_index]
            path = ""
            if isinstance(image, dict):
                path = str(image.get("image_path", image.get("path", "")) or "").strip()
            painter.fillRect(tile_rect, QColor("#ffffff"))
            inner = tile_rect
            if path and inner.width() > 0 and inner.height() > 0:
                thumb = self._load_pixmap(str(resolve_data_path(path)))
                if not thumb.isNull():
                    thumb = thumb.scaled(
                        inner.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    thumb_x = inner.left() + (inner.width() - thumb.width()) // 2
                    thumb_y = inner.top() + (inner.height() - thumb.height()) // 2
                    painter.drawPixmap(thumb_x, thumb_y, thumb)
            selected_thumbnail = image_index == active_index
            painter.setPen(
                QPen(
                    QColor("#1675e8" if selected_thumbnail else "#cbd5e1"),
                    1,
                ),
            )
            painter.drawRect(tile_rect.adjusted(0, 0, -1, -1))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.setPen(QColor("#334e68"))
        if left_arrow is not None:
            painter.drawText(left_arrow, Qt.AlignmentFlag.AlignCenter, "<")
        if right_arrow is not None:
            painter.drawText(right_arrow, Qt.AlignmentFlag.AlignCenter, ">")

    def paint(self, painter: QPainter, option, index) -> None:
        super().paint(painter, option, index)
        raw_gallery = index.data(self.GALLERY_ROLE)
        gallery = raw_gallery if isinstance(raw_gallery, list) else []
        active_index = self._active_index(gallery, index.data(self.ACTIVE_INDEX_ROLE))
        try:
            thumbnail_start = max(int(index.data(self.THUMBNAIL_START_ROLE) or 0), 0)
        except (TypeError, ValueError):
            thumbnail_start = 0
        image_path = self._selected_path(gallery, active_index, index.data(self.IMAGE_ROLE))
        cell = self.cell_content_rect(option.rect)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        image_rect, thumbnail_top = self.main_image_layout(
            option.rect,
            image_path,
            has_thumbnails=len(gallery) > 1,
        )
        self._paint_main_preview(painter, image_rect, image_path)
        if len(gallery) > 1:
            self._paint_thumbnail_strip(
                painter,
                cell,
                gallery,
                active_index,
                thumbnail_start,
                thumbnail_top,
            )
        painter.restore()

        # The preview fills the cell vertically, so redraw the selected-cell
        # frame last to keep it visible above the image and thumbnail pixels.
        if option.state & QStyle.StateFlag.State_Selected:
            painter.save()
            painter.setPen(QPen(QColor("#1675e8"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(option.rect.adjusted(0, 0, -1, -1))
            painter.restore()

    @staticmethod
    def _load_pixmap(image_path: str) -> QPixmap:
        """Load images lazily and cache decoded pixmaps in Qt."""
        cache_key = f"fcm-product-image:{image_path}"
        pixmap = QPixmap()
        if QPixmapCache.find(cache_key, pixmap):
            return pixmap
        pixmap.load(image_path)
        if not pixmap.isNull():
            QPixmapCache.insert(cache_key, pixmap)
        return pixmap

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        del option, index
        return QSize(self.DEFAULT_SIZE, self.DEFAULT_HEIGHT)


class StockColorDelegate(ProductCellDelegate):
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
    HORIZONTAL_PADDING = 5
    TEXT_HORIZONTAL_PADDING = 4
    TEXT_GAP = 4
    MIN_LINE_HEIGHT = 24
    TEXT_COLOR = "#173f6d"

    def paint(self, painter: QPainter, option, index) -> None:
        self.paint_item_background(painter, option, index)
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
            indicator = ProductTable._stock_color_style(color)[1]

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
            # Fondo neutro: el círculo codifica el color sin teñir toda la fila.

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


class ProductDetailDelegate(ProductCellDelegate):
    """Renderiza el detalle con interlineado compacto y ajuste de texto."""

    HORIZONTAL_PADDING = 8
    VERTICAL_PADDING = 8
    LINE_SPACING_REDUCTION = 1
    PARAGRAPH_SPACING_REDUCTION = 2
    GRIDLINE_ALLOWANCE = 1
    # Bold labels at the start of a line or sentence. A colon inside a value
    # such as "(área de impresión recomendada: ...)" is not another label.
    # Numbered labels like "1. Estuche:" are also supported.
    _BOLD_DETAIL_LABEL_PATTERN = re.compile(
        r"(?:(?<=^)|(?<=[.!?]\s))(?:\s*\d+\.\s*)?([A-ZÁÉÍÓÚÜÑ][^:\n]{0,60}):"
    )

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
        for paragraph_index, paragraph in enumerate(paragraphs):
            layout = QTextLayout(paragraph, font)
            formats: list[QTextLayout.FormatRange] = []
            for match in cls._BOLD_DETAIL_LABEL_PATTERN.finditer(paragraph):
                label_key = " ".join(match.group(1).split()).casefold()
                if label_key in {
                    "peso bruto / caja",
                    "peso neto / caja",
                    "medidas de la caja máster",
                }:
                    continue
                char_format = QTextCharFormat()
                char_format.setFontWeight(QFont.Weight.Bold)
                format_range = QTextLayout.FormatRange()
                format_range.start = match.start(1)
                format_range.length = match.end() - match.start(1)
                format_range.format = char_format
                formats.append(format_range)
            layout.setFormats(formats)
            text_option = QTextOption()
            text_option.setWrapMode(
                QTextOption.WrapMode.WordWrap,
            )
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
            if paragraph_index < len(paragraphs) - 1:
                total_height += max(
                    paragraph_height - cls.PARAGRAPH_SPACING_REDUCTION,
                    1,
                )
            else:
                total_height += paragraph_height
        return layouts, round(total_height)

    @classmethod
    def content_height(cls, text: str, font: QFont, width: int) -> int:
        if not text:
            return 0
        _, height = cls._layout_text(text, font, width)
        return height

    @classmethod
    def _vertical_text_offset(cls, rect_height: int, content_height: int) -> float:
        """Center short detail blocks and keep a safe inset for taller content."""
        return max(
            (rect_height - content_height) / 2,
            float(cls.VERTICAL_PADDING),
        )

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
        layouts, layout_height = self._layout_text(
            text,
            styled_option.font,
            text_width,
        )
        vertical_text_offset = self._vertical_text_offset(
            styled_option.rect.height(),
            layout_height,
        )
        painter.save()
        painter.setPen(styled_option.palette.color(QPalette.ColorRole.Text))
        for layout, top_offset in layouts:
            layout.draw(
                painter,
                QPointF(
                    styled_option.rect.left() + self.HORIZONTAL_PADDING,
                    styled_option.rect.top() + vertical_text_offset + top_offset,
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
    TEXT_COLUMN_WIDTH_INCREASE = 16
    CODE_COLUMN_WIDTH_REDUCTION = 2 * TEXT_COLUMN_WIDTH_INCREASE
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
    DEFAULT_IMAGE_CELL_HEIGHT = ProductImageDelegate.DEFAULT_HEIGHT
    # IMAGE_SIZE sigue representando el preview usado por ProductDialog (144 px);
    # la columna principal usa DEFAULT_IMAGE_CELL_SIZE para alojar miniaturas.
    IMAGE_SIZE = 144
    DEFAULT_PRICE_COLUMN_WIDTH = 110
    FIXED_PRICE_COLUMN_WIDTH = 88
    DETAIL_FIELD_LABELS: ClassVar[dict[str, str]] = {
        "descripción comercial": "Descripción",
        "descripcion comercial": "Descripción",
        "descripción": "Descripción",
        "descripcion": "Descripción",
        "interfaz": "Interfaz",
        "técnica de impresión": "Técnica de impresión",
        "medidas de la caja máster": "Medidas de la caja máster",
        "medidas de la caja master": "Medidas de la caja máster",
        "peso bruto / caja": "Peso bruto / caja",
        "peso neto / caja": "Peso neto / caja",
        "tecnica de impresion": "Técnica de impresión",
        "superficie de impresión": "Superficie de impresión",
        "superficie de impresion": "Superficie de impresión",
        "dimensión": "Dimensión",
        "dimension": "Dimensión",
        "características": "Características",
        "caracteristicas": "Características",
        "propiedades": "Propiedades",
        "micras": "Micras",
        "medidas del estuche": "Medidas del Estuche",
        "medida y capacidad": "Medida y capacidad",
        "medida de impresión": "Medida de impresión",
        "medida de impresion": "Medida de impresión",
        "calidad": "Calidad",
        "paquete": "Paquete",
        "caja": "Caja",
        "medidas de estuche": "Medidas de Estuche",
        "presentación del estuche": "Presentación del Estuche",
        "uso ideal": "Uso ideal",
        "fecha": "Fecha",
        "forma": "Forma",
        "técnica de aplicación": "Técnica de aplicación",
        "tecnica de aplicacion": "Técnica de aplicación",
        "tipo de corte": "Tipo de corte",
        "capacidad de corte": "Capacidad de corte",
        "tamaño de corte máximo": "Tamaño de corte máximo",
        "tamano de corte maximo": "Tamaño de corte máximo",
        "dimensiones del producto": "Dimensiones del producto",
        "peso neto aproximado": "Peso neto aproximado",
        "tipo de encuadernado": "Tipo de encuadernado",
        "capacidad de encuadernado": "Capacidad de encuadernado",
        "tipo de encuadernación": "Tipo de encuadernación",
        "tipo de encuadernacion": "Tipo de encuadernación",
        "capacidad de encuadernación": "Capacidad de encuadernación",
        "capacidad de encuadernacion": "Capacidad de encuadernación",
        "presentacion del estuche": "Presentación del Estuche",
        "número de rodillos": "Número de rodillos",
        "numero de rodillos": "Número de rodillos",
        "velocidad de laminación": "Velocidad de laminación",
        "velocidad de laminacion": "Velocidad de laminación",
        "rollos por caja": "Rollos por caja",
        "impresiones por rollo": "Impresiones por rollo",
        "válido para impresoras": "Válido para impresoras",
        "valido para impresoras": "Válido para impresoras",
        "opciones de acabado": "Opciones de acabado",
        "soporta": "Soporta",
        "cortadora con 3 tipos de corte": "Cortadora con 3 tipos de corte",
        "levantamiento de materiales": "Levantamiento de materiales",
        "proyectos de manualidades": "Proyectos de manualidades",
        "aplicaciones de vinilo": "Aplicaciones de vinilo",
        "trabajo en scrapbooking": "Trabajo en scrapbooking",
        "calidad superior": "Calidad Superior",
        "compatibilidad confiable": "Compatibilidad Confiable",
        "procedencia coreana": "Procedencia Coreana",
        "facilidad de uso": "Facilidad de Uso",
        "espesor máximo del material": "Espesor máximo del material",
        "area máxima de corte": "Área máxima de corte",
        "área máxima de corte": "Área máxima de corte",
        "area de corte": "Área de corte",
        "área de corte": "Área de corte",
        "ancho de corte": "Ancho de Corte",
        "longitud de corte": "Longitud de Corte",
        "fuerza de corte": "Fuerza de Corte",
        "velocidad de corte": "Velocidad de Corte",
        "sistema de motor": "Sistema de Motor",
        "tipo de luz": "Tipo de luz",
        "espacio libre": "Espacio Libre",
        "contiene": "Contiene",
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
        "colores disponibles": "Colores disponibles",
        "voltaje y frecuencia": "Voltaje y Frecuencia",
        "tiempo de precalentamiento": "Tiempo de precalentamiento",
        "temperatura de trabajo": "Temperatura de trabajo",
        "sistema de calentamiento": "Sistema de calentamiento",
        "medidas mochila": "Medidas mochila",
        "medidas cartera": "Medidas cartera",
        "envase largo": "Envase Largo",
        "toalla largo": "Toalla Largo",
        "medidas cartuchera": "Medidas cartuchera",
        "tamaño cinta": "Tamaño de cinta",
        "tamano cinta": "Tamaño de cinta",
        "forro": "Forro",
        "medidas": "Medidas",
        "interior": "Interior",
        "espesor": "Espesor",
        "potencia": "Potencia",
        "dimensiones": "Dimensiones",
        "peso unitario": "Peso Unitario",
        "uso recomendado": "Uso Recomendado",
        "empaque individual": "Empaque Individual",
        "cantidad por caja": "Cantidad por Caja",
        "dimensiones caja": "Dimensiones Caja",
        "cubicaje por caja": "Cubicaje por Caja",
        "ancho de entrada": "Ancho de entrada",
        "espesor máximo de laminación": "Espesor máximo de laminación",
        "espesor maximo de laminacion": "Espesor máximo de laminación",
        "peso neto por caja": "Peso neto por caja",
        "peso bruto por caja": "Peso bruto por caja",
        "voltaje": "Voltaje",
        "materiales": "Materiales",
        "material": "Material",
        "modelo": "Modelo",
        "capacidad": "Capacidad",
        "tipo": "Tipo",
        "tamaño de impresión (cm)": "Tamaño de impresión (cm)",
        "tamano de impresion (cm)": "Tamaño de impresión (cm)",
        "tamaño impresión (cm)": "Tamaño impresión (cm)",
        "tamano impresion (cm)": "Tamaño impresión (cm)",
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
        "acceso": "Acceso",
        "conectividad": "Conectividad",
        "contenido": "Contenido",
        "incluye": "Incluye",
        "presentación del producto": "Presentación del producto",
        "empaque": "Empaque",
        "medida": "Medida",
        "alimentacion": "Alimentación",
        "alimentación": "Alimentación",
        "tiempo": "Tiempo",
        "diametro": "Diámetro",
        "diámetro": "Diámetro",
        "acabado": "Acabado",
        "funcion": "Función",
        "función": "Función",
        "funciones adicionales": "Funciones adicionales",
        "funciones": "Funciones",
        "rango de espesor polaseal": "Rango de espesor Polaseal",
        "rango de espesor": "Rango de espesor",
        "tiempo de calentamiento": "Tiempo de calentamiento",
        "consumo de energía": "Consumo de energía",
        "consumo de energia": "Consumo de energía",
        "uso": "Uso",
        "aplicacion": "Aplicación",
        "aplicación": "Aplicación",
        "area de trabajo": "Área de trabajo",
        "área de trabajo": "Área de trabajo",
        "color de tinta": "Color de tinta",
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
    # Prefer known aliases, but also recognize source-specific labels such as
    # "Modos:", "Acabado:", "Material de la hoja:" without SKU-specific rules.
    # Known aliases are case-insensitive; the generic fallback requires an
    # uppercase initial to avoid splitting ordinary lowercase prose at colons.
    _DETAIL_FIELD_LABEL_ALIASES_PATTERN: ClassVar[str] = "|".join(
        re.escape(label)
        for label in sorted(DETAIL_FIELD_LABELS, key=len, reverse=True)
    )
    DETAIL_FIELD_LABEL_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"(?<!\w)((?i:"
        + _DETAIL_FIELD_LABEL_ALIASES_PATTERN
        + r")|(?-i:(?![^:\n]{0,60}\b(?i:"
        + _DETAIL_FIELD_LABEL_ALIASES_PATTERN
        + r")\s*:)[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ ()/_-]{0,60}?))\s*:"
    )
    DETAIL_NESTED_MEASURE_LABELS: ClassVar[frozenset[str]] = frozenset({
        "envase largo",
        "toalla largo",
        "diámetro",
        "diametro",
        "largo",
        "ancho",
        "alto",
        "alt",
        "altura",
        "esp",
        "interior",
        "espesor",
        "estuche",
        "resaltador",
        "usb",
        "mochila",
        "cartera",
        "cartuchera",
    })
    DETAIL_PARENT_MEASURE_LABELS: ClassVar[frozenset[str]] = frozenset({
        "medidas del estuche",
        "medidas estuche",
        "medidas de estuche",
        "medida del estuche",
        "medidas mochila",
        "medidas cartera",
        "medidas cartuchera",
        "medidas usb",
    })
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
        IMAGE_COLUMN: ProductImageDelegate.DEFAULT_SIZE,
        CODE_COLUMN: 72,
        NAME_COLUMN: 112,
        DETAIL_COLUMN: 100,
        CATEGORY_COLUMN: 0,
        STOCK_COLUMN: 1,
        PRICE_SAMPLE_COLUMN: 72,
        PRICE_HUNDRED_COLUMN: 72,
        PRICE_THOUSAND_COLUMN: 72,
    }

    SORTABLE_COLUMNS: ClassVar[set[int]] = {
        STOCK_COLUMN,
        PRICE_SAMPLE_COLUMN,
        PRICE_HUNDRED_COLUMN,
        PRICE_THOUSAND_COLUMN,
    }

    HEADER_LABELS: ClassVar[list[str]] = [
        "Imagen",
        "Código",
        "Producto /\nCategoría",
        "Detalle",
        "",
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
        self._last_applied_sort_states = self._sort_states.copy()
        self._default_category_sort_active = True
        self._stable_code_width: int | None = None
        self._products: list[Product] = []
        self._search_text = ""
        self._render_generation = 0
        self._pending_render_products: list[Product] = []
        self._pending_render_index = 0
        self._rendered_products: list[Product] = []
        self._visible_product_keys: set[int] | None = None
        self._preferred_widths_cache: list[int] | None = None
        self._even_column_distribution = False
        self._gallery_overrides: dict[str, list[dict]] = {}
        self._row_by_code: dict[str, int] = {}
        self._rendering = False
        self._row_adjust_generation = 0
        table_font = QFont(self.FONT_FAMILY)
        table_font.setPixelSize(self.FONT_PIXEL_SIZE)
        self.setFont(table_font)
        self.setColumnCount(len(self.HEADER_LABELS))
        self.setHorizontalHeaderLabels(self.HEADER_LABELS)
        self._setup_table()
        self._setup_header()
        self.currentCellChanged.connect(self._handle_current_cell_changed)

    def _setup_table(self) -> None:
        self.setSortingEnabled(False)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.EditKeyPressed,
        )
        self.setWordWrap(True)
        self.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_image_context_menu)
        # La categoría se conserva como columna interna para edición y orden,
        # pero se muestra junto al código en la columna visible de la tabla.
        self.setColumnHidden(self.CATEGORY_COLUMN, True)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(self.DEFAULT_IMAGE_CELL_HEIGHT)
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
                padding: 3px 4px;
                font-family: "Segoe UI";
                font-size: 13px;
                color: #173f6d;
            }
            QTableWidget::item:focus {
                border: 0px;
                outline: none;
            }
            QTableWidget::item:selected {
                background-color: #fbfdff;
                border: 1px solid #1675e8;
                outline: none;
                color: #173f6d;
            }
            QTableWidget::item:selected:focus {
                border: 1px solid #1675e8;
                outline: none;
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
        self.setItemDelegate(ProductCellDelegate(self))
        header = ProductHeader(self)
        self.setHorizontalHeader(header)
        self.setItemDelegateForColumn(
            self.IMAGE_COLUMN,
            ProductImageDelegate(self),
        )
        self.setItemDelegateForColumn(
            self.NAME_COLUMN,
            ProductNameCategoryDelegate(self),
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
        # Keep the image column exactly as wide as the fixed primary preview;
        # thumbnails share that width without padding or inter-image gaps.
        header.setSectionResizeMode(
            self.IMAGE_COLUMN,
            QHeaderView.ResizeMode.Fixed,
        )
        for column, width in self.MIN_COLUMN_WIDTHS.items():
            self.setColumnWidth(column, width)
        self.setColumnHidden(self.CATEGORY_COLUMN, True)
        header.sectionResized.connect(self._handle_section_resized)

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

    def _handle_section_resized(
        self,
        logical_index: int,
        old_size: int,
        new_size: int,
    ) -> None:
        """Recalculate wrapped text heights when a visible text column changes."""
        del old_size, new_size
        if logical_index not in {self.NAME_COLUMN, self.DETAIL_COLUMN}:
            return
        if getattr(self, "_is_fitting_columns", False) or self._rendering:
            return

        self._row_adjust_generation += 1
        generation = self._row_adjust_generation
        QTimer.singleShot(
            0,
            lambda generation=generation: self._adjust_table_rows_batch(
                generation,
                0,
            ),
        )

    def _handle_header_click(self, column: int) -> None:
        if column not in self.SORTABLE_COLUMNS:
            return

        current = self._sort_states.get(column)
        if current == Qt.SortOrder.AscendingOrder:
            self._sort_states = {column: Qt.SortOrder.DescendingOrder}
            self._default_category_sort_active = False
        elif current == Qt.SortOrder.DescendingOrder:
            # The third click returns to the catalog's default category/name order.
            self._sort_states = {
                self.CATEGORY_COLUMN: Qt.SortOrder.AscendingOrder,
            }
            self._default_category_sort_active = True
        else:
            # The most recently clicked sortable column takes priority; searching,
            # stock availability and category filters remain managed independently.
            self._sort_states = {column: Qt.SortOrder.AscendingOrder}
            self._default_category_sort_active = False

        self._apply_current_sort()

    def _apply_current_sort(self) -> None:
        sorted_products = self._sorted_products()
        sort_state_changed = (
            self._last_applied_sort_states != self._sort_states
        )
        if not self._rendered_products and self.rowCount() == 0:
            self._update_sort_header_labels()
            self._render_products(sorted_products)
            self._last_applied_sort_states = self._sort_states.copy()
            return
        self._render_products(sorted_products)
        self._update_sort_header_labels()
        self._last_applied_sort_states = self._sort_states.copy()
        if sort_state_changed:
            self._preferred_widths_cache = None

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
            display_categories = sorted(
                self._natural_sort_key(display_category_name(category))
                for category in split_category_names(product.category)
            )
            category_key = (
                display_categories[0]
                if display_categories
                else self._natural_sort_key("")
            )
            return (
                category_key,
                self._natural_sort_key(product.name),
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
        """Mantiene la API de la ventana; ya no se reserva ancho para Categoría."""
        del products
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
        self._stable_code_width = None
        self._preferred_widths_cache = None
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
        active_index = 0
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
        image_item.setData(ProductImageDelegate.THUMBNAIL_START_ROLE, 0)
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
        item_code.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter,
        )
        self.setItem(row, self.CODE_COLUMN, item_code)
        self._set_text_item(row, self.NAME_COLUMN, product.name)
        detail = self._format_detail(product)
        self._set_text_item(row, self.DETAIL_COLUMN, detail)
        detail_item = self.item(row, self.DETAIL_COLUMN)
        if detail_item is not None:
            detail_item.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            )
        self._set_category_item(row, product.category)
        self._set_stock_widget(row, product)
        self._set_price_item(row, self.PRICE_SAMPLE_COLUMN, product.price_sample)
        self._set_price_item(row, self.PRICE_HUNDRED_COLUMN, product.price_hundred)
        self._set_price_item(row, self.PRICE_THOUSAND_COLUMN, product.price_thousand)

    @staticmethod
    def _product_gallery(product: Product) -> list[dict]:
        return normalize_product_gallery(product)

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
            gallery, changed_for_row = self._merge_gallery_options(
                gallery,
                options,
            )
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
            self._adjust_table_rows()
            self.viewport().update()

    @staticmethod
    def _merge_gallery_options(
        gallery: list[dict],
        options: list[dict],
    ) -> tuple[list[dict], bool]:
        seen_urls = {
            str(image.get("url", "") or "").strip().casefold()
            for image in gallery
            if isinstance(image, dict)
            and str(image.get("url", "") or "").strip()
        }
        seen_paths = {
            str(image.get("image_path", image.get("path", "")) or "")
            .strip()
            .replace("\\", "/")
            .casefold()
            for image in gallery
            if isinstance(image, dict)
            and str(
                image.get("image_path", image.get("path", "")) or ""
            ).strip()
        }
        seen_hashes = {
            str(image.get("image_hash", image.get("hash", "")) or "")
            .strip()
            .casefold()
            for image in gallery
            if isinstance(image, dict)
            and str(image.get("image_hash", image.get("hash", "")) or "").strip()
        }
        changed = False
        for option in options:
            url = str(option.get("url", "") or "").strip()
            path = str(option.get("path", option.get("image_path", "")) or "").strip()
            image_hash = str(
                option.get("hash", option.get("image_hash", "")) or ""
            ).strip()
            url_key = url.casefold()
            path_key = path.replace("\\", "/").casefold()
            hash_key = image_hash.casefold()
            if (
                (url_key and url_key in seen_urls)
                or (path_key and path_key in seen_paths)
                or (hash_key and hash_key in seen_hashes)
            ):
                continue
            normalized_option = dict(option)
            if path:
                normalized_option["image_path"] = path
            if image_hash:
                normalized_option["image_hash"] = image_hash
            gallery.append(normalized_option)
            if url_key:
                seen_urls.add(url_key)
            if path_key:
                seen_paths.add(path_key)
            if hash_key:
                seen_hashes.add(hash_key)
            changed = True
        return gallery, changed

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

    def keyPressEvent(self, event) -> None:
        """Use horizontal arrows to select the adjacent gallery thumbnail."""
        if (
            self.currentColumn() == self.IMAGE_COLUMN
            and event.key()
            in (Qt.Key.Key_Left, Qt.Key.Key_Right)
        ):
            row = self.currentRow()
            item = self.item(row, self.IMAGE_COLUMN)
            gallery = (
                item.data(ProductImageDelegate.GALLERY_ROLE)
                if item is not None
                else None
            )
            if (
                item is not None
                and isinstance(gallery, list)
                and len(gallery) > 1
            ):
                active_index = ProductImageDelegate._active_index(
                    gallery,
                    item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE),
                )
                direction = (
                    -1 if event.key() == Qt.Key.Key_Left else 1
                )
                next_index = max(
                    0,
                    min(active_index + direction, len(gallery) - 1),
                )
                if next_index != active_index:
                    if len(gallery) > ProductImageDelegate.MAX_VISIBLE_THUMBNAILS:
                        thumbnail_start = item.data(
                            ProductImageDelegate.THUMBNAIL_START_ROLE,
                        )
                        try:
                            thumbnail_start = max(int(thumbnail_start or 0), 0)
                        except (TypeError, ValueError):
                            thumbnail_start = 0
                        max_start = max(
                            len(gallery)
                            - ProductImageDelegate.MAX_VISIBLE_THUMBNAILS,
                            0,
                        )
                        thumbnail_start = min(thumbnail_start, max_start)
                        if next_index < thumbnail_start:
                            thumbnail_start = next_index
                        elif next_index >= (
                            thumbnail_start
                            + ProductImageDelegate.MAX_VISIBLE_THUMBNAILS
                        ):
                            thumbnail_start = (
                                next_index
                                - ProductImageDelegate.MAX_VISIBLE_THUMBNAILS
                                + 1
                            )
                        item.setData(
                            ProductImageDelegate.THUMBNAIL_START_ROLE,
                            thumbnail_start,
                        )
                    self._set_active_image(row, next_index)
                event.accept()
                return
        super().keyPressEvent(event)

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
                content_rect = ProductImageDelegate.cell_content_rect(rect)
                thumbnail_start = item.data(
                    ProductImageDelegate.THUMBNAIL_START_ROLE,
                )
                try:
                    thumbnail_start = max(int(thumbnail_start or 0), 0)
                except (TypeError, ValueError):
                    thumbnail_start = 0
                active_index = ProductImageDelegate._active_index(
                    gallery,
                    item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE),
                )
                image_path = ProductImageDelegate._selected_path(
                    gallery,
                    active_index,
                    item.data(ProductImageDelegate.IMAGE_ROLE),
                )
                strip_top = ProductImageDelegate.thumbnail_strip_top(
                    rect,
                    image_path,
                    has_thumbnails=True,
                )
                tiles, left_arrow, right_arrow, strip_top = (
                    ProductImageDelegate.thumbnail_layout(
                        content_rect,
                        len(gallery),
                        thumbnail_start,
                        active_index=active_index,
                        thumbnail_top=strip_top,
                    )
                )
                if position.y() >= strip_top:
                    for image_index, tile_rect in tiles:
                        if tile_rect.contains(position):
                            self.setCurrentCell(index.row(), self.IMAGE_COLUMN)
                            self._set_active_image(index.row(), image_index)
                            event.accept()
                            return
                    if left_arrow is not None and left_arrow.contains(position):
                        self.setCurrentCell(index.row(), self.IMAGE_COLUMN)
                        self._scroll_thumbnail_strip(index.row(), -1)
                        event.accept()
                        return
                    if right_arrow is not None and right_arrow.contains(position):
                        self.setCurrentCell(index.row(), self.IMAGE_COLUMN)
                        self._scroll_thumbnail_strip(index.row(), 1)
                        event.accept()
                        return
        super().mousePressEvent(event)

    def _scroll_thumbnail_strip(self, row: int, direction: int) -> None:
        item = self.item(row, self.IMAGE_COLUMN)
        if item is None:
            return
        gallery = item.data(ProductImageDelegate.GALLERY_ROLE)
        if not isinstance(gallery, list) or len(gallery) <= (
            ProductImageDelegate.MAX_VISIBLE_THUMBNAILS
        ):
            return
        current = item.data(ProductImageDelegate.THUMBNAIL_START_ROLE)
        try:
            current = max(int(current or 0), 0)
        except (TypeError, ValueError):
            current = 0
        max_start = max(
            len(gallery) - ProductImageDelegate.MAX_VISIBLE_THUMBNAILS,
            0,
        )
        item.setData(
            ProductImageDelegate.THUMBNAIL_START_ROLE,
            max(0, min(current + direction, max_start)),
        )
        self.viewport().update()

    def _set_active_image(self, row: int, active_index: int) -> None:
        item = self.item(row, self.IMAGE_COLUMN)
        if item is None:
            return
        gallery = item.data(ProductImageDelegate.GALLERY_ROLE)
        if not isinstance(gallery, list) or not gallery:
            return
        active_index %= len(gallery)
        # The main preview changes, while thumbnails remain in their persisted
        # positions and only the selected thumbnail border is updated.
        item.setData(ProductImageDelegate.ACTIVE_INDEX_ROLE, active_index)
        self._set_image_item_path(item, gallery, active_index)
        self._set_row_height(row)
        self.viewport().update()

    def _handle_current_cell_changed(
        self,
        current_row: int,
        current_column: int,
        previous_row: int,
        previous_column: int,
    ) -> None:
        """Restore original primaries when navigation moves to another row."""
        del current_column, previous_column
        if self._rendering or current_row == previous_row:
            return

        affected_rows = {
            row for row in (previous_row, current_row)
            if 0 <= row < self.rowCount()
        }
        for row in affected_rows:
            item = self.item(row, self.IMAGE_COLUMN)
            if item is None:
                continue
            gallery = item.data(ProductImageDelegate.GALLERY_ROLE)
            if not isinstance(gallery, list) or not gallery:
                continue
            item.setData(ProductImageDelegate.ACTIVE_INDEX_ROLE, 0)
            item.setData(ProductImageDelegate.THUMBNAIL_START_ROLE, 0)
            self._set_image_item_path(item, gallery, 0)
            self._set_row_height(row)

        self.viewport().update()

    @staticmethod
    def _cell_tooltip_html(text: str, width: int, alignment: int) -> str:
        """Constrain tooltip text to the cell width and its text alignment."""
        alignment_flags = Qt.AlignmentFlag(alignment)
        if alignment_flags & Qt.AlignmentFlag.AlignRight:
            text_alignment = "right"
        elif alignment_flags & Qt.AlignmentFlag.AlignHCenter:
            text_alignment = "center"
        else:
            text_alignment = "left"
        safe_width = max(width, 1)
        safe_text = html.escape(text).replace("\n", "<br>")
        return (
            f'<table width="{safe_width}" style="width:{safe_width}px; '
            f'margin:0; border:0;" cellspacing="0" cellpadding="0" border="0">'
            f'<tr><td align="{text_alignment}" '
            f'style="padding:0; white-space:normal; word-wrap:break-word;">'
            f'{safe_text}</td></tr></table>'
        )

    def viewportEvent(self, event) -> bool:
        if (
            event.type() == QEvent.Type.ToolTip
            and isinstance(event, QHelpEvent)
        ):
            index = self.indexAt(event.pos())
            item = self.itemFromIndex(index) if index.isValid() else None
            tooltip_text = item.toolTip() if item is not None else ""
            if item is not None and tooltip_text:
                cell_rect = self.visualRect(index)
                tooltip_html = self._cell_tooltip_html(
                    tooltip_text,
                    max(cell_rect.width() - 8, 1),
                    item.textAlignment(),
                )
                QToolTip.showText(
                    event.globalPos(),
                    tooltip_html,
                    self.viewport(),
                    cell_rect,
                )
            else:
                QToolTip.hideText()
            return True
        return super().viewportEvent(event)

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
        """Format source rows without losing labels or explicit field grouping."""
        raw_description = cls._correct_detail_spelling(
            str(product.description or "")
        )
        raw_description = raw_description.replace("\r\n", "\n").replace(
            "\r", "\n"
        )
        source_segments = re.split(r"[\n\u241e•▪●‣◦]+", raw_description)
        if not any(segment.strip() for segment in source_segments):
            return ""

        lines: list[str] = []
        for source_segment in source_segments:
            source_segment = re.sub(r"[ \t]+", " ", source_segment).strip()
            if not source_segment:
                continue

            if cls._has_explicit_source_grouping(source_segment):
                # Keep an unlisted leading field label. Rows containing a
                # removable color field still pass through the shared policy.
                source_labels = list(
                    cls.DETAIL_FIELD_LABEL_PATTERN.finditer(source_segment)
                )
                has_color_field = any(
                    match.group(1).strip().casefold()
                    in {"color", "colores", "colores disponibles"}
                    for match in source_labels
                )
                if has_color_field:
                    segment = normalize_detail_text(
                        source_segment,
                        preserve_boundaries=True,
                    )
                else:
                    segment = re.sub(
                        r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]",
                        "",
                        source_segment,
                    )
                    segment = re.sub(
                        r"(?:\s*,\s*|\s+)?\bprecio\s+incluye\s+igv\b\.?",
                        "",
                        segment,
                        flags=re.IGNORECASE,
                    )
                    segment = re.sub(r"\s+", " ", segment).strip()
            else:
                segment = normalize_detail_text(
                    source_segment,
                    preserve_boundaries=True,
                )
                segment = re.sub(r"[ \t]+", " ", segment).strip()

            for part in segment.splitlines():
                if part.strip():
                    lines.extend(cls._format_detail_segment(part, product))

        return cls._format_nested_estuche_resaltador_measurements(
            "\n".join(line for line in lines if line.strip()),
        )

    @classmethod
    def _has_explicit_source_grouping(cls, segment: str) -> bool:
        """Detect grouped fields from source separators, not product identity."""
        # The first label may be supplier-specific and absent from our label
        # vocabulary; detect the row shape independently of that vocabulary.
        starts_with_label = re.match(
            r"^\s*[A-ZÁÉÍÓÚÜÑ][^:\n]{0,60}:",
            segment,
        ) is not None
        # A slash is a grouping separator only when spaced on both sides;
        # otherwise unit notation such as "m³/CBM" can swallow later fields.
        grouped_after_slash = re.search(
            r"\s+/\s+[A-ZÁÉÍÓÚÜÑ][^:\n]{0,60}:",
            segment,
        ) is not None
        grouped_after_pipe = re.search(
            r"\|\s*[A-ZÁÉÍÓÚÜÑ][^:\n]{0,60}:",
            segment,
        ) is not None
        return starts_with_label and (grouped_after_slash or grouped_after_pipe)

    @classmethod
    def _format_detail_segment(
        cls,
        segment: str,
        product: Product,
    ) -> list[str]:
        """Format one source paragraph without merging neighboring fields."""
        segment = re.sub(r"[ \t]+", " ", segment).strip()
        if not segment:
            return []

        # A nested label in parentheses belongs to the value of the printing
        # technique field, not to a separate field in the table. Protect its
        # colon while detecting field boundaries, then restore it for display.
        protected_colon = "\ue001"
        if re.search(r"(?i)(?<!\w)t[eé]cnica\s+de\s+impresi[oó]n\s*:", segment):
            segment = re.sub(
                r"(?i)(área\s+de\s+impresi[oó]n\s+recomendada)\s*:",
                lambda match: f"{match.group(1)}{protected_colon}",
                segment,
            )

        matches = list(cls.DETAIL_FIELD_LABEL_PATTERN.finditer(segment))
        if not matches:
            cleaned = re.sub(r"[ \t.;]+$", "", segment)
            cleaned = cleaned.replace(protected_colon, ":")
            return [cleaned] if cleaned else []

        matches = cls._select_detail_field_matches(matches)
        if not matches:
            return []

        # Grouping is determined from the source separators, even when the
        # first label is supplier-specific and not in the known-label map.
        if cls._has_explicit_source_grouping(segment):
            cleaned = segment.replace(protected_colon, ":")
            cleaned = re.sub(r"[ \t.;]+$", "", cleaned)
            return [cleaned] if cleaned else []

        lines: list[str] = []
        raw_prefix = segment[: matches[0].start()]
        prefix = raw_prefix.strip(" \t\r\n.;|")
        combined_label_prefix = ""
        if len(matches) == 1 and raw_prefix.rstrip().endswith("|"):
            # Keep a descriptive prefix with the sole label that follows it
            # when the source uses a vertical bar as the grouping separator.
            combined_label_prefix = f"{prefix} | "
            prefix = ""
        if prefix:
            lines.append(re.sub(r"[ \t.;]+$", "", prefix))

        for index, match in enumerate(matches):
            next_start = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(segment)
            )
            alias = match.group(1).strip().casefold()
            label = cls.DETAIL_FIELD_LABELS.get(alias) or match.group(1).strip()
            if index == 0 and combined_label_prefix:
                label = f"{combined_label_prefix}{label}"
            value = segment[match.end() : next_start]
            value = value.replace(protected_colon, ":")
            value = re.sub(r"^[ \t\r\n.;]+", "", value)
            trailing_separators = (
                r"[ \t\r\n.;/]+$"
                if index + 1 < len(matches)
                else r"[ \t\r\n.;]+$"
            )
            value = re.sub(trailing_separators, "", value)
            value = re.sub(r"\s+", " ", value).strip()
            line = cls._format_detail_field_line(
                alias,
                label,
                value,
                product,
            )
            if line is not None:
                lines.append(line)

        return lines

    @classmethod
    def _select_detail_field_matches(
        cls,
        matches: list[re.Match[str]],
    ) -> list[re.Match[str]]:
        """Ignore removable color variants and nested measure sublabels."""
        selected: list[re.Match[str]] = []
        inside_measure_value = False
        for match in matches:
            alias = match.group(1).strip().casefold()
            if alias in {"área de impresión", "area de impresion"}:
                prefix = match.string[: match.start()]
                open_parenthesis = prefix.rfind("(")
                close_parenthesis = prefix.rfind(")")
                if open_parenthesis > close_parenthesis:
                    has_parent_technique = any(
                        previous.start() > close_parenthesis
                        and previous.start() < match.start()
                        and previous.group(1).strip().casefold()
                        in {"técnica de impresión", "tecnica de impresion"}
                        for previous in matches
                    )
                    if has_parent_technique:
                        continue
            if alias == "colores disponibles":
                continue
            if alias in {"medida", "medidas"} | cls.DETAIL_PARENT_MEASURE_LABELS:
                inside_measure_value = True
                selected.append(match)
                continue
            if (
                inside_measure_value
                and alias in cls.DETAIL_NESTED_MEASURE_LABELS
            ):
                continue
            inside_measure_value = False
            selected.append(match)
        return selected

    @staticmethod
    def _format_nested_estuche_resaltador_measurements(text: str) -> str:
        """Split numbered estuche/resaltador measurements independent of SKU."""
        formatted_lines: list[str] = []
        for line in text.splitlines():
            separator = re.search(
                r"\s+(?=2\s*\.\s*Resaltador\s*:)",
                line,
                re.IGNORECASE,
            )
            if separator is None:
                formatted_lines.append(line)
                continue

            estuche_source = line[: separator.start()].rstrip()
            resaltador_source = line[separator.start():].strip()
            if not re.search(
                r"\b1\s*\.\s*Estuche\s*:",
                estuche_source,
                re.IGNORECASE,
            ):
                formatted_lines.append(line)
                continue

            estuche = re.sub(
                r"\b1\s*\.\s*Estuche\s*:",
                "1. Estuche:",
                estuche_source,
                flags=re.IGNORECASE,
            )
            resaltador = re.sub(
                r"^2\s*\.\s*Resaltador\s*:",
                "2. Resaltador:",
                resaltador_source,
                flags=re.IGNORECASE,
            )
            if estuche:
                formatted_lines.append(estuche)
            if resaltador:
                formatted_lines.append(resaltador)
        return "\n".join(formatted_lines)

    @classmethod
    def _format_detail_field_line(
        cls,
        alias: str,
        label: str,
        value: str,
        product: Product,
    ) -> str | None:
        """Keep empty Caja visible while skipping other empty or duplicate fields."""
        if not value:
            return f"{label}:" if alias == "caja" else None
        if cls._detail_field_duplicates_row(label, value, product):
            return None
        return f"{label}: {value}".rstrip(" .")

    @classmethod
    def _detail_field_duplicates_row(
        cls,
        label: str,
        value: str,
        product: Product,
    ) -> bool:
        label_key = cls._detail_comparison_key(label)
        value_key = cls._detail_comparison_key(value)

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
            lines.extend(cls.CATEGORY_FORCED_LINES.get(category_name, (category_name,)))
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

    ROW_VERTICAL_SPACING = 0
    VERY_TALL_ROW_THRESHOLD = 320

    def _set_row_height(self, row: int) -> None:
        """Fit the row to its tallest cell content without extra vertical gaps."""

        content_height = 0
        image_item = self.item(row, self.IMAGE_COLUMN)
        if image_item is not None:
            gallery = image_item.data(ProductImageDelegate.GALLERY_ROLE)
            if not isinstance(gallery, list):
                gallery = []
            active_index = ProductImageDelegate._active_index(
                gallery,
                image_item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE),
            )
            image_path = ProductImageDelegate._selected_path(
                gallery,
                active_index,
                image_item.data(ProductImageDelegate.IMAGE_ROLE),
            )
            if image_path:
                image_content_height = ProductImageDelegate.main_image_height(
                    image_path,
                )
                if len(gallery) > 1:
                    image_content_height += (
                        ProductImageDelegate.THUMBNAIL_GAP
                        + ProductImageDelegate.THUMBNAIL_STRIP_HEIGHT
                    )
                image_content_height += (
                    (2 * ProductImageDelegate.CELL_VERTICAL_PADDING)
                    + ProductImageDelegate.GRIDLINE_BOTTOM_ALLOWANCE
                )
                content_height = max(content_height, image_content_height)

        name_item = self.item(row, self.NAME_COLUMN)
        category_item = self.item(row, self.CATEGORY_COLUMN)
        if name_item is not None:
            category_text = (
                category_item.text() if category_item is not None else "—"
            )
            name_height = ProductNameCategoryDelegate.content_height(
                name_item.text(),
                category_text,
                self.font(),
                max(self.columnWidth(self.NAME_COLUMN), 1),
            )
            content_height = max(content_height, name_height)

        detail_item = self.item(row, self.DETAIL_COLUMN)
        if detail_item is not None and detail_item.text():
            # QTableWidget's painted cell rect excludes the right gridline.
            # Match the delegate's actual wrapping width and reserve the bottom
            # gridline so a final wrapped line cannot be clipped.
            detail_width = max(
                self.columnWidth(self.DETAIL_COLUMN)
                - ProductDetailDelegate.GRIDLINE_ALLOWANCE
                - (2 * ProductDetailDelegate.HORIZONTAL_PADDING),
                1,
            )
            detail_height = (
                ProductDetailDelegate.content_height(
                    detail_item.text(),
                    self.font(),
                    detail_width,
                )
                + (2 * ProductDetailDelegate.VERTICAL_PADDING)
                + ProductDetailDelegate.GRIDLINE_ALLOWANCE
            )
            content_height = max(content_height, detail_height)

        stock_item = self.item(row, self.STOCK_COLUMN)
        if stock_item is not None:
            color_stock = stock_item.data(StockColorDelegate.STOCK_ROLE)
            if isinstance(color_stock, list) and color_stock:
                stock_height = (
                    len(color_stock) * StockColorDelegate.MIN_LINE_HEIGHT
                    + (2 * ProductImageDelegate.CELL_VERTICAL_PADDING)
                )
                content_height = max(content_height, stock_height)

        if content_height <= 0:
            content_height = (
                QFontMetrics(self.font()).height()
                + (2 * ProductImageDelegate.CELL_VERTICAL_PADDING)
            )

        self.setRowHeight(row, max(content_height, 1))

    def _adjust_table_rows(self) -> None:
        for row in range(self.rowCount()):
            self._set_row_height(row)

    ROW_HEIGHT_ADJUST_BATCH_SIZE = 64

    def set_even_column_distribution(self, enabled: bool) -> None:
        """Distribute width now and adjust row heights incrementally afterward."""

        enabled = bool(enabled)
        if self._even_column_distribution == enabled:
            return
        self._even_column_distribution = enabled
        self._fit_columns_to_content()
        self._row_adjust_generation += 1
        generation = self._row_adjust_generation
        QTimer.singleShot(
            0,
            lambda generation=generation: self._adjust_table_rows_batch(
                generation,
                0,
            ),
        )

    def _adjust_table_rows_batch(self, generation: int, start_row: int) -> None:
        if generation != self._row_adjust_generation:
            return
        end_row = min(
            start_row + self.ROW_HEIGHT_ADJUST_BATCH_SIZE,
            self.rowCount(),
        )
        for row in range(start_row, end_row):
            self._set_row_height(row)
        if end_row < self.rowCount():
            QTimer.singleShot(
                0,
                lambda generation=generation, next_row=end_row: (
                    self._adjust_table_rows_batch(generation, next_row)
                ),
            )

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

    def _preferred_column_widths(self, header: QHeaderView) -> list[int]:
        del header
        cached = self._preferred_widths_cache
        if cached is None:
            minimum_widths = [
                self.MIN_COLUMN_WIDTHS[column]
                for column in range(self.columnCount())
            ]
            minimum_widths[self.CATEGORY_COLUMN] = 0
            minimum_widths[self.STOCK_COLUMN] = self._stock_minimum_width()

            metrics = QFontMetrics(self.font())
            if self._stable_code_width is None:
                measured_code_width = max(
                    (
                        metrics.horizontalAdvance(str(product.code))
                        + (2 * self.CONTENT_SIDE_PADDING)
                    )
                    for product in self._products
                ) if self._products else minimum_widths[self.CODE_COLUMN]
                self._stable_code_width = min(
                    max(measured_code_width, minimum_widths[self.CODE_COLUMN]),
                    112,
                )

            preferred_widths = [
                max(width, 100)
                for width in minimum_widths
            ]
            preferred_widths[self.CATEGORY_COLUMN] = 0
            preferred_widths[self.IMAGE_COLUMN] = self.DEFAULT_IMAGE_CELL_SIZE
            preferred_widths[self.CODE_COLUMN] = max(
                minimum_widths[self.CODE_COLUMN],
                self._stable_code_width - self.CODE_COLUMN_WIDTH_REDUCTION,
            )
            preferred_widths[self.NAME_COLUMN] = (
                ProductNameCategoryDelegate.PREFERRED_WIDTH
            )
            preferred_widths[self.DETAIL_COLUMN] = (
                260 + self.TEXT_COLUMN_WIDTH_INCREASE
            )
            preferred_widths[self.STOCK_COLUMN] = minimum_widths[
                self.STOCK_COLUMN
            ]
            for price_column in (
                self.PRICE_SAMPLE_COLUMN,
                self.PRICE_HUNDRED_COLUMN,
                self.PRICE_THOUSAND_COLUMN,
            ):
                preferred_widths[price_column] = self.FIXED_PRICE_COLUMN_WIDTH
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
            minimum_widths[self.CATEGORY_COLUMN] = 0
            minimum_widths[self.STOCK_COLUMN] = self._stock_minimum_width()
            if self._even_column_distribution:
                minimum_widths[self.IMAGE_COLUMN] = preferred_widths[
                    self.IMAGE_COLUMN
                ]
            available_width = max(self.viewport().width(), 1)
            widths = self._allocate_column_widths(
                preferred_widths,
                minimum_widths,
                available_width,
                even_distribution=self._even_column_distribution,
                growable_columns=(
                    {
                        column
                        for column in range(self.columnCount())
                        if column != self.CATEGORY_COLUMN
                    }
                    if self._even_column_distribution
                    else {
                        self.DETAIL_COLUMN,
                        self.STOCK_COLUMN,
                        self.PRICE_SAMPLE_COLUMN,
                        self.PRICE_HUNDRED_COLUMN,
                        self.PRICE_THOUSAND_COLUMN,
                    }
                ),
            )

            for column, width in enumerate(widths):
                header.resizeSection(column, width)
        finally:
            self._is_fitting_columns = False

    @staticmethod
    def _reduce_column_widths(
        widths: list[int],
        floors: list[int],
        active_columns: list[int],
        deficit: int,
    ) -> int:
        """Reduce a set of widths without crossing the requested lower bounds."""
        while deficit > 0:
            flexible = [
                column
                for column in active_columns
                if widths[column] > floors[column]
            ]
            if not flexible:
                return deficit
            share = max((deficit + len(flexible) - 1) // len(flexible), 1)
            previous_deficit = deficit
            for column in flexible:
                reduction = min(
                    widths[column] - floors[column],
                    share,
                    deficit,
                )
                widths[column] -= reduction
                deficit -= reduction
                if deficit <= 0:
                    break
            if deficit == previous_deficit:
                return deficit
        return deficit

    @staticmethod
    def _allocate_column_widths(
        preferred_widths: list[int],
        minimum_widths: list[int],
        target_width: int,
        *,
        growable_columns: set[int],
        even_distribution: bool = False,
    ) -> list[int]:
        """Distribute surplus width proportionally across selected columns."""
        widths = [
            max(preferred, minimum)
            for preferred, minimum in zip(
                preferred_widths,
                minimum_widths,
                strict=True,
            )
        ]
        target_width = max(target_width, 1)
        active = [
            index
            for index, minimum in enumerate(minimum_widths)
            if minimum > 0
        ]
        current = sum(widths)

        if current > target_width:
            deficit = ProductTable._reduce_column_widths(
                widths,
                minimum_widths,
                active,
                current - target_width,
            )
            if deficit > 0:
                emergency_floors = [
                    1 if index in active else 0
                    for index in range(len(widths))
                ]
                ProductTable._reduce_column_widths(
                    widths,
                    emergency_floors,
                    active,
                    deficit,
                )

        current = sum(widths)
        if current < target_width and active:
            growth_columns = [
                index
                for index in active
                if index in growable_columns
                and not (
                    even_distribution
                    and index == ProductTable.IMAGE_COLUMN
                )
            ] or [
                index
                for index in active
                if not (even_distribution and index == ProductTable.IMAGE_COLUMN)
            ]
            extra = target_width - current
            # When the category sidebar is hidden, distribute the freed width
            # proportionally across visible columns while keeping Imagen fixed.
            weights = {
                index: max(
                    preferred_widths[index],
                    minimum_widths[index],
                    widths[index],
                    1,
                )
                for index in growth_columns
            }
            total_weight = sum(weights.values())
            remainders: list[tuple[int, int]] = []
            assigned = 0
            for index in growth_columns:
                increment, remainder = divmod(
                    extra * weights[index],
                    total_weight,
                )
                widths[index] += increment
                assigned += increment
                remainders.append((remainder, index))
            leftover = extra - assigned
            for _remainder, index in sorted(remainders, reverse=True)[:leftover]:
                widths[index] += 1
        return widths

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if getattr(self, "_is_fitting_columns", False):
            return
        self._fit_columns_to_content()
        self._adjust_table_rows()
