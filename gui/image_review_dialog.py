from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QResizeEvent, QSize, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QSizePolicy,
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


class _ResponsiveAlternativesWidget(QWidget):
    """Reacomoda alternativas de imagen según el ancho disponible."""

    OPTION_WIDTH = 125
    SPACING = 6

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[QWidget] = []
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setHorizontalSpacing(self.SPACING)
        self._layout.setVerticalSpacing(self.SPACING)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

    def add_widget(self, widget: QWidget) -> None:
        self._items.append(widget)
        self._relayout()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._relayout()

    def sizeHint(self):
        columns = max(1, min(len(self._items), 4))
        rows = max(
            1,
            (len(self._items) + columns - 1) // columns,
        )
        width = (
            4
            + columns * self.OPTION_WIDTH
            + max(0, columns - 1) * self.SPACING
        )
        height = 4 + rows * self.OPTION_WIDTH + max(0, rows - 1) * self.SPACING
        return QSize(width, height)

    def _relayout(self) -> None:
        while self._layout.count():
            self._layout.takeAt(0)
        available_width = max(self.width() - 4, self.OPTION_WIDTH)
        columns = max(
            1,
            available_width // (self.OPTION_WIDTH + self.SPACING),
        )
        for index, widget in enumerate(self._items):
            self._layout.addWidget(
                widget,
                index // columns,
                index % columns,
            )


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
        self._records_signature: tuple | None = ()
        self._page = 0
        self.PAGE_SIZE = 24
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
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
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Código", "Producto", "Imagen actual", "Imágenes detectadas"],
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setWordWrap(True)
        self.table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(140)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
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

        self.previous_button = QPushButton("<< Anteriores")
        self.previous_button.clicked.connect(self._previous_page)
        navigation_layout.addWidget(self.previous_button)

        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        navigation_layout.addWidget(self.page_label, 1)

        self.next_button = QPushButton("Siguientes >>")
        self.next_button.clicked.connect(self._next_page)
        navigation_layout.addWidget(self.next_button)

        layout.addWidget(navigation)

        self.apply_button = QPushButton("APLICAR")
        self.apply_button.clicked.connect(self._apply_changes)
        self.apply_button.setFixedHeight(36)
        self.apply_button.setEnabled(False)
        layout.addWidget(self.apply_button)

    def reload(self) -> None:
        records = self.service.available()
        signature = tuple(
            (
                str(record.get("id", "")),
                str(record.get("status", "")),
                str(record.get("kind", "replacement")),
                str(record.get("candidate_hash", "")),
                str(record.get("selected_action", "")),
                str(record.get("selected_path", "")),
                str(record.get("selected_url", "")),
                tuple(
                    str(value)
                    for value in list(record.get("excluded_options", []) or [])
                ),
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
        if (
            self._records_signature is not None
            and signature == self._records_signature
            and hasattr(self, "_visible_records")
        ):
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

        self._fit_table_columns()
        self._update_navigation()

    def _update_navigation(self) -> None:
        total = len(self.records)
        pages = max((total + self.PAGE_SIZE - 1) // self.PAGE_SIZE, 1)
        current = min(self._page + 1, pages)
        self.page_label.setText(f"Página {current} de {pages}")
        self.previous_button.setEnabled(self._page > 0)
        self.next_button.setEnabled(self._page + 1 < pages)
        self.apply_button.setEnabled(
            any(
                str(record.get("selected_action", "") or "").strip()
                or list(record.get("excluded_options", []) or [])
                for record in self.records
            )
        )

    def _previous_page(self) -> None:
        if self._page <= 0:
            return
        self._page -= 1
        self._records_signature = None
        self.reload()

    def _next_page(self) -> None:
        if (self._page + 1) * self.PAGE_SIZE >= len(self.records):
            return
        self._page += 1
        self._records_signature = None
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

        current = self._current_widget(record)
        candidate = self._candidate_widget(record)
        self.table.setCellWidget(row, 2, current)
        self.table.setCellWidget(row, 3, candidate)

    def _candidate_widget(self, record: dict) -> QWidget:
        excluded = {
            str(value).strip()
            for value in list(record.get("excluded_options", []) or [])
            if str(value).strip()
        }
        options = [
            option
            for option in list(record.get("candidate_options", []) or [])
            if str(option.get("path", "") or "").strip() not in excluded
        ]
        if not options:
            fallback = str(record.get("candidate_path", "") or "")
            if fallback and fallback not in excluded:
                options = [{
                    "path": fallback,
                    "url": str(record.get("candidate_url", "") or ""),
                    "generic": False,
                }]

        container = _ResponsiveAlternativesWidget()

        if not options:
            label = QLabel("No hay alternativas detectadas.")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            container.add_widget(label)
            return container

        for index, option in enumerate(options, start=1):
            path = resolve_data_path(str(option.get("path", "") or ""))
            option_path = str(option.get("path", "") or "")

            is_gallery = (
                str(record.get("kind", "replacement")).strip().casefold()
                == "gallery"
            )
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
                "}"
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
                f"{'Detectada en la galería.' if is_gallery else 'Detectada en la tarjeta.'} "
                "Haga clic para seleccionarla.",
            )

            if not is_gallery:
                container.add_widget(label)
                continue

            option_container = QWidget()
            option_layout = QGridLayout(option_container)
            option_layout.setContentsMargins(0, 0, 0, 0)
            option_layout.setSpacing(0)
            option_layout.addWidget(label, 0, 0)

            reject_button = QPushButton("x")
            reject_button.setFixedSize(22, 22)
            reject_button.setToolTip(
                "Excluir esta alternativa; no se guardará en la galería."
            )
            reject_button.setStyleSheet(
                "QPushButton {"
                " color: #173f6d;"
                " background-color: #ffffff;"
                " border: 1px solid #cbddea;"
                " border-radius: 11px;"
                " font-weight: bold;"
                " padding: 0px;"
                "}"
                " QPushButton:hover {"
                " background-color: #eef5fb;"
                "}"
            )
            reject_button.clicked.connect(
                lambda _checked=False, rid=str(record["id"]), selected=option_path:
                self._exclude_candidate(rid, selected),
            )
            option_layout.addWidget(
                reject_button,
                0,
                0,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
            )
            container.add_widget(option_container)

        return container

    def _exclude_candidate(self, review_id: str, option_path: str) -> None:
        try:
            self.service.exclude_candidate(review_id, option_path)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Revisión de imágenes",
                str(error),
            )
            return
        self._records_signature = None
        self.reload()

    def _current_widget(self, record: dict) -> QWidget:
        path = self._selected_preview_path(record)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        label = _ImageChoiceLabel(
            lambda rid=str(record["id"]): self._choose_manual(rid),
        )
        label.setFixedSize(self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            "QLabel {"
            " background-color: #ffffff;"
            " border: 2px solid #cbddea;"
            " color: #6b7c8f;"
            "}"
            " QLabel:hover {"
            " border: 2px solid #6b8fb3;"
            "}"
        )

        if not path.is_file():
            label.setText("Sin imagen")
        else:
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                label.setText("No se pudo previsualizar")
            else:
                label.setPixmap(
                    pixmap.scaled(
                        self.THUMBNAIL_SIZE - 8,
                        self.THUMBNAIL_SIZE - 8,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    ),
                )
        label.setToolTip("Haga clic para elegir una imagen del archivo.")
        layout.addWidget(label, 0, Qt.AlignmentFlag.AlignCenter)

        apply_button = QPushButton("APLICAR")
        apply_button.setObjectName("apply_review_button")
        apply_button.setEnabled(self._record_has_pending_changes(record))
        apply_button.setToolTip(
            "Aplica solamente esta revisión."
            if apply_button.isEnabled()
            else "Seleccione una alternativa antes de aplicar.",
        )
        apply_button.clicked.connect(
            lambda _checked=False, rid=str(record["id"]):
            self._apply_single_changes(rid),
        )
        layout.addWidget(apply_button)
        return container

    @staticmethod
    def _record_has_pending_changes(record: dict) -> bool:
        return bool(
            str(record.get("selected_action", "") or "").strip()
            or list(record.get("excluded_options", []) or [])
        )

    @staticmethod
    def _selected_preview_path(record: dict) -> Path:
        selected_action = str(
            record.get("selected_action", "") or ""
        ).casefold()
        selected_path = str(
            record.get("selected_path", "") or ""
        ).strip()
        if selected_action in {"candidate", "manual"} and selected_path:
            candidate = resolve_data_path(selected_path)
            if candidate.is_file():
                return candidate
        return resolve_data_path(
            str(record.get("current_path", "") or "")
        )

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
        try:
            self.service.apply_selection(
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

        self._records_signature = None
        self.reload()

    def _apply_single_changes(self, review_id: str) -> None:
        try:
            results = self.service.finalize_selected([review_id])
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Revisión de imágenes",
                str(error),
            )
            return

        if results and callable(self.on_catalog_changed):
            self.on_catalog_changed()

        self._records_signature = None
        self.reload()
        if not self.records:
            self.close()

    def _apply_changes(self) -> None:
        review_ids = [
            str(record.get("id", ""))
            for record in self.records
            if (
                str(record.get("selected_action", "") or "").strip()
                or list(record.get("excluded_options", []) or [])
            )
        ]
        if not review_ids:
            return

        try:
            results = self.service.finalize_selected(review_ids)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Revisión de imágenes",
                str(error),
            )
            return

        if results and callable(self.on_catalog_changed):
            self.on_catalog_changed()

        self._records_signature = None
        self.reload()
        if not self.records:
            self.close()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "table"):
            return
        self._fit_table_columns()

    def _fit_table_columns(self) -> None:
        if self.width() <= 0:
            return
        header = self.table.horizontalHeader()
        for column in range(3):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.resizeColumnsToContents()

        title_width = (
            self.fontMetrics().horizontalAdvance("Imágenes detectadas") + 16
        )
        header.resizeSection(
            3,
            max(
                title_width,
                header.sectionSize(3),
                140,
            ),
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.resizeRowsToContents()

    def closeEvent(self, event) -> None:
        self.refresh_timer.stop()
        super().closeEvent(event)
