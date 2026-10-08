from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
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

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        available_width = max(int(width) - 4, self.OPTION_WIDTH)
        columns = max(
            1,
            (available_width + self.SPACING) // (self.OPTION_WIDTH + self.SPACING),
        )
        rows = max(
            1,
            (len(self._items) + columns - 1) // columns,
        )
        margins = self._layout.contentsMargins()
        return (
            margins.top()
            + margins.bottom()
            + rows * self.OPTION_WIDTH
            + max(0, rows - 1) * self.SPACING
        )

    def sizeHint(self) -> QSize:
        columns = max(1, min(len(self._items), 4))
        width = (
            4
            + columns * self.OPTION_WIDTH
            + max(0, columns - 1) * self.SPACING
        )
        return QSize(width, self.heightForWidth(width))

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
            "Seleccione una alternativa, elimine una imagen o use APLICAR para conservar la actual.",
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
        code_item = QTableWidgetItem(str(record.get("code", "")))
        code_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 0, code_item)
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
            dict(option)
            for option in list(record.get("candidate_options", []) or [])
            if str(option.get("path", "") or "").strip() not in excluded
        ]
        if not options:
            fallback = str(record.get("candidate_path", "") or "").strip()
            if fallback and fallback not in excluded:
                options = [{
                    "path": fallback,
                    "url": str(record.get("candidate_url", "") or ""),
                    "generic": False,
                }]

        selected_action = str(
            record.get("selected_action", "") or ""
        ).strip().casefold()
        selected_path = str(record.get("selected_path", "") or "").strip()
        current_path = str(record.get("current_path", "") or "").strip()
        if selected_action == "candidate" and selected_path:
            for index, option in enumerate(options):
                if str(option.get("path", "") or "").strip() == selected_path:
                    options[index] = {
                        "path": current_path,
                        "url": str(record.get("current_url", "") or ""),
                        "hash": str(record.get("current_hash", "") or ""),
                        "current": True,
                    }
                    break

        container = _ResponsiveAlternativesWidget()
        if not options:
            label = QLabel("No hay alternativas detectadas.")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            container.add_widget(label)
            return container

        is_gallery = (
            str(record.get("kind", "replacement")).strip().casefold()
            == "gallery"
        )
        for index, option in enumerate(options, start=1):
            option_path = str(option.get("path", "") or "").strip()
            is_current = bool(option.get("current"))
            description = (
                "Imagen actual anterior."
                if is_current
                else (
                    "Detectada en la galería."
                    if is_gallery
                    else "Detectada en la tarjeta."
                )
            )
            if is_current:
                card = self._image_card(
                    option_path,
                    lambda rid=str(record["id"]): self._apply(rid, "keep"),
                    lambda rid=str(record["id"]): self._remove_current(rid),
                    f"Imagen actual anterior a la selección {index}. {description}",
                )
            else:
                card = self._image_card(
                    option_path,
                    lambda rid=str(record["id"]), selected=option_path:
                    self._apply(rid, "candidate", selected),
                    lambda rid=str(record["id"]), selected=option_path:
                    self._remove_candidate(rid, selected),
                    f"Alternativa {index}. {description}",
                )
            container.add_widget(card)
        return container

    def _current_widget(self, record: dict) -> QWidget:
        path = self._selected_preview_path(record)
        selected_action = str(
            record.get("selected_action", "") or ""
        ).strip().casefold()

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        image_label = self._thumbnail_label(
            "" if selected_action == "delete" else str(path),
            "Imagen actual. Haga clic para elegir una imagen del archivo.",
            fixed_size=self.THUMBNAIL_SIZE,
        )
        if selected_action == "delete":
            image_label.setText("Marcada para eliminar")

        def current_action() -> None:
            self._choose_manual(str(record["id"]))
        image_card = self._image_card(
            "" if selected_action == "delete" else str(path),
            current_action,
            lambda rid=str(record["id"]): self._remove_current(rid),
            "Imagen actual. Haga clic para elegir una imagen del archivo.",
            existing_label=image_label,
        )
        layout.addWidget(image_card, 0, Qt.AlignmentFlag.AlignCenter)

        apply_button = QPushButton("APLICAR")
        apply_button.setObjectName("apply_review_button")
        apply_button.setEnabled(True)
        apply_button.setToolTip(
            "Conserva la imagen actual y aplica esta revisión."
            if not self._record_has_pending_changes(record)
            else "Aplica solamente esta revisión.",
        )
        apply_button.clicked.connect(
            lambda _checked=False, rid=str(record["id"]):
            self._apply_single_changes(rid),
        )
        layout.addWidget(apply_button)
        return container

    @staticmethod
    def _thumbnail_style() -> str:
        return (
            "QLabel {"
            " background-color: #ffffff;"
            " border: 2px solid #cbddea;"
            " color: #6b7c8f;"
            "}"
            " QLabel:hover {"
            " border: 2px solid #6b8fb3;"
            "}"
        )

    def _thumbnail_label(
        self,
        path_value: str,
        tooltip: str,
        *,
        fixed_size: int = 125,
    ) -> _ImageChoiceLabel:
        path = resolve_data_path(path_value)
        label = _ImageChoiceLabel(lambda: None)
        label.setFixedSize(fixed_size, fixed_size)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(self._thumbnail_style())
        label.setProperty("image_path", str(path_value))
        if path_value and path.is_file():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                label.setPixmap(
                    pixmap.scaled(
                        fixed_size - 8,
                        fixed_size - 8,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    ),
                )
        if label.pixmap() is None:
            label.setText(
                "Imagen actual"
                if "Imagen actual" in tooltip
                else "Alternativa"
            )
        label.setToolTip(tooltip)
        return label

    def _image_card(
        self,
        path_value: str,
        on_select,
        on_remove,
        tooltip: str,
        *,
        existing_label: _ImageChoiceLabel | None = None,
    ) -> QWidget:
        card = QWidget()
        grid = QGridLayout(card)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        label = existing_label or self._thumbnail_label(path_value, tooltip)
        label._callback = on_select
        grid.addWidget(label, 0, 0)

        remove_button = QPushButton("X")
        remove_button.setFixedSize(22, 22)
        remove_button.setToolTip("Eliminar esta imagen.")
        remove_button.setStyleSheet(
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
        remove_button.clicked.connect(
            lambda _checked=False: on_remove(),
        )
        grid.addWidget(
            remove_button,
            0,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )
        return card

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
            return resolve_data_path(selected_path)
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

    def _remove_candidate(self, review_id: str, option_path: str) -> None:
        try:
            remove = getattr(self.service, "remove_candidate", None)
            if callable(remove):
                remove(review_id, option_path)
            else:
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

    def _remove_current(self, review_id: str) -> None:
        try:
            self.service.apply_selection(review_id, "delete")
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
        record = next(
            (
                item
                for item in self.records
                if str(item.get("id", "")) == str(review_id)
            ),
            None,
        )
        try:
            if record is not None and not self._record_has_pending_changes(record):
                self.service.apply_selection(review_id, "keep")
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
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.resizeSection(0, 105)
        header.resizeSection(1, 280)
        header.resizeSection(2, 170)
        self.table.resizeRowsToContents()

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

    def closeEvent(self, event) -> None:
        self.refresh_timer.stop()
        super().closeEvent(event)
