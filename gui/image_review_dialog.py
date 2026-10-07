from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.runtime_paths import resolve_data_path
from services.scraping.image_review_service import ImageReviewService


class _ImageChoiceLabel(QLabel):
    """Miniatura clicable para seleccionar una alternativa de imagen."""

    def __init__(self, callback, parent=None) -> None:
        super().__init__(parent)
        self._callback = callback
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._callback()
        super().mouseReleaseEvent(event)


class ImageReviewDialog(QDialog):
    """Revisa imágenes nuevas detectadas por una actualización del catálogo."""

    THUMBNAIL_SIZE = 130

    def __init__(
        self,
        service: ImageReviewService | None = None,
        on_catalog_changed=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.service = service or ImageReviewService()
        self.on_catalog_changed = on_catalog_changed
        self.records: list[dict] = []
        self._records_signature: tuple = ()
        self._page = 0
        self.PAGE_SIZE = 24
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowTitle("Revisión de imágenes detectadas")
        self.resize(1040, 620)
        self._build_ui()
        self.reload()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(700)
        self.refresh_timer.timeout.connect(self.reload)
        self.refresh_timer.start()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-weight: bold;")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Código", "Producto", "Imagen actual", "Imágenes detectadas", "Acciones"],
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet(
            "QTableWidget {"
            " background-color: #fbfdff;"
            " gridline-color: #dce7f1;"
            " color: #173f6d;"
            "}"
            " QTableWidget::item {"
            " padding: 4px;"
            ' font-family: "Segoe UI";'
            " font-size: 13px;"
            " vertical-align: center;"
            "}"
            " QHeaderView::section {"
            " padding: 6px;"
            ' font-family: "Segoe UI";'
            " font-size: 13px;"
            " font-weight: bold;"
            " background-color: #eef5fb;"
            " color: #173f6d;"
            "}"
        )
        layout.addWidget(self.table, 1)

        navigation = QWidget()
        navigation_layout = QHBoxLayout(navigation)
        navigation_layout.setContentsMargins(0, 0, 0, 0)
        navigation_layout.setSpacing(6)

        self.previous_button = QPushButton("‹ Anteriores")
        self.previous_button.clicked.connect(self._previous_page)
        navigation_layout.addWidget(self.previous_button)

        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        navigation_layout.addWidget(self.page_label, 1)

        self.next_button = QPushButton("Siguientes ›")
        self.next_button.clicked.connect(self._next_page)
        navigation_layout.addWidget(self.next_button)

        layout.addWidget(navigation)

        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.close)
        close_button.setFixedHeight(34)
        layout.addWidget(close_button)

    def reload(self) -> None:
        records = self.service.available()
        signature = tuple(
            (
                str(record.get("id", "")),
                str(record.get("status", "")),
                str(record.get("kind", "replacement")),
                str(record.get("candidate_hash", "")),
                tuple(
                    (
                        str(option.get("path", "")),
                        str(option.get("hash", "")),
                    )
                    for option in list(
                        record.get("candidate_options", []) or []
                    )
                ),
            )
            for record in records
        )
        if signature == self._records_signature and hasattr(self, "_visible_records"):
            self._update_navigation()
            return
        self._records_signature = signature
        self.records = records
        max_page = max((len(self.records) - 1) // self.PAGE_SIZE, 0)
        self._page = min(self._page, max_page)
        start = self._page * self.PAGE_SIZE
        self._visible_records = self.records[start : start + self.PAGE_SIZE]
        self.summary_label.setText(
            f"Imágenes nuevas o actualizadas: {len(self.records)}. "
            f"Mostrando {start + 1 if self.records else 0}-"
            f"{min(start + self.PAGE_SIZE, len(self.records))}. "
            "La imagen actual se conserva hasta aprobar un cambio.",
        )
        self.table.setRowCount(len(self._visible_records))

        for row, record in enumerate(self._visible_records):
            self._populate_row(row, record)

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 110)
        self.table.setColumnWidth(1, 230)
        self.table.setColumnWidth(2, 170)
        self.table.setColumnWidth(3, 430)
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, 165)
        self._update_navigation()

    def _update_navigation(self) -> None:
        total = len(self.records)
        pages = max((total + self.PAGE_SIZE - 1) // self.PAGE_SIZE, 1)
        current = min(self._page + 1, pages)
        self.page_label.setText(f"Página {current} de {pages}")
        self.previous_button.setEnabled(self._page > 0)
        self.next_button.setEnabled(self._page + 1 < pages)

    def _previous_page(self) -> None:
        if self._page <= 0:
            return
        self._page -= 1
        self._records_signature = ()
        self.reload()

    def _next_page(self) -> None:
        if (self._page + 1) * self.PAGE_SIZE >= len(self.records):
            return
        self._page += 1
        self._records_signature = ()
        self.reload()

    def _populate_row(self, row: int, record: dict) -> None:
        self.table.setItem(
            row,
            0,
            QTableWidgetItem(str(record.get("code", ""))),
        )
        self.table.setItem(
            row,
            1,
            QTableWidgetItem(str(record.get("product_name", ""))),
        )

        current = self._preview_widget(
            resolve_data_path(str(record.get("current_path", "") or "")),
            "Sin imagen",
        )
        candidate = self._candidate_widget(record)
        self.table.setCellWidget(row, 2, current)
        self.table.setCellWidget(row, 3, candidate)

        actions = QWidget()
        action_layout = QVBoxLayout(actions)
        action_layout.setContentsMargins(4, 4, 4, 4)
        action_layout.setSpacing(6)

        review_id = str(record["id"])
        is_gallery = str(record.get("kind", "replacement")) == "gallery"
        if is_gallery:
            accept_button = QPushButton("Aceptar galería")
            accept_button.clicked.connect(
                lambda _checked=False, rid=review_id: self._apply(
                    rid,
                    "accept_gallery",
                ),
            )
            action_layout.addWidget(accept_button)

            dismiss_button = QPushButton("Descartar galería")
            dismiss_button.clicked.connect(
                lambda _checked=False, rid=review_id: self._apply(
                    rid,
                    "dismiss_gallery",
                ),
            )
            action_layout.addWidget(dismiss_button)
        else:
            keep_button = QPushButton("Conservar actual")
            keep_button.clicked.connect(
                lambda _checked=False, rid=review_id: self._apply(
                    rid,
                    "keep",
                ),
            )
            action_layout.addWidget(keep_button)

            replace_button = QPushButton("Reemplazar por detectada")
            replace_button.clicked.connect(
                lambda _checked=False, rid=review_id: self._apply(
                    rid,
                    "replace",
                ),
            )
            action_layout.addWidget(replace_button)

            manual_button = QPushButton("Elegir otra imagen…")
            manual_button.clicked.connect(
                lambda _checked=False, rid=review_id: self._choose_manual(
                    rid,
                ),
            )
            action_layout.addWidget(manual_button)

        action_layout.addStretch()

        self.table.setCellWidget(row, 4, actions)

    def _candidate_widget(self, record: dict) -> QWidget:
        options = list(record.get("candidate_options", []) or [])
        if not options:
            fallback = str(record.get("candidate_path", "") or "")
            if fallback:
                options = [{
                    "path": fallback,
                    "url": str(record.get("candidate_url", "") or ""),
                    "generic": False,
                }]

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(6)

        if not options:
            label = QLabel("No hay alternativas detectadas.")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            layout.addWidget(label)
            return container

        for index, option in enumerate(options, start=1):
            path = resolve_data_path(str(option.get("path", "") or ""))
            option_path = str(option.get("path", "") or "")
            label = _ImageChoiceLabel(
                lambda rid=str(record["id"]), selected=option_path: self._apply(
                    rid,
                    "candidate",
                    selected,
                ),
            )
            label.setFixedSize(125, 125)
            label.setStyleSheet(
                "QLabel {"
                " background-color: #ffffff;"
                " border: 2px solid #cbddea;"
                " color: #6b7c8f;"
                "}"
                " QLabel:hover {"
                " border: 2px solid #6b8fb3;"
                "}",
            )
            if path.is_file():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    label.setPixmap(
                        pixmap.scaled(
                            117,
                            117,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        ),
                    )
            if label.pixmap() is None:
                label.setText(f"Alternativa {index}")
            label.setToolTip(
                f"Alternativa {index}. "
                f"{'Detectada en la galería.' if option.get('gallery') else 'Detectada en la tarjeta.'} "
                "Haga clic para seleccionarla.",
            )
            layout.addWidget(label)

        layout.addStretch()
        return container

    @classmethod
    def _preview_widget(cls, path: Path, empty_text: str) -> QLabel:
        label = QLabel()
        label.setFixedSize(cls.THUMBNAIL_SIZE, cls.THUMBNAIL_SIZE)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            "QLabel {"
            " background-color: #ffffff;"
            " border: 1px solid #cbddea;"
            " color: #6b7c8f;"
            "}"
        )

        if not path.is_file():
            label.setText(empty_text)
            return label

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            label.setText("No se pudo previsualizar")
            return label

        label.setPixmap(
            pixmap.scaled(
                cls.THUMBNAIL_SIZE - 8,
                cls.THUMBNAIL_SIZE - 8,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ),
        )
        label.setToolTip(str(path))
        return label

    def _choose_manual(self, review_id: str) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Elegir nueva imagen",
            "",
            "Imágenes (*.jpg *.jpeg *.png *.webp *.gif)",
        )
        if not filename:
            return
        self._apply(review_id, "manual", filename)

    def _apply(
        self,
        review_id: str,
        action: str,
        manual_path: str | None = None,
    ) -> None:
        was_pending = any(
            str(record.get("id", "")) == review_id
            and record.get("status") == "pending"
            for record in self.records
        )
        try:
            result = self.service.apply_selection(
                review_id,
                action,
                manual_path=manual_path,
            )
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Revisión de imágenes",
                str(error),
            )
            return

        if (
            was_pending
            and action in {"candidate", "manual"}
            and result.get("selected")
        ):
            try:
                finalized = self.service.finalize_selected([review_id])
                result = finalized[0] if finalized else result
            except Exception as error:  # noqa: BLE001
                QMessageBox.critical(
                    self,
                    "Revisión de imágenes",
                    str(error),
                )
                return

        if result.get("changed") and callable(self.on_catalog_changed):
            self.on_catalog_changed()

        self.reload()

    def closeEvent(self, event) -> None:
        self.refresh_timer.stop()
        super().closeEvent(event)
