from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.runtime_paths import resolve_data_path
from gui.product_table import ProductImageDelegate
from models.product import Product


class _GalleryThumbnailLabel(QLabel):
    """Miniatura clicable que selecciona temporalmente la imagen principal."""

    def __init__(
        self,
        index: int,
        image_path: str,
        width: int,
        height: int,
        callback: Callable[[int], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.image_index = index
        self._callback = callback
        self.setObjectName("gallery_thumbnail")
        self.setProperty("image_path", image_path)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(width, height)
        self.setToolTip(Path(image_path).name if image_path else "Imagen")
        self.setStyleSheet(
            "QLabel { background: #ffffff; border: 1px solid #cbd5e1; }"
        )

        pixmap = (
            QPixmap(str(resolve_data_path(image_path)))
            if image_path
            else QPixmap()
        )
        if not pixmap.isNull():
            self.setPixmap(
                pixmap.scaled(
                    width - 8,
                    height - 8,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def set_active(self, active: bool) -> None:
        border = "3px solid #1675e8" if active else "1px solid #cbd5e1"
        self.setStyleSheet(
            f"QLabel {{ background: #ffffff; border: {border}; }}"
        )

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._callback(self.image_index)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ProductImageGalleryDialog(QDialog):
    """Visor al 260 % del tamaño original (30 % más que la escala previa)."""

    SCALE_FACTOR = 2.6
    MAIN_IMAGE_WIDTH = round(
        ProductImageDelegate.MAIN_IMAGE_WIDTH * SCALE_FACTOR
    )
    CONTENT_WIDTH = round(ProductImageDelegate.DEFAULT_SIZE * SCALE_FACTOR)
    THUMBNAIL_HEIGHT = round(
        ProductImageDelegate.THUMBNAIL_HEIGHT * SCALE_FACTOR
    )
    THUMBNAIL_GAP = round(ProductImageDelegate.THUMBNAIL_GAP * SCALE_FACTOR)
    MAX_VISIBLE_THUMBNAILS = ProductImageDelegate.MAX_VISIBLE_THUMBNAILS
    ARROW_WIDTH = round(12 * SCALE_FACTOR)

    def __init__(
        self,
        product: Product,
        parent=None,
        gallery_images: list[dict[str, Any]] | None = None,
        active_index: int = 0,
    ) -> None:
        super().__init__(parent)
        self.product = product
        self.images = self._normalized_gallery(product, gallery_images)
        self.active_index = (
            active_index % len(self.images) if self.images else 0
        )
        self.thumbnail_start = 0
        self.thumbnail_labels: list[_GalleryThumbnailLabel] = []

        self.setWindowTitle(f"Imágenes · {product.code}")
        self.setModal(True)

        self.main_image = QLabel()
        self.main_image.setObjectName("gallery_main_image")
        self.main_image.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.main_image_area = QWidget(self)
        main_layout = QHBoxLayout(self.main_image_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addStretch(1)
        main_layout.addWidget(self.main_image, 0, Qt.AlignmentFlag.AlignCenter)
        main_layout.addStretch(1)
        self.main_image_area.setFixedWidth(self.CONTENT_WIDTH)

        self.thumbnail_area = QWidget(self)
        self.thumbnail_area.setObjectName("gallery_thumbnail_area")
        self.thumbnail_layout = QHBoxLayout(self.thumbnail_area)
        self.thumbnail_layout.setContentsMargins(0, 0, 0, 0)
        self.thumbnail_layout.setSpacing(self.THUMBNAIL_GAP)
        self.thumbnail_area.setFixedWidth(self.CONTENT_WIDTH)

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(12, 12, 12, 12)
        self.root_layout.setSpacing(self.THUMBNAIL_GAP * 2)
        self.root_layout.addWidget(
            self.main_image_area,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )
        self.root_layout.addWidget(
            self.thumbnail_area,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )

        self._render()

    @staticmethod
    def _normalized_gallery(
        product: Product,
        gallery_images: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        source = (
            gallery_images
            if gallery_images is not None
            else list(product.gallery_images or [])
        )
        normalized: list[dict[str, Any]] = []
        for image in source:
            if not isinstance(image, dict):
                continue
            image_path = str(
                image.get("image_path") or image.get("path") or ""
            ).strip()
            if not image_path:
                continue
            normalized.append(
                {
                    **image,
                    "image_path": image_path,
                    "position": len(normalized) + 1,
                }
            )

        if not normalized and product.image_path:
            normalized.append(
                {
                    "url": product.image_url,
                    "image_path": product.image_path,
                    "image_hash": product.image_hash,
                    "position": 1,
                    "source": "primary",
                }
            )
        return normalized

    def _render(self) -> None:
        self._render_main_image()
        self._render_thumbnails()
        self.root_layout.activate()
        self.adjustSize()
        self.setMinimumSize(self.sizeHint())

    def _render_main_image(self) -> None:
        path = ""
        if self.images:
            path = str(
                self.images[self.active_index].get("image_path", "") or ""
            ).strip()

        pixmap = QPixmap(str(resolve_data_path(path))) if path else QPixmap()
        if pixmap.isNull():
            self.main_image.setPixmap(QPixmap())
            self.main_image.setText("Sin vista previa" if path else "Sin imágenes")
            self.main_image.setFixedSize(self.MAIN_IMAGE_WIDTH, 144)
            self.main_image_area.setFixedHeight(144)
            return

        preview = pixmap.scaledToWidth(
            self.MAIN_IMAGE_WIDTH,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.main_image.setText("")
        self.main_image.setPixmap(preview)
        self.main_image.setFixedSize(preview.size())
        self.main_image_area.setFixedHeight(preview.height())

    def _render_thumbnails(self) -> None:
        while self.thumbnail_layout.count():
            item = self.thumbnail_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        self.thumbnail_labels = []
        thumbnail_indexes = [
            index
            for index in range(len(self.images))
            if index != self.active_index
        ]
        if not thumbnail_indexes:
            self.thumbnail_area.hide()
            return

        self.thumbnail_area.show()
        has_arrows = len(thumbnail_indexes) > self.MAX_VISIBLE_THUMBNAILS
        visible_count = min(
            len(thumbnail_indexes),
            self.MAX_VISIBLE_THUMBNAILS,
        )
        if has_arrows:
            available_width = (
                self.CONTENT_WIDTH
                - (2 * self.ARROW_WIDTH)
                - (self.THUMBNAIL_GAP * (visible_count + 1))
            )
        else:
            available_width = self.CONTENT_WIDTH - (
                self.THUMBNAIL_GAP * (self.MAX_VISIBLE_THUMBNAILS - 1)
            )
        tile_width = max(available_width // self.MAX_VISIBLE_THUMBNAILS, 1)

        if has_arrows:
            self.thumbnail_layout.addWidget(self._arrow_button("<", -1))
        else:
            self.thumbnail_layout.addStretch(1)

        max_start = max(len(thumbnail_indexes) - visible_count, 0)
        self.thumbnail_start = max(0, min(self.thumbnail_start, max_start))
        visible_indices = thumbnail_indexes[
            self.thumbnail_start : self.thumbnail_start + visible_count
        ]
        for index in visible_indices:
            path = str(self.images[index].get("image_path", "") or "")
            thumbnail = _GalleryThumbnailLabel(
                index,
                path,
                tile_width,
                self.THUMBNAIL_HEIGHT,
                self._select_image,
                self.thumbnail_area,
            )
            thumbnail.set_active(False)
            self.thumbnail_labels.append(thumbnail)
            self.thumbnail_layout.addWidget(thumbnail)

        if has_arrows:
            self.thumbnail_layout.addWidget(self._arrow_button(">", 1))
        else:
            self.thumbnail_layout.addStretch(1)

        self.thumbnail_layout.activate()

    def _arrow_button(self, label: str, direction: int) -> QPushButton:
        button = QPushButton(label, self.thumbnail_area)
        button.setObjectName(
            "gallery_previous" if direction < 0 else "gallery_next"
        )
        button.setFixedSize(self.ARROW_WIDTH, self.THUMBNAIL_HEIGHT)
        button.setToolTip(
            "Ver miniaturas anteriores"
            if direction < 0
            else "Ver miniaturas siguientes"
        )
        button.clicked.connect(
            lambda _checked=False, step=direction: self._scroll_thumbnails(step)
        )
        return button

    def _scroll_thumbnails(self, direction: int) -> None:
        thumbnail_count = len(self.images) - 1
        if thumbnail_count <= self.MAX_VISIBLE_THUMBNAILS:
            return
        max_start = thumbnail_count - self.MAX_VISIBLE_THUMBNAILS
        self.thumbnail_start = max(
            0,
            min(self.thumbnail_start + direction, max_start),
        )
        self._render_thumbnails()

    def _select_image(self, index: int) -> None:
        if index < 0 or index >= len(self.images) or index == self.active_index:
            return
        # Keep the persisted/gallery order stable. The formerly active image
        # becomes the first alternative when it is no longer the main preview.
        self.active_index = index
        self.thumbnail_start = 0
        self._render()
