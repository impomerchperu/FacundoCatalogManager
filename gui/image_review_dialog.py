from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGridLayout,
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
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Código", "Producto", "Imagen actual", "Imágenes detectadas"],
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
        self.table.setColumnWidth(3, 560)
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
                layout.addWidget(label)
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
            layout.addWidget(option_container)

        layout.addStretch()
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
        self._records_signature = ()
        self.reload()

    def _current_widget(self, record: dict) -> _ImageChoiceLabel:
        path = self._selected_preview_path(record)
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
        return label

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

        self._records_signature = ()
        self.reload()

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

        self._records_signature = ()
        self.reload()
        if not self.records:
            self.close()

    def closeEvent(self, event) -> None:
        self.refresh_timer.stop()
        super().closeEvent(event)
