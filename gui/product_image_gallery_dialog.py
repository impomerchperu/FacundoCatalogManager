from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
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
    """Editor visual de galería con la misma selección/reemplazo por tarjetas."""

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

        self.setWindowTitle(f"Imágenes · {product.code}")
        self.resize(720, 360)

        self.summary = QLabel(
            "Seleccione una imagen para usarla como principal. "
            "Puede reemplazarla, quitarla o agregar alternativas."
        )
        self.summary.setWordWrap(True)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.canvas = QWidget()
        self.canvas_layout = QHBoxLayout(self.canvas)
        self.canvas_layout.setContentsMargins(6, 6, 6, 6)
        self.canvas_layout.setSpacing(8)
        self.scroll.setWidget(self.canvas)

        add_button = QPushButton("Subir imágenes...")
        add_button.clicked.connect(self.add_images)
        primary_button = QPushButton("Hacer principal")
        primary_button.clicked.connect(self.make_primary)
        replace_button = QPushButton("Reemplazar seleccionada")
        replace_button.clicked.connect(self.replace_selected)
        remove_button = QPushButton("Quitar")
        remove_button.clicked.connect(self.remove_selected)

        actions = QHBoxLayout()
        actions.addWidget(add_button)
        actions.addWidget(primary_button)
        actions.addWidget(replace_button)
        actions.addWidget(remove_button)
        actions.addStretch()

        save_button = QPushButton("Guardar")
        save_button.clicked.connect(self.save)
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)
        actions.addWidget(cancel_button)
        actions.addWidget(save_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(self.scroll, 1)
        layout.addLayout(actions)

        self.selected_index = 0 if self.images else -1
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

        self.canvas_layout.addStretch(1)
        self.canvas.adjustSize()

        count = len(self.images)
        primary = " · Principal: " + (
            Path(str(self.images[0].get("image_path", ""))).name
            if self.images
            else "sin imagen"
        )
        self.summary.setText(
            f"{count} imagen(es){primary}. "
            "Haga clic sobre una tarjeta para seleccionarla."
        )

    def _image_card(self, index: int, image: dict[str, object]) -> QWidget:
        path = str(image.get("image_path", "") or "").strip()
        selected = index == self.selected_index

        card = QPushButton()
        card.setFixedSize(self.IMAGE_SIZE, self.IMAGE_SIZE)
        card.setCheckable(True)
        card.setChecked(selected)
        card.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        card.setToolTip(path)
        card.setStyleSheet(
            "QPushButton {"
            " background: #ffffff;"
            " border: 2px solid #cbddea;"
            " border-radius: 4px;"
            " padding: 2px;"
            "}"
            " QPushButton:checked {"
            " border: 3px solid #173f6d;"
            "}"
        )

        pixmap = QPixmap(str(resolve_data_path(path)))
        if not pixmap.isNull():
            card.setIcon(pixmap)
            card.setIconSize(
                QSize(self.IMAGE_SIZE - 8, self.IMAGE_SIZE - 8),
            )
        else:
            card.setText("Sin vista previa")

        if index == 0:
            card.setText(
                ("★ Principal\n" if pixmap.isNull() else "")
                + Path(path).name
            )
        else:
            card.setText(Path(path).name)

        card.clicked.connect(
            lambda _checked=False, value=index: self._select(value),
        )
        return card

    def _select(self, index: int) -> None:
        if 0 <= index < len(self.images):
            self.selected_index = index
            self._render()

    def add_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Subir imágenes",
            "",
            self.IMAGE_EXTENSIONS,
        )
        if not files:
            return
        existing = {
            str(image.get("image_path", "") or "").casefold()
            for image in self.images
        }
        for filename in files:
            path = str(Path(filename))
            if path.casefold() in existing:
                continue
            self.images.append(
                {
                    "url": "",
                    "image_path": path,
                    "image_hash": "",
                    "position": len(self.images) + 1,
                    "source": "manual",
                }
            )
            existing.add(path.casefold())
        if self.selected_index < 0 and self.images:
            self.selected_index = 0
        self._render()

    def replace_selected(self) -> None:
        if not (0 <= self.selected_index < len(self.images)):
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Reemplazar imagen",
            "",
            self.IMAGE_EXTENSIONS,
        )
        if not filename:
            return
        current = self.images[self.selected_index]
        self.images[self.selected_index] = {
            **current,
            "url": "",
            "image_path": str(Path(filename)),
            "image_hash": "",
            "source": "manual",
        }
        self._render()

    def make_primary(self) -> None:
        if not (0 <= self.selected_index < len(self.images)):
            return
        if self.selected_index == 0:
            return
        image = self.images.pop(self.selected_index)
        self.images.insert(0, image)
        self.selected_index = 0
        self._render()

    def remove_selected(self) -> None:
        if not (0 <= self.selected_index < len(self.images)):
            return
        self.images.pop(self.selected_index)
        if self.images:
            self.selected_index = min(self.selected_index, len(self.images) - 1)
        else:
            self.selected_index = -1
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
            image_url=str(primary.get("url", "") or "") or self.product.image_url,
            image_path=str(primary.get("image_path", "") or ""),
            image_hash=str(primary.get("image_hash", "") or ""),
            gallery_images=gallery,
            content_hash=self.product.content_hash,
            product_id=self.product.id,
        )
        self.service.update_product(updated)
        self.product.gallery_images = gallery
        self.product.image_url = updated.image_url
        self.product.image_path = updated.image_path
        self.product.image_hash = updated.image_hash
        self.accept()
