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
            "QLabel { background: #ffffff; border: 3px solid #cbd5e1; }"
        )
        self.setProperty("active", False)

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
        # Keep border thickness fixed so selection never resizes the thumbnail.
        self.setProperty("active", active)
        color = "#1675e8" if active else "#cbd5e1"
        self.setStyleSheet(
            f"QLabel {{ background: #ffffff; border: 3px solid {color}; }}"
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
    THUMBNAIL_WIDTH = max(
        (
            CONTENT_WIDTH
            - (THUMBNAIL_GAP * (MAX_VISIBLE_THUMBNAILS - 1))
        )
        // MAX_VISIBLE_THUMBNAILS,
        1,
    )

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
        self.setStyleSheet(
            "QDialog { background-color: #ffffff; }"
            " QWidget#gallery_main_image_area,"
            " QWidget#gallery_thumbnail_area,"
            " QLabel#gallery_main_image { background-color: #ffffff; }"
        )

        self.main_image = QLabel()
        self.main_image.setObjectName("gallery_main_image")
        self.main_image.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.main_image_area = QWidget(self)
        self.main_image_area.setObjectName("gallery_main_image_area")
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
        self.root_layout.setSpacing(self.THUMBNAIL_GAP)
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
        if not self.images:
            self.thumbnail_area.hide()
            self.thumbnail_area.setFixedWidth(self.CONTENT_WIDTH)
            self.main_image_area.setFixedWidth(self.CONTENT_WIDTH)
            return

        # Every image keeps its original slot, including the current primary.
        # The popup grows horizontally instead of shrinking or scrolling tiles.
        row_width = (
            len(self.images) * self.THUMBNAIL_WIDTH
            + max(len(self.images) - 1, 0) * self.THUMBNAIL_GAP
        )
        content_width = max(self.CONTENT_WIDTH, row_width)
        self.main_image_area.setFixedWidth(content_width)
        self.thumbnail_area.setFixedWidth(content_width)
        self.thumbnail_area.show()

        if row_width < content_width:
            self.thumbnail_layout.addStretch(1)

        # The selected main image always occupies the first thumbnail slot.
        # Swap only it with the former first image so all other slots stay put.
        thumbnail_indexes = list(range(len(self.images)))
        if self.active_index:
            thumbnail_indexes[0], thumbnail_indexes[self.active_index] = (
                thumbnail_indexes[self.active_index],
                thumbnail_indexes[0],
            )

        for index in thumbnail_indexes:
            path = str(self.images[index].get("image_path", "") or "")
            thumbnail = _GalleryThumbnailLabel(
                index,
                path,
                self.THUMBNAIL_WIDTH,
                self.THUMBNAIL_HEIGHT,
                self._select_image,
                self.thumbnail_area,
            )
            thumbnail.set_active(index == self.active_index)
            self.thumbnail_labels.append(thumbnail)
            self.thumbnail_layout.addWidget(thumbnail)

        if row_width < content_width:
            self.thumbnail_layout.addStretch(1)

        self.thumbnail_layout.activate()

    def _select_image(self, index: int) -> None:
        if index < 0 or index >= len(self.images) or index == self.active_index:
            return
        # Keep every thumbnail in its slot; only the main preview and selected
        # border change when a different image is chosen.
        self.active_index = index
        self._render()
