from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from config.runtime_paths import resolve_data_path
from models.product import Product
from services.product_service import ProductService


class ProductImageGalleryDialog(QDialog):
    """Galería editable por clic, con guardado explícito de los cambios."""

    IMAGE_SIZE = 144
    IMAGE_EXTENSIONS = "Imágenes (*.png *.jpg *.jpeg *.webp *.gif)"

    def __init__(
        self,
        product: Product,
        parent=None,
        service: ProductService | None = None,
    ) -> None:
        super().__init__(parent)
        self.product = product
        self.service = service or ProductService()
        self.images = self._normalized_gallery(product)
        self.selected_index = 0 if self.images else -1

        self.setWindowTitle(f"Imágenes · {product.code}")
        self.resize(900, 270)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.save_button = QPushButton("Guardar")
        self.save_button.clicked.connect(self.save)

        header = QHBoxLayout()
        header.addWidget(self.summary, 1)
        header.addWidget(self.save_button)

        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(False)
        self.gallery_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self.gallery_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.canvas = QWidget()
        self.canvas_layout = QHBoxLayout(self.canvas)
        self.canvas_layout.setContentsMargins(6, 6, 6, 6)
        self.canvas_layout.setSpacing(8)
        self.gallery_scroll.setWidget(self.canvas)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.gallery_scroll, 1)
        self._render()

    @staticmethod
    def _normalized_gallery(product: Product) -> list[dict[str, object]]:
        images = [
            dict(image)
            for image in list(product.gallery_images or [])
            if isinstance(image, dict)
        ]
        if not images and product.image_path:
            images = [
                {
                    "url": product.image_url,
                    "image_path": product.image_path,
                    "image_hash": product.image_hash,
                    "position": 1,
                    "source": "primary",
                }
            ]
        return [
            {
                **image,
                "image_path": str(
                    image.get("image_path", image.get("path", "")) or ""
                ).strip(),
                "position": index + 1,
            }
            for index, image in enumerate(images)
            if str(
                image.get("image_path", image.get("path", "")) or ""
            ).strip()
        ]

    def _render(self) -> None:
        while self.canvas_layout.count():
            item = self.canvas_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for index, image in enumerate(self.images):
            self.canvas_layout.addWidget(self._image_card(index, image))

        if not self.images:
            self.canvas_layout.addWidget(self._empty_image_card())
        self.canvas_layout.addStretch(1)
        self.canvas.adjustSize()

        count = len(self.images)
        primary = (
            Path(str(self.images[0].get("image_path", ""))).name
            if self.images
            else "sin imagen"
        )
        self.summary.setText(
            f"{count} imagen(es) · Imagen actual: {primary}. "
            "Clic en la imagen actual para reemplazarla; clic en una "
            "alternativa para intercambiarla con la actual."
        )
        self.gallery_scroll.setMinimumHeight(self.IMAGE_SIZE + 48)

    def _image_card(self, index: int, image: dict[str, object]) -> QWidget:
        path = str(image.get("image_path", "") or "").strip()
        current = index == 0
        card = QWidget()
        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(3)

        image_button = QPushButton()
        image_button.setFixedSize(self.IMAGE_SIZE, self.IMAGE_SIZE)
        image_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        image_button.setToolTip(
            "Clic para reemplazar la imagen actual"
            if current
            else "Clic para intercambiar con la imagen actual"
        )
        image_button.setStyleSheet(
            "QPushButton {"
            " background: #ffffff;"
            + (
                " border: 3px solid #173f6d;"
                if current
                else " border: 2px solid #cbddea;"
            )
            + " border-radius: 4px; padding: 2px;"
            "}"
            " QPushButton:hover { border-color: #4a90c2; }"
        )

        pixmap = QPixmap(str(resolve_data_path(path)))
        if not pixmap.isNull():
            image_button.setIcon(pixmap)
            image_button.setIconSize(
                QSize(self.IMAGE_SIZE - 10, self.IMAGE_SIZE - 10),
            )
        else:
            image_button.setText(
                "Imagen actual\nSin vista previa"
                if current
                else "Alternativa\nSin vista previa"
            )

        if current:
            image_button.clicked.connect(self.replace_primary_image)
            label_text = "Imagen actual"
        else:
            image_button.clicked.connect(
                lambda _checked=False, value=index: (
                    self.exchange_with_primary(value)
                ),
            )
            label_text = f"Alternativa {index}"

        name = Path(path).name
        label = QLabel(f"{label_text}\n{name}")
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        label.setWordWrap(True)
        label.setFixedWidth(self.IMAGE_SIZE)
        card_layout.addWidget(image_button)
        card_layout.addWidget(label)
        return card

    def _empty_image_card(self) -> QWidget:
        card = QWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        image_button = QPushButton("Agregar imagen")
        image_button.setFixedSize(self.IMAGE_SIZE, self.IMAGE_SIZE)
        image_button.setStyleSheet(
            "QPushButton { background: #ffffff; border: 2px dashed #9bb6ca; }"
        )
        image_button.clicked.connect(self.replace_primary_image)
        label = QLabel("Imagen actual")
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(image_button)
        card_layout.addWidget(label)
        return card

    def replace_primary_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Reemplazar imagen actual",
            "",
            self.IMAGE_EXTENSIONS,
        )
        if filename:
            self._replace_primary_path(filename)

    def _replace_primary_path(self, filename: str) -> None:
        path = str(Path(filename))
        replacement = {
            "url": "",
            "image_path": path,
            "image_hash": "",
            "position": 1,
            "source": "manual",
        }
        if self.images:
            previous = dict(self.images[0])
            previous_path = str(previous.get("image_path", "") or "").casefold()
            replacement_key = path.casefold()
            alternatives = [
                dict(image)
                for image in self.images[1:]
                if str(image.get("image_path", "") or "").casefold()
                != replacement_key
            ]
            if previous_path and previous_path != replacement_key:
                alternatives = [
                    image
                    for image in alternatives
                    if str(image.get("image_path", "") or "").casefold()
                    != previous_path
                ]
                alternatives.insert(0, previous)
            self.images = [replacement, *alternatives]
        else:
            self.images = [replacement]
        self.selected_index = 0
        self._render()

    def exchange_with_primary(self, index: int) -> None:
        if index <= 0 or index >= len(self.images):
            return
        self.images[0], self.images[index] = self.images[index], self.images[0]
        for position, image in enumerate(self.images, start=1):
            image["position"] = position
        self.selected_index = 0
        self._render()

    def save(self) -> None:
        gallery = [
            {**image, "position": index + 1}
            for index, image in enumerate(self.images)
        ]
        primary = gallery[0] if gallery else {}
        updated = Product(
            code=self.product.code,
            name=self.product.name,
            price=self.product.price,
            category=self.product.category,
            description=self.product.description,
            price_sample=self.product.price_sample,
            price_hundred=self.product.price_hundred,
            price_thousand=self.product.price_thousand,
            stock=self.product.stock,
            color_stock=dict(self.product.color_stock),
            image_url=str(primary.get("url", "") or "") if gallery else "",
            image_path=str(primary.get("image_path", "") or ""),
            image_hash=str(primary.get("image_hash", "") or ""),
            gallery_images=gallery,
            content_hash=self.product.content_hash,
            product_id=self.product.id,
        )
        try:
            self.service.update_product(updated)
        except (sqlite3.Error, ValueError) as error:
            QMessageBox.critical(self, "Imágenes", str(error))
            return
        self.product.gallery_images = gallery
        self.product.image_url = updated.image_url
        self.product.image_path = updated.image_path
        self.product.image_hash = updated.image_hash
        self.accept()
