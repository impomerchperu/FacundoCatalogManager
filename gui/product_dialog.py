from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from config.runtime_paths import resolve_data_path

from gui.category_selector import CategorySelector
from models.product import Product
from services.product_service import ProductService
from services.scraping.category_name_normalizer import (
    available_category_names,
    split_category_names,
)


class ProductDialog(QDialog):
    """Editor y alta manual de productos con galería de imágenes."""

    IMAGE_EXTENSIONS = "Imágenes (*.png *.jpg *.jpeg *.webp *.gif)"

    def __init__(
        self,
        parent=None,
        product: Product | None = None,
    ):
        super().__init__(parent)
        self.product = product
        self.service = ProductService()
        self.gallery_images: list[dict[str, object]] = []

        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint,
        )
        self.setWindowTitle(
            "Editar Producto" if self.product else "Nuevo Producto",
        )
        self.resize(620, 760)

        self.code = QLineEdit()
        self.code.setPlaceholderText("Se genera automáticamente si queda vacío")
        self.name = QLineEdit()

        self.category = CategorySelector(editable_text=True)
        self.category.set_categories(
            available_category_names(
                self.product.category if self.product else "",
            ),
        )

        self.description = QTextEdit()
        self.description.setFixedHeight(80)

        self.price = self._create_price_spinbox()
        self.price_sample = self._create_price_spinbox()
        self.price_hundred = self._create_price_spinbox()
        self.price_thousand = self._create_price_spinbox()

        self.stock = QSpinBox()
        self.stock.setMaximum(9999999)
        self.stock.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.color_stock = QTextEdit()
        self.color_stock.setFixedHeight(70)
        self.color_stock.setPlaceholderText("Rojo: 10\nAzul: 25")
        self.color_stock.textChanged.connect(self._sync_stock_from_colors)

        self.image_path = QLineEdit()
        self.image_path.setReadOnly(True)

        self.image_preview = QLabel()
        self.image_preview.setFixedSize(180, 180)
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setStyleSheet(
            "border: 1px solid gray; background: white;"
        )

        self.gallery_list = QListWidget()
        self.gallery_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        self.gallery_list.setIconSize(self.gallery_list_icon_size())
        self.gallery_list.setFixedHeight(105)
        self.gallery_list.currentRowChanged.connect(
            self._gallery_row_changed,
        )

        self.load_product_data()

        form = QFormLayout()
        form.addRow("Código:", self.code)
        form.addRow("Nombre:", self.name)

        category_layout = QHBoxLayout()
        category_layout.addWidget(self.category, 1)
        self.new_category_button = QPushButton("+ Nueva categoría")
        self.new_category_button.clicked.connect(self.add_typed_category)
        category_layout.addWidget(self.new_category_button)
        form.addRow("Categoría:", category_layout)

        form.addRow("Descripción:", self.description)
        form.addRow("Precio:", self.price)
        form.addRow("Precio muestra:", self.price_sample)
        form.addRow("Precio ciento:", self.price_hundred)
        form.addRow("Precio millar:", self.price_thousand)
        form.addRow("Stock:", self.stock)
        form.addRow("Stock por color:", self.color_stock)
        form.addRow("Imagen principal:", self.image_path)

        image_buttons = QHBoxLayout()
        btn_add_images = QPushButton("Agregar imágenes...")
        btn_add_images.clicked.connect(self.select_images)
        image_buttons.addWidget(btn_add_images)

        btn_primary = QPushButton("Hacer principal")
        btn_primary.clicked.connect(self.set_primary_image)
        image_buttons.addWidget(btn_primary)

        btn_remove = QPushButton("Quitar")
        btn_remove.clicked.connect(self.remove_selected_image)
        image_buttons.addWidget(btn_remove)

        form.addRow("Galería:", self.gallery_list)
        form.addRow("", image_buttons)
        form.addRow("Vista previa:", self.image_preview)

        btn_save = QPushButton("Guardar")
        btn_save.clicked.connect(self.save_product)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(btn_save)
        buttons.addWidget(btn_cancel)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)

    @staticmethod
    def gallery_list_icon_size():
        from PySide6.QtCore import QSize

        return QSize(64, 64)

    @staticmethod
    def _create_price_spinbox() -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setMaximum(9999999)
        widget.setDecimals(2)
        widget.setPrefix("S/ ")
        widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        return widget

    def load_product_data(self) -> None:
        if self.product is None:
            self.code.setText(self.service.next_product_code())
            self.stock.setReadOnly(False)
            return

        self.code.setText(self.product.code)
        self.code.setReadOnly(True)
        self.name.setText(self.product.name)
        self.category.set_selected_categories(
            split_category_names(self.product.category),
        )
        self.description.setPlainText(self.product.description)
        self.price.setValue(self.product.price)
        self.price_sample.setValue(self.product.price_sample)
        self.price_hundred.setValue(self.product.price_hundred)
        self.price_thousand.setValue(self.product.price_thousand)
        self.stock.setValue(self.product.stock)
        self.color_stock.setPlainText(
            "\n".join(
                f"{color}: {stock}"
                for color, stock in self.product.color_stock.items()
            ),
        )

        source_gallery = [
            dict(image)
            for image in list(self.product.gallery_images or [])
            if isinstance(image, dict)
        ]
        if not source_gallery and self.product.image_path:
            source_gallery = [
                {
                    "url": self.product.image_url,
                    "image_path": self.product.image_path,
                    "image_hash": self.product.image_hash,
                    "position": 1,
                    "source": "primary",
                }
            ]
        self.gallery_images = self._normalize_gallery(source_gallery)
        self._refresh_gallery_list()
        self._sync_stock_from_colors()

    @staticmethod
    def _normalize_gallery(
        images: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        seen: set[str] = set()
        for image in images:
            path = str(
                image.get("image_path", image.get("path", "")) or ""
            ).strip()
            url = str(image.get("url", "") or "").strip()
            identity = path.casefold()
            if not path or not identity or identity in seen:
                continue
            seen.add(identity)
            result.append(
                {
                    "url": url,
                    "image_path": path,
                    "image_hash": str(
                        image.get("image_hash", image.get("hash", "")) or ""
                    ),
                    "position": len(result) + 1,
                    "source": str(
                        image.get("source", "gallery") or "gallery"
                    ),
                }
            )
        return result

    def _refresh_gallery_list(self) -> None:
        current_path = (
            str(
                self.gallery_images[0].get("image_path", "")
                if self.gallery_images
                else ""
            )
            .strip()
            .casefold()
        )
        selected_path = (
            str(
                self.gallery_images[
                    min(max(self.gallery_list.currentRow(), 0), len(self.gallery_images) - 1)
                ].get("image_path", "")
                if self.gallery_images
                else ""
            )
            .strip()
            .casefold()
        )

        self.gallery_list.blockSignals(True)
        self.gallery_list.clear()
        for index, image in enumerate(self.gallery_images):
            path = str(image.get("image_path", "") or "").strip()
            label = Path(path).name or path
            prefix = "★ Principal · " if index == 0 else f"Alternativa {index} · "
            item = QListWidgetItem(prefix + label)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            resolved = resolve_data_path(path)
            if resolved.is_file():
                pixmap = QPixmap(str(resolved))
                if not pixmap.isNull():
                    item.setIcon(QIcon(pixmap))
            self.gallery_list.addItem(item)
        self.gallery_list.blockSignals(False)

        target = -1
        for index, image in enumerate(self.gallery_images):
            path = str(image.get("image_path", "") or "").strip().casefold()
            if path == selected_path:
                target = index
                break
            if path == current_path and target < 0:
                target = index
        if target < 0 and self.gallery_images:
            target = 0
        if target >= 0:
            self.gallery_list.setCurrentRow(target)
        self._update_primary_fields()

    def add_typed_category(self) -> None:
        line_edit = self.category.lineEdit()
        value = line_edit.text().strip() if line_edit is not None else ""
        if not value:
            return
        self.category.add_category(value, select=True)

    def _sync_stock_from_colors(self) -> None:
        values = self._color_stock_values()
        has_colors = bool(values)
        if has_colors:
            self.stock.setValue(sum(values.values()))
        self.stock.setReadOnly(has_colors)

    def select_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Agregar imágenes",
            "",
            self.IMAGE_EXTENSIONS,
        )
        if not files:
            return

        existing = {
            str(image.get("image_path", "") or "").strip().casefold()
            for image in self.gallery_images
        }
        for filename in files:
            path = str(Path(filename)).strip()
            key = path.casefold()
            if not path or key in existing:
                continue
            self.gallery_images.append(
                {
                    "url": "",
                    "image_path": path,
                    "image_hash": "",
                    "position": len(self.gallery_images) + 1,
                    "source": "manual",
                }
            )
            existing.add(key)

        if self.gallery_images and self.gallery_list.currentRow() < 0:
            self.gallery_list.setCurrentRow(0)
        self._refresh_gallery_list()

    def select_image(self) -> None:
        """Compatibilidad con la acción anterior de selección individual."""
        self.select_images()

    def set_primary_image(self) -> None:
        row = self.gallery_list.currentRow()
        if row <= 0 or row >= len(self.gallery_images):
            if row < 0:
                QMessageBox.information(
                    self,
                    "Imagen principal",
                    "Seleccione una imagen de la galería.",
                )
            return
        image = self.gallery_images.pop(row)
        self.gallery_images.insert(0, image)
        self._refresh_gallery_list()
        self.gallery_list.setCurrentRow(0)

    def remove_selected_image(self) -> None:
        row = self.gallery_list.currentRow()
        if row < 0 or row >= len(self.gallery_images):
            QMessageBox.information(
                self,
                "Galería",
                "Seleccione una imagen para quitarla.",
            )
            return
        self.gallery_images.pop(row)
        self._refresh_gallery_list()

    def _gallery_row_changed(self, row: int) -> None:
        if 0 <= row < len(self.gallery_images):
            path = str(
                self.gallery_images[row].get("image_path", "") or ""
            ).strip()
            self.load_preview(path)
        elif not self.gallery_images:
            self.load_preview("")

    def _update_primary_fields(self) -> None:
        if not self.gallery_images:
            self.image_path.clear()
            self.load_preview("")
            return
        primary = self.gallery_images[0]
        path = str(primary.get("image_path", "") or "").strip()
        self.image_path.setText(path)
        self.load_preview(path)

    def load_preview(self, path: str) -> None:
        if not path:
            self.image_preview.clear()
            return

        resolved = resolve_data_path(path)
        pixmap = QPixmap(str(resolved))
        if pixmap.isNull():
            self.image_preview.setText("Sin vista previa")
            return

        pixmap = pixmap.scaled(
            170,
            170,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_preview.setPixmap(pixmap)

    def _color_stock_values(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for line in self.color_stock.toPlainText().splitlines():
            try:
                color, stock = line.rsplit(":", 1)
            except ValueError:
                continue
            color = color.strip()
            if not color:
                continue
            try:
                result[color] = max(
                    int(stock.strip().replace(",", "")),
                    0,
                )
            except ValueError:
                continue
        return result

    def _gallery_for_save(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for position, image in enumerate(self.gallery_images, start=1):
            item = dict(image)
            item["position"] = position
            result.append(item)
        return result

    def save_product(self) -> None:
        code = self.code.text().strip()
        name = self.name.text().strip()
        category = self.category.selected_text()
        description = self.description.toPlainText().strip()

        if not code:
            code = self.service.repository.next_product_code()
            self.code.setText(code)

        if not name:
            QMessageBox.warning(
                self,
                "Datos incompletos",
                "El nombre es obligatorio.",
            )
            return

        gallery = self._gallery_for_save()
        primary = gallery[0] if gallery else {}
        image_path = str(primary.get("image_path", "") or "").strip()
        image_url = str(primary.get("url", "") or "").strip()
        image_hash = str(primary.get("image_hash", "") or "").strip()

        if self.product is None:
            product = Product(
                code=code,
                name=name,
                category=category,
                description=description,
                price=self.price.value(),
                price_sample=self.price_sample.value(),
                price_hundred=self.price_hundred.value(),
                price_thousand=self.price_thousand.value(),
                stock=self.stock.value(),
                color_stock=self._color_stock_values(),
                image_url=image_url,
                image_path=image_path,
                image_hash=image_hash,
                gallery_images=gallery,
            )
        else:
            product = Product(
                code=self.product.code,
                name=name,
                category=category,
                description=description,
                price=self.price.value(),
                price_sample=self.price_sample.value(),
                price_hundred=self.price_hundred.value(),
                price_thousand=self.price_thousand.value(),
                stock=self.stock.value(),
                color_stock=self._color_stock_values(),
                image_url=image_url or self.product.image_url,
                image_path=image_path,
                image_hash=image_hash,
                gallery_images=gallery,
                content_hash=self.product.content_hash,
                product_id=self.product.id,
            )

        try:
            if self.product:
                self.service.update_product(product)
                message = "Producto actualizado correctamente."
            else:
                self.service.create_product(product)
                message = "Producto creado correctamente."
        except sqlite3.IntegrityError:
            QMessageBox.critical(
                self,
                "Error",
                "Ya existe un producto con ese código.",
            )
            return
        except sqlite3.Error as error:
            QMessageBox.critical(
                self,
                "Error de base de datos",
                str(error),
            )
            return
        except ValueError as error:
            QMessageBox.critical(
                self,
                "Error de validación",
                str(error),
            )
            return

        QMessageBox.information(self, "Correcto", message)
        self.accept()
