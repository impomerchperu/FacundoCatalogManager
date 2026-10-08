import sqlite3

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QFocusEvent,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyleOptionButton,
    QVBoxLayout,
    QWidget,
)

from config.runtime_paths import is_frozen
from controllers.product_controller import ProductController
from gui.product_table import ProductTable
from gui.scraping_dialog import ScrapingDialog
from gui.workers.catalog_bootstrap_worker import CatalogBootstrapWorker
from gui.workers.catalog_load_worker import CatalogLoadWorker
from models.product import Product
from services.product_search import product_matches_search
from services.scraping.category_name_normalizer import (
    available_category_names,
    split_category_names,
)
from services.scraping.image_review_service import ImageReviewService

if TYPE_CHECKING:
    from gui.image_review_dialog import ImageReviewDialog
    from gui.scraping_history_dialog import ScrapingHistoryDialog


class CategoryFilterButton(QPushButton):
    """Botón de categoría con navegación vertical y edición por doble clic."""

    doubleClicked = Signal()

    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._focus_frame = QFrame(self)
        self._focus_frame.setObjectName("category_focus_frame")
        self._focus_frame.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self._focus_frame.setStyleSheet(
            "#category_focus_frame {"
            " border: 1px solid #000000;"
            " background: transparent;"
            "}"
        )
        self._focus_frame.hide()
        self._focus_frame.raise_()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _update_focus_frame(self) -> None:
        self._focus_frame.setGeometry(
            self.rect().adjusted(1, 1, -2, -2),
        )
        self._focus_frame.setVisible(self.hasFocus())
        self._focus_frame.raise_()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_focus_frame()

    def focusInEvent(self, event: QFocusEvent) -> None:
        super().focusInEvent(event)
        self._update_focus_frame()

    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        self._update_focus_frame()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.state &= ~QStyle.StateFlag.State_HasFocus

        painter = QPainter(self)
        self.style().drawControl(
            QStyle.ControlElement.CE_PushButton,
            option,
            painter,
            self,
        )

    def _navigation_buttons(self) -> list["CategoryFilterButton"]:
        parent = self.parentWidget()
        if parent is None:
            return []

        layout = parent.layout()
        if layout is None:
            return []

        buttons: list[CategoryFilterButton] = []
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, CategoryFilterButton):
                buttons.append(widget)
        return buttons

    def _category_scroll_area(self) -> "CategoryScrollArea | None":
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, CategoryScrollArea):
                return parent
            parent = parent.parentWidget()
        return None

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            buttons = self._navigation_buttons()
            try:
                index = buttons.index(self)
            except ValueError:
                index = -1

            step = -1 if event.key() == Qt.Key.Key_Up else 1
            target_index = index + step
            if 0 <= target_index < len(buttons):
                target = buttons[target_index]
                target.setFocus(Qt.FocusReason.OtherFocusReason)
                scroll_area = self._category_scroll_area()
                if scroll_area is not None:
                    scroll_area.ensure_widget_visible_vertically(target)
                event.accept()
                return

        super().keyPressEvent(event)


class CategoryScrollArea(QScrollArea):
    """Área de categorías que solo permite desplazamiento vertical."""

    FOCUS_FRAME_MARGIN = 2

    def ensure_widget_visible_vertically(self, widget: QWidget) -> None:
        viewport = self.viewport()
        top_left = widget.mapTo(viewport, QPoint(0, 0))
        widget_top = top_left.y()
        widget_bottom = widget_top + widget.height()
        viewport_height = viewport.height()
        margin = self.FOCUS_FRAME_MARGIN
        vertical_scrollbar = self.verticalScrollBar()
        horizontal_scrollbar = self.horizontalScrollBar()

        horizontal_scrollbar.setValue(0)
        if widget_top < margin:
            vertical_scrollbar.setValue(
                vertical_scrollbar.value() + widget_top - margin,
            )
        elif widget_bottom > viewport_height - margin:
            vertical_scrollbar.setValue(
                vertical_scrollbar.value()
                + widget_bottom
                - (viewport_height - margin),
            )
        horizontal_scrollbar.setValue(0)

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        del dx
        self.horizontalScrollBar().setValue(0)
        super().scrollContentsBy(0, dy)
        self.horizontalScrollBar().setValue(0)


class MainWindow(QMainWindow):
    """Ventana principal del catálogo."""

    FONT_FAMILY = ProductTable.FONT_FAMILY
    TEXT_COLOR = ProductTable.TABLE_TEXT_COLOR
    ACTIVE_BUTTON_STYLE = """
        QPushButton {
            color: #173f6d;
            font-family: "Segoe UI";
            background-color: #fbfdff;
            border: 1px solid #cbddea;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #eef5fb;
        }
        QPushButton:checked {
            background-color: #d8edf7;
            border: 1px solid #a9cfe2;
            color: #173f6d;
            font-weight: bold;
        }
    """

    TOGGLE_FONT_SIZE = 16
    TOGGLE_BUTTON_HORIZONTAL_PADDING = 4
    TOGGLE_BUTTON_HEIGHT = 40
    SEARCH_FONT_SIZE = 16
    SEARCH_HEIGHT = 38
    COUNTER_FONT_SIZE = 13
    ACTION_BUTTON_FONT_SIZE = 13
    ACTION_BUTTON_HORIZONTAL_PADDING = 4
    ACTION_BUTTON_HEIGHT = 34
    CATEGORY_FONT_SIZE = 13
    CATEGORY_BUTTON_HORIZONTAL_PADDING = 4
    CATEGORY_BUTTON_HEIGHT = 28
    TOP_CONTROLS_SPACING = 4
    CATEGORY_SPACING = 1
    CATEGORY_SIDEBAR_SPACING = 4
    CATEGORY_SIDEBAR_HORIZONTAL_PADDING = 4
    CATEGORY_SIDEBAR_REFERENCE_TEXT = "Enmicadoras / Laminadoras"
    INITIAL_WINDOW_WIDTH = 1200
    INITIAL_WINDOW_HEIGHT = 700

    def __init__(self) -> None:
        super().__init__()
        self.controller = ProductController()
        self.image_review_service = ImageReviewService()
        self.setWindowTitle("Facundo Catalog Manager")
        self.setStyleSheet("QMainWindow { background-color: #ffffff; }")
        self.resize(self.INITIAL_WINDOW_WIDTH, self.INITIAL_WINDOW_HEIGHT)

        base_font = QFont(self.FONT_FAMILY)
        base_font.setPixelSize(ProductTable.FONT_PIXEL_SIZE)
        self.setFont(base_font)

        self.all_products: list[Product] = []
        self.selected_categories: set[str] = set()
        self.stock_only = False
        self.category_buttons: list[QPushButton] = []
        self.categories_visible = False
        self.scraping_dialog: ScrapingDialog | None = None
        self.history_dialog: ScrapingHistoryDialog | None = None
        self.image_review_dialog: ImageReviewDialog | None = None
        self.catalog_bootstrap_thread: QThread | None = None
        self.catalog_bootstrap_worker: CatalogBootstrapWorker | None = None
        self.catalog_bootstrap_running = False
        self.catalog_bootstrap_changed = False
        self.catalog_bootstrap_blocked_buttons: list[QPushButton] = []
        self.catalog_load_thread: QThread | None = None
        self.catalog_load_worker: CatalogLoadWorker | None = None
        self.image_review_button: QPushButton | None = None
        self.image_review_poll_timer = QTimer(self)
        self.image_review_poll_timer.setInterval(700)
        self.image_review_poll_timer.timeout.connect(self._refresh_image_review_state)

        central = QWidget()
        central.setObjectName("main_content")
        central.setStyleSheet("#main_content { background-color: #ffffff; }")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar producto...")
        self.search_box.setMinimumHeight(self.SEARCH_HEIGHT)
        self.search_box.setMinimumWidth(0)
        self.search_box.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.search_box.setStyleSheet(
            "QLineEdit {"
            ' font-family: "Segoe UI";'
            f" font-size: {self.SEARCH_FONT_SIZE}px;"
            " color: #173f6d;"
            " padding: 4px 8px;"
            " background-color: #fbfdff;"
            " border: 1px solid #cbddea;"
            " border-radius: 4px;"
            "}"
        )
        self.search_box.textChanged.connect(self.search_products)

        self.table = ProductTable(self.controller)
        self.table.cellDoubleClicked.connect(self._table_cell_double_clicked)
        self.table.itemChanged.connect(self._table_item_changed)
        self._table_edit_guard = False
        self.create_filter_controls(layout)

        counter_layout = QHBoxLayout()
        counter_layout.setContentsMargins(0, 0, 0, 0)
        self.product_counter = QLabel("Cargando catálogo...")
        self.product_counter.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        self.product_counter.setStyleSheet(
            "QLabel {"
            ' font-family: "Segoe UI";'
            f" font-size: {self.COUNTER_FONT_SIZE}px;"
            " font-weight: bold;"
            " color: #173f6d;"
            "}"
        )
        counter_layout.addWidget(self.product_counter)
        counter_layout.addStretch()
        layout.addLayout(counter_layout)

        self._prepare_category_filter_layout()
        self.category_toggle_button.setChecked(True)
        self._set_initial_window_geometry()

        # El bootstrap histórico no debe bloquear la creación de la ventana.
        # Ambos trabajos comienzan después de que Qt haya podido mostrarla:
        # la lectura del catálogo persistido y la reparación opcional avanzan
        # independientemente.
        QTimer.singleShot(0, self._start_catalog_bootstrap)
        QTimer.singleShot(0, self._load_initial_catalog)
        self.image_review_poll_timer.start()
        self._refresh_image_review_state()

    def _start_catalog_bootstrap(self) -> None:
        """Ejecuta la reparación inicial en segundo plano."""
        if (
            self.catalog_bootstrap_thread is not None
            and self.catalog_bootstrap_thread.isRunning()
        ):
            return

        self.catalog_bootstrap_running = True
        for button in self.catalog_bootstrap_blocked_buttons:
            button.setEnabled(False)

        self.catalog_bootstrap_thread = QThread(self)
        self.catalog_bootstrap_worker = CatalogBootstrapWorker()
        self.catalog_bootstrap_worker.moveToThread(self.catalog_bootstrap_thread)

        self.catalog_bootstrap_thread.started.connect(
            self.catalog_bootstrap_worker.run,
        )
        self.catalog_bootstrap_worker.finished.connect(
            self._catalog_bootstrap_finished,
        )
        self.catalog_bootstrap_worker.error.connect(
            self._catalog_bootstrap_error,
        )
        self.catalog_bootstrap_worker.finished.connect(
            self.catalog_bootstrap_thread.quit,
        )
        self.catalog_bootstrap_worker.error.connect(
            self.catalog_bootstrap_thread.quit,
        )
        self.catalog_bootstrap_thread.finished.connect(
            self._cleanup_catalog_bootstrap,
        )
        self.catalog_bootstrap_thread.start()

    def _load_initial_catalog(self) -> None:
        """Inicia la lectura del catálogo sin bloquear el hilo de la interfaz."""
        if not self.isVisible():
            return

        # En una distribución congelada la primera ejecución puede estar
        # provisionando la semilla del catálogo. Esperamos a que ese trabajo
        # termine antes de abrir una segunda conexión SQLite sobre el archivo
        # que acaba de ser creado/reemplazado. La ventana ya está visible, por
        # lo que esto no bloquea el arranque de la interfaz.
        if is_frozen() and self.catalog_bootstrap_running:
            QTimer.singleShot(25, self._load_initial_catalog)
            return

        self._start_catalog_load()

    def _start_catalog_load(self) -> None:
        if (
            self.catalog_load_thread is not None
            and self.catalog_load_thread.isRunning()
        ):
            return

        self.catalog_load_thread = QThread(self)
        self.catalog_load_worker = CatalogLoadWorker()
        self.catalog_load_worker.moveToThread(self.catalog_load_thread)

        self.catalog_load_thread.started.connect(
            self.catalog_load_worker.run,
        )
        self.catalog_load_worker.finished.connect(
            self._catalog_load_finished,
        )
        self.catalog_load_worker.error.connect(
            self._catalog_load_error,
        )
        self.catalog_load_worker.finished.connect(
            self.catalog_load_thread.quit,
        )
        self.catalog_load_worker.error.connect(
            self.catalog_load_thread.quit,
        )
        self.catalog_load_thread.finished.connect(
            self._cleanup_catalog_load,
        )
        self.catalog_load_thread.start()

    def _catalog_load_finished(self, products: list[Product]) -> None:
        self._apply_catalog_products(products)

    def _catalog_load_error(self, message: str) -> None:
        self.product_counter.setToolTip(
            "No se pudo cargar el catálogo inicial: " + message,
        )

    def _cleanup_catalog_load(self) -> None:
        if self.catalog_load_worker is not None:
            self.catalog_load_worker.deleteLater()
        if self.catalog_load_thread is not None:
            self.catalog_load_thread.deleteLater()
        self.catalog_load_worker = None
        self.catalog_load_thread = None

    def _catalog_bootstrap_finished(self, _count: int, changed: bool) -> None:
        self.catalog_bootstrap_changed = changed

    def _catalog_bootstrap_error(self, message: str) -> None:
        self.product_counter.setToolTip(
            "La verificación inicial del catálogo falló: " + message,
        )

    def _cleanup_catalog_bootstrap(self) -> None:
        changed = self.catalog_bootstrap_changed
        self.catalog_bootstrap_changed = False
        self.catalog_bootstrap_running = False
        for button in self.catalog_bootstrap_blocked_buttons:
            button.setEnabled(True)

        if changed:
            # El hilo ya terminó y su conexión SQLite fue cerrada en el worker;
            # ahora la tabla puede leer el catálogo consolidado con seguridad.
            QTimer.singleShot(0, self._start_catalog_load)

        if self.catalog_bootstrap_worker is not None:
            self.catalog_bootstrap_worker.deleteLater()
        if self.catalog_bootstrap_thread is not None:
            self.catalog_bootstrap_thread.deleteLater()
        self.catalog_bootstrap_worker = None
        self.catalog_bootstrap_thread = None

    def create_filter_controls(self, layout: QVBoxLayout) -> None:
        filter_layout = QVBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(6)

        top_controls = QGridLayout()
        top_controls.setContentsMargins(0, 0, 0, 0)
        top_controls.setHorizontalSpacing(self.TOP_CONTROLS_SPACING)
        top_controls.setVerticalSpacing(0)

        self.category_toggle_button = QPushButton("Filtrar Categorías")
        self.category_toggle_button.setCheckable(True)
        self._configure_toggle_button(
            self.category_toggle_button,
            "Filtrar Categorías",
            "Ocultar Categorías",
        )
        self.category_toggle_button.toggled.connect(
            self.toggle_categories_visibility,
        )
        top_controls.addWidget(self.category_toggle_button, 0, 0)

        self.stock_filter_button = QPushButton("Solo Stock Disponible")
        self.stock_filter_button.setCheckable(True)
        self._configure_toggle_button(
            self.stock_filter_button,
            "Solo Stock Disponible",
        )
        self.stock_filter_button.setToolTip(
            "Mostrar únicamente productos con stock mayor a 0.",
        )
        self.stock_filter_button.toggled.connect(self.toggle_stock_filter)
        top_controls.addWidget(self.stock_filter_button, 0, 1)

        top_controls.addWidget(self.search_box, 0, 2)
        top_controls.setColumnStretch(2, 1)

        self.top_actions_container = QWidget()
        self.top_actions_container.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        action_layout = QHBoxLayout(self.top_actions_container)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(self.TOP_CONTROLS_SPACING)
        self._add_action_buttons(action_layout)
        action_width = 0
        action_widgets = []
        for index in range(action_layout.count()):
            item = action_layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if widget is None:
                continue
            action_widgets.append(widget)
            action_width += widget.width()

        action_width += (
            max(0, len(action_widgets) - 1) * self.TOP_CONTROLS_SPACING
        )
        self.top_actions_container.setFixedWidth(action_width)
        top_controls.addWidget(self.top_actions_container, 0, 3)
        filter_layout.addLayout(top_controls)

        catalog_layout = QHBoxLayout()
        catalog_layout.setContentsMargins(0, 0, 0, 0)
        catalog_layout.setSpacing(self.CATEGORY_SIDEBAR_SPACING)

        self.category_sidebar = QWidget()
        self.category_sidebar.setObjectName("category_sidebar")
        self.category_sidebar.setStyleSheet(
            "#category_sidebar { background-color: #ffffff; }"
        )
        self.category_sidebar_layout = QVBoxLayout(self.category_sidebar)
        self.category_sidebar_layout.setContentsMargins(4, 0, 4, 0)
        self.category_sidebar_layout.setSpacing(self.CATEGORY_SIDEBAR_SPACING)

        self.category_scroll = CategoryScrollArea()
        self.category_scroll.setWidgetResizable(True)
        self.category_scroll.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus,
        )
        self.category_scroll.viewport().setStyleSheet(
            "background-color: #ffffff;"
        )
        self.category_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.category_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self.category_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.category_scroll.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        )
        self.category_scroll.verticalScrollBar().rangeChanged.connect(
            self._sync_category_sidebar_width_with_scrollbar,
        )
        self.category_scroll.setMinimumHeight(0)
        self.category_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.category_scroll.setVisible(False)
        self._sync_category_scrollbar_with_table()
        self.category_sidebar_layout.addWidget(self.category_scroll, 1)

        self.category_container = QWidget()
        self.category_container.setObjectName("category_container")
        self.category_container.setStyleSheet(
            "#category_container { background-color: #ffffff; }"
        )
        self.category_layout = QVBoxLayout(self.category_container)
        self.category_layout.setContentsMargins(0, 0, 0, 0)
        self.category_layout.setSpacing(self.CATEGORY_SPACING)
        self.category_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
        )
        self.category_scroll.setWidget(self.category_container)

        self.all_categories_button = CategoryFilterButton("Todas las categorías")
        self.all_categories_button.setCheckable(True)
        self.all_categories_button.setProperty(
            "category_text",
            "Todas las categorías",
        )
        self.all_categories_button.setStyleSheet(self._category_button_style())
        self.all_categories_button.clicked.connect(self.clear_category_filters)
        self.category_buttons = [self.all_categories_button]
        self._category_sidebar_open_width = 0
        self._category_sidebar_closed_width = 0
        self.category_sidebar.setVisible(False)

        catalog_layout.addWidget(self.category_sidebar, 0)
        catalog_layout.addWidget(self.table, 1)
        filter_layout.addLayout(catalog_layout, 1)
        layout.addLayout(filter_layout)

    def _sync_category_scrollbar_with_table(self) -> None:
        table_scrollbar = self.table.verticalScrollBar()
        category_scrollbar = self.category_scroll.verticalScrollBar()

        category_scrollbar.setSingleStep(table_scrollbar.singleStep())
        category_scrollbar.setFont(table_scrollbar.font())

    def _sync_category_sidebar_width_with_scrollbar(
        self,
        _minimum: int = 0,
        maximum: int = 0,
    ) -> None:
        if not hasattr(self, "_category_sidebar_button_width"):
            return

        scrollbar_width = (
            self.category_scroll.verticalScrollBar().sizeHint().width()
            if maximum > 0
            else 0
        )
        self._category_sidebar_open_width = (
            self._category_sidebar_button_width
            + (2 * self.CATEGORY_SIDEBAR_HORIZONTAL_PADDING)
            + scrollbar_width
        )

        toggle_button = getattr(self, "category_toggle_button", None)
        if toggle_button is not None:
            toggle_button.setFixedWidth(self._category_sidebar_open_width)

        if getattr(self, "categories_visible", False):
            self.category_sidebar.setFixedWidth(
                self._category_sidebar_open_width,
            )

    def _add_action_buttons(self, layout: QHBoxLayout) -> None:
        buttons = [
            ("Exportar", self.export_catalog),
            ("Imágenes (0)", self.open_pending_image_review),
            ("Nuevo", self.new_product),
            ("Importar", self.import_products),
            ("Eliminar", self.delete_selected),
            ("Actualizar catálogo", self.open_scraping),
            ("Historial", self.open_scraping_history),
        ]
        for text, callback in buttons:
            button = QPushButton(text)
            self._configure_action_button(button)
            button.setFixedWidth(button.sizeHint().width())
            button.clicked.connect(callback)
            layout.addWidget(button)
            if text == "Imágenes (0)":
                self.image_review_button = button
                button.setFixedWidth(115)
            if text == "Actualizar catálogo":
                self.catalog_bootstrap_blocked_buttons.append(button)

    @classmethod
    def _configure_action_button(cls, button: QPushButton) -> None:
        font = button.font()
        font.setPixelSize(cls.ACTION_BUTTON_FONT_SIZE)
        button.setFont(font)
        button.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        button.setStyleSheet(
            "QPushButton {"
            ' font-family: "Segoe UI";'
            f" font-size: {cls.ACTION_BUTTON_FONT_SIZE}px;"
            " color: #173f6d;"
            " background-color: #fbfdff;"
            f" padding: 0px {cls.ACTION_BUTTON_HORIZONTAL_PADDING}px;"
            " border: 1px solid #cbddea;"
            " border-radius: 4px;"
            f" min-height: {cls.ACTION_BUTTON_HEIGHT}px;"
            f" max-height: {cls.ACTION_BUTTON_HEIGHT}px;"
            "}"
            " QPushButton:hover { background-color: #eef5fb; }"
            " QPushButton:pressed { background-color: #dbeeff; }"
        )

    @classmethod
    def _configure_toggle_button(cls, button: QPushButton, *texts: str) -> None:
        font = button.font()
        font.setPixelSize(cls.TOGGLE_FONT_SIZE)
        button.setFont(font)
        button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        button.setStyleSheet(
            'QPushButton { font-family: "Segoe UI"; color: #173f6d; padding: 0px 4px; }\n'
            + cls.ACTIVE_BUTTON_STYLE,
        )
        cls._set_toggle_button_width(button, *texts)

    @classmethod
    def _set_toggle_button_width(cls, button: QPushButton, *texts: str) -> None:
        font = button.font()
        metrics = QFontMetrics(font)
        bold_font = QFont(font)
        bold_font.setBold(True)
        bold_metrics = QFontMetrics(bold_font)
        required_width = max(
            max(metrics.horizontalAdvance(text), bold_metrics.horizontalAdvance(text))
            for text in texts
        ) + (2 * cls.TOGGLE_BUTTON_HORIZONTAL_PADDING) + 2
        button.setFixedWidth(required_width)
        button.setFixedHeight(cls.TOGGLE_BUTTON_HEIGHT)

    @classmethod
    def _category_button_style(cls) -> str:
        return (
            'QPushButton {'
            ' font-family: "Segoe UI";'
            f" font-size: {cls.CATEGORY_FONT_SIZE}px;"
            " color: #173f6d;"
            " padding: 0px 4px;"
            " text-align: left;"
            " border: none;"
            " background: transparent;"
            "}"
            " QPushButton:hover { background-color: #eef5fb; }"
            " QPushButton:checked {"
            " background-color: #d8edf7;"
            " color: #173f6d;"
            " font-weight: bold;"
            " border: none;"
            "}"
        )

    @classmethod
    def _category_button_width(cls, button: QPushButton, text: str) -> int:
        font = button.font()
        font.setPixelSize(cls.CATEGORY_FONT_SIZE)
        bold_font = QFont(font)
        bold_font.setBold(True)
        metrics = QFontMetrics(font)
        bold_metrics = QFontMetrics(bold_font)
        return max(
            metrics.horizontalAdvance(text),
            bold_metrics.horizontalAdvance(text),
        ) + (2 * cls.CATEGORY_BUTTON_HORIZONTAL_PADDING) + 2

    @classmethod
    def _fit_category_button(
        cls,
        button: QPushButton,
        text: str,
        max_width: int | None = None,
    ) -> int:
        font = button.font()
        font.setPixelSize(cls.CATEGORY_FONT_SIZE)
        button.setFont(font)
        button.setToolTip(text)
        button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        width = cls._category_button_width(button, text)
        if max_width is not None:
            width = max_width
            text_width = max(
                max_width - (2 * cls.CATEGORY_BUTTON_HORIZONTAL_PADDING),
                1,
            )
            text = QFontMetrics(font).elidedText(
                text,
                Qt.TextElideMode.ElideRight,
                text_width,
            )
        button.setText(text)
        button.setFixedWidth(width)
        button.setFixedHeight(cls.CATEGORY_BUTTON_HEIGHT)
        return width

    def toggle_categories_visibility(self, visible: bool) -> None:
        self.category_toggle_button.setChecked(visible)
        self.categories_visible = visible
        self.category_toggle_button.setText(
            "Ocultar Categorías" if visible else "Filtrar Categorías",
        )
        self.category_toggle_button.setFixedWidth(
            self._category_sidebar_open_width,
        )
        self.category_sidebar.setVisible(visible)
        self.category_scroll.setVisible(visible)
        self.category_sidebar.setFixedWidth(
            self._category_sidebar_open_width,
        )

    def refresh_catalog(self) -> None:
        self._apply_catalog_products(self.controller.get_products())

    def _apply_catalog_products(self, products: list[Product]) -> None:
        self.all_products = list(products)
        self.table.set_category_reference_products(self.all_products)
        self.table.set_category_editor_options(
            available_category_names(
                *(product.category for product in self.all_products)
            )
        )
        self.table.load_products(self.all_products)
        self.rebuild_category_filters()
        self.apply_filters()

    @staticmethod
    def _product_categories(product: Product) -> set[str]:
        return {
            category
            for category in (
                split_category_names(getattr(product, "category", ""))
            )
            if category
        }

    def rebuild_category_filters(self) -> None:
        for button in self.category_buttons:
            if button is not self.all_categories_button:
                button.deleteLater()
        self.category_buttons = [self.all_categories_button]
        self._clear_category_rows()

        categories = sorted(
            {
                category
                for product in self.all_products
                for category in self._product_categories(product)
            },
            key=str.casefold,
        )
        self.selected_categories.intersection_update(set(categories))

        for category in categories:
            button = CategoryFilterButton(category)
            button.setProperty("category_text", category)
            button.setCheckable(True)
            button.setChecked(category in self.selected_categories)
            button.setStyleSheet(self._category_button_style())
            button.clicked.connect(
                lambda checked, value=category: self.toggle_category(
                    value,
                    checked,
                ),
            )
            button.doubleClicked.connect(
                lambda value=category: self.rename_category_button(value)
            )
            self.category_buttons.append(button)

        self._update_all_categories_button()
        self._prepare_category_filter_layout()

    def _clear_category_rows(self) -> None:
        while self.category_layout.count():
            item = self.category_layout.takeAt(0)
            if item is None:
                continue
            row_layout = item.layout()
            if row_layout is None:
                continue
            while row_layout.count():
                child = row_layout.takeAt(0)
                if child is None:
                    continue
                widget = child.widget()
                if widget is not None:
                    widget.setParent(self.category_container)

    def _prepare_category_filter_layout(self) -> None:
        if not hasattr(self, "category_layout") or not self.category_buttons:
            return

        self._clear_category_rows()

        reference_font = QFont(self.category_buttons[0].font())
        reference_font.setPixelSize(self.CATEGORY_FONT_SIZE)
        reference_bold_font = QFont(reference_font)
        reference_bold_font.setBold(True)
        reference_metrics = QFontMetrics(reference_font)
        reference_bold_metrics = QFontMetrics(reference_bold_font)
        reference_text_width = max(
            reference_metrics.horizontalAdvance(self.CATEGORY_SIDEBAR_REFERENCE_TEXT),
            reference_bold_metrics.horizontalAdvance(
                self.CATEGORY_SIDEBAR_REFERENCE_TEXT,
            ),
        )
        category_button_width = (
            reference_text_width
            + (2 * self.CATEGORY_BUTTON_HORIZONTAL_PADDING)
        )
        self._category_sidebar_button_width = category_button_width
        self._category_sidebar_open_width = (
            category_button_width + (2 * self.CATEGORY_SIDEBAR_HORIZONTAL_PADDING)
        )

        for button in self.category_buttons:
            text = str(
                button.property("category_text") or button.text(),
            ).replace("\n", " ")
            self._fit_category_button(
                button,
                text,
                max_width=category_button_width,
            )
            self.category_layout.addWidget(
                button,
                0,
                Qt.AlignmentFlag.AlignLeft,
            )
        toggle_button = getattr(self, "category_toggle_button", None)
        if toggle_button is not None:
            toggle_button.setFixedWidth(self._category_sidebar_open_width)
        self._sync_category_sidebar_width_with_scrollbar(
            maximum=self.category_scroll.verticalScrollBar().maximum(),
        )
        if self.categories_visible:
            self.category_sidebar.setFixedWidth(
                self._category_sidebar_open_width,
            )

    def _update_all_categories_button(self) -> None:
        self.all_categories_button.setChecked(not self.selected_categories)
        self.all_categories_button.setText("Todas las categorías")
        self.all_categories_button.setProperty(
            "category_text",
            "Todas las categorías",
        )

    def clear_category_filters(self) -> None:
        self.selected_categories.clear()
        for button in self.category_buttons:
            if button is not self.all_categories_button:
                button.setChecked(False)
        self._update_all_categories_button()
        self.apply_filters()

    def toggle_category(self, category: str, checked: bool) -> None:
        self.table.clearSelection()
        if checked:
            self.selected_categories.add(category)
        else:
            self.selected_categories.discard(category)
        self._update_all_categories_button()
        self.apply_filters()

    def toggle_stock_filter(self, checked: bool) -> None:
        self.stock_only = checked
        self._set_toggle_button_width(
            self.stock_filter_button,
            "Solo Stock Disponible",
        )
        self.apply_filters()

    def _filtered_products(self) -> list[Product]:
        products = list(self.all_products)
        search_text = self.search_box.text().strip()
        if search_text:
            products = [
                product
                for product in products
                if self.product_matches_search(product, search_text)
            ]
        if self.selected_categories:
            products = [
                product
                for product in products
                if self.selected_categories.intersection(
                    self._product_categories(product),
                )
            ]
        if self.stock_only:
            products = [product for product in products if product.stock > 0]
        return products

    def apply_filters(self) -> None:
        search_text = self.search_box.text().strip()
        products = self._filtered_products()
        self.table.show_only_products(products)
        self.table.set_search_text(search_text)
        self.update_product_counter(len(products))

    @staticmethod
    def product_matches_search(product: Product, search_text: str) -> bool:
        return product_matches_search(product, search_text)

    def open_scraping(self) -> None:
        if getattr(self, "catalog_bootstrap_running", False):
            return
        if self.is_scraping_running():
            if self.scraping_dialog is not None:
                if self.scraping_dialog.isMinimized():
                    self.scraping_dialog.showNormal()
                self.scraping_dialog.raise_()
                self.scraping_dialog.activateWindow()
            return
        # El progreso es una ventana independiente, no una ventana hija del
        # catálogo. Así puede alternarse con MainWindow mediante clic o Alt+Tab.
        self.scraping_dialog = ScrapingDialog()
        self.scraping_dialog.finished_success.connect(self.scraping_finished)
        self.scraping_dialog.finished.connect(self.scraping_dialog_closed)
        self.scraping_dialog.setModal(False)
        self.scraping_dialog.show()
        self.scraping_dialog.raise_()
        self.scraping_dialog.activateWindow()

    def open_scraping_history(self) -> None:
        if self.history_dialog is not None:
            self.history_dialog.load_history()
            if self.history_dialog.isMinimized():
                self.history_dialog.showNormal()
            self.history_dialog.raise_()
            self.history_dialog.activateWindow()
            return

        from gui.scraping_history_dialog import ScrapingHistoryDialog

        self.history_dialog = ScrapingHistoryDialog(self)
        self.history_dialog.finished.connect(lambda: self._history_closed())
        self.history_dialog.setModal(False)
        self.history_dialog.show()
        self.history_dialog.raise_()
        self.history_dialog.activateWindow()

    def _history_closed(self) -> None:
        self.history_dialog = None

    def _refresh_image_review_state(self) -> None:
        button = getattr(self, "image_review_button", None)
        service = getattr(self, "image_review_service", None)
        if button is None or service is None:
            return
        try:
            records = service.available()
        except Exception:  # noqa: BLE001
            return

        count = len(records)
        gallery_count = sum(
            1
            for record in records
            if str(record.get("kind", "replacement")) == "gallery"
        )
        replacement_count = count - gallery_count
        button.setText(f"Imágenes ({count})")
        button.setToolTip(
            f"{gallery_count} galerías nuevas · "
            f"{replacement_count} reemplazos pendientes."
            if count
            else "No hay cambios de imagen pendientes."
        )
        if count:
            button.setStyleSheet(
                "QPushButton {"
                " color: #173f6d; font-weight: bold;"
                " background-color: #fff7d6;"
                " border: 1px solid #e2c85b;"
                " border-radius: 4px;"
                "}"
                " QPushButton:hover { background-color: #fff2bd; }"
            )
        else:
            self._configure_action_button(button)

        gallery_overrides: dict[str, list[dict]] = {}
        for record in records:
            if (
                str(record.get("kind", "replacement")) != "gallery"
                or str(record.get("selected_action", "") or "")
                == "dismiss_gallery"
            ):
                continue
            code = str(record.get("code", "") or "").strip().casefold()
            if not code:
                continue
            excluded = {
                str(value).strip()
                for value in list(record.get("excluded_options", []) or [])
                if str(value).strip()
            }
            gallery_overrides[code] = [
                dict(option)
                for option in list(record.get("candidate_options", []) or [])
                if str(option.get("path", "") or "").strip() not in excluded
            ]
        self.table.set_gallery_overrides(gallery_overrides)

    def open_pending_image_review(self) -> None:
        if self.image_review_dialog is not None:
            self.image_review_dialog.raise_()
            self.image_review_dialog.activateWindow()
            return

        from gui.image_review_dialog import ImageReviewDialog

        dialog = ImageReviewDialog(
            service=self.image_review_service,
            on_catalog_changed=self.refresh_catalog,
            parent=self,
        )
        if not dialog.records:
            dialog.close()
            return

        self.image_review_dialog = dialog
        dialog.finished.connect(self._image_review_dialog_closed)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _image_review_dialog_closed(self) -> None:
        self.image_review_dialog = None
        self._refresh_image_review_state()

    def scraping_finished(self) -> None:
        self.refresh_catalog()
        self._refresh_image_review_state()
        if self.history_dialog is not None:
            self.history_dialog.load_history()
        self.open_pending_image_review()
        if self.scraping_dialog is not None:
            self.scraping_dialog.setWindowTitle("Actualización completada")
            self.scraping_dialog.raise_()
            self.scraping_dialog.activateWindow()

    def scraping_dialog_closed(self) -> None:
        self.scraping_dialog = None

    def is_scraping_running(self) -> bool:
        if self.scraping_dialog is None:
            return False
        thread = self.scraping_dialog.scraping_thread
        return bool(thread is not None and thread.isRunning())

    def update_product_counter(self, filtered_count: int | None = None) -> None:
        total = len(self.all_products)
        visible = total if filtered_count is None else filtered_count
        self.product_counter.setText(f"Mostrando {visible} de {total} productos")

    def new_product(self) -> None:
        from gui.product_dialog import ProductDialog

        dialog = ProductDialog(self)
        if dialog.exec():
            self.refresh_catalog()

    def edit_product(self) -> None:
        from gui.product_dialog import ProductDialog

        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Editar", "Seleccione un producto.")
            return
        item = self.table.item(row, 1)
        if item is None:
            return
        product_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(product_id, int):
            return
        product = self.controller.get_product_by_id(product_id)
        if product is None:
            return
        dialog = ProductDialog(self, product)
        if dialog.exec():
            self.refresh_catalog()

    def delete_product(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, self.table.CODE_COLUMN)
        if item is None:
            return
        product_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(product_id, int):
            return
        response = QMessageBox.question(
            self,
            "Confirmar eliminación",
            "¿Desea eliminar este producto?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if response == QMessageBox.StandardButton.Yes:
            self.controller.delete_product(product_id)
            self.refresh_catalog()

    def delete_selected(self) -> None:
        """Elimina el producto o la única categoría seleccionada."""
        row = self.table.currentRow()
        if row >= 0 and not self.table.isRowHidden(row):
            self.delete_product()
            return

        categories = sorted(self.selected_categories, key=str.casefold)
        if len(categories) > 1:
            QMessageBox.warning(
                self,
                "Eliminar categoría",
                "Seleccione una sola categoría para eliminarla.",
            )
            return
        if len(categories) == 1:
            category = categories[0]
            response = QMessageBox.question(
                self,
                "Confirmar eliminación",
                (
                    f"¿Desea eliminar la categoría “{category}” del catálogo?\n\n"
                    "Los productos se conservarán y mantendrán sus demás categorías."
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if response == QMessageBox.StandardButton.Yes:
                self.controller.delete_category(category)
                self.selected_categories.discard(category)
                self.refresh_catalog()
            return

        QMessageBox.warning(
            self,
            "Eliminar",
            "Seleccione un producto o una categoría.",
        )

    def _table_cell_double_clicked(self, row: int, column: int) -> None:
        if column != self.table.IMAGE_COLUMN:
            return
        if row < 0 or row >= len(self.table._rendered_products):
            return
        product = self.table._rendered_products[row]
        if product.id is None:
            return

        from gui.product_image_gallery_dialog import ProductImageGalleryDialog

        dialog = ProductImageGalleryDialog(
            product,
            parent=self,
            service=self.controller._get_service(),
        )
        if dialog.exec():
            self.refresh_catalog()

    @staticmethod
    def _parse_inline_number(value: str) -> float:
        text = str(value or "").strip().replace("S/", "").replace(" ", "")
        if "," in text and "." in text:
            text = text.replace(",", "")
        elif "," in text:
            text = text.replace(",", ".")
        try:
            return max(float(text), 0)
        except ValueError as error:
            raise ValueError("Ingrese un valor numérico válido.") from error

    def _table_item_changed(self, item) -> None:
        if self._table_edit_guard or item is None:
            return
        row = item.row()
        column = item.column()
        if row < 0 or row >= len(self.table._rendered_products):
            return
        if column == self.table.IMAGE_COLUMN:
            return

        product_id_item = self.table.item(row, self.table.CODE_COLUMN)
        if product_id_item is None:
            return
        product_id = product_id_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(product_id, int):
            return

        product = self.controller.get_product_by_id(product_id)
        if product is None:
            return
        original_text = str(item.data(Qt.ItemDataRole.DisplayRole) or "")

        try:
            if column == self.table.CODE_COLUMN:
                product.code = item.text().strip()
            elif column == self.table.NAME_COLUMN:
                product.name = item.text().strip()
            elif column == self.table.DETAIL_COLUMN:
                product.description = item.text().strip()
            elif column == self.table.CATEGORY_COLUMN:
                product.category = item.text().replace("\n", ", ").strip()
            elif column == self.table.PRICE_SAMPLE_COLUMN:
                value = self._parse_inline_number(item.text())
                product.price_sample = value
                product.price = value
            elif column == self.table.PRICE_HUNDRED_COLUMN:
                product.price_hundred = self._parse_inline_number(item.text())
            elif column == self.table.PRICE_THOUSAND_COLUMN:
                product.price_thousand = self._parse_inline_number(item.text())
            elif column == self.table.STOCK_COLUMN:
                if product.color_stock:
                    raise ValueError(
                        "El stock se calcula automáticamente a partir del stock por color."
                    )
                product.stock = max(
                    round(self._parse_inline_number(item.text())),
                    0,
                )
            else:
                return

            self.controller.update_product(product)
        except (sqlite3.Error, ValueError) as error:
            self._table_edit_guard = True
            try:
                item.setText(original_text)
            finally:
                self._table_edit_guard = False
            QMessageBox.warning(
                self,
                "Edición de producto",
                str(error),
            )
            return

        self.refresh_catalog()

    def rename_category_button(self, category: str) -> None:
        value, accepted = QInputDialog.getText(
            self,
            "Editar categoría",
            "Nuevo nombre:",
            text=category,
        )
        if not accepted:
            return
        new_name = value.strip()
        if not new_name:
            return
        try:
            self.controller.rename_category(category, new_name)
        except (sqlite3.Error, ValueError) as error:
            QMessageBox.warning(
                self,
                "Editar categoría",
                str(error),
            )
            return

        if category in self.selected_categories:
            self.selected_categories.discard(category)
            self.selected_categories.add(new_name)
        self.refresh_catalog()

    def import_products(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Importar carga masiva",
            "",
            (
                "Archivos compatibles (*.csv *.xlsx *.xlsm);;"
                "CSV (*.csv);;Excel (*.xlsx *.xlsm)"
            ),
        )
        if not filename:
            return

        from services.product_import import ProductImportService

        try:
            products = ProductImportService.import_products(filename)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Importar carga masiva", str(error))
            return

        from gui.product_import_preview_dialog import ProductImportPreviewDialog

        preview = ProductImportPreviewDialog(
            products,
            current_products=self.all_products,
            parent=self,
        )
        if preview.exec() != preview.DialogCode.Accepted:
            return

        try:
            saved = self.controller.save_products(preview.accepted_products)
        except (sqlite3.Error, ValueError) as error:
            QMessageBox.critical(
                self,
                "Importar carga masiva",
                str(error),
            )
            return

        QMessageBox.information(
            self,
            "Importar carga masiva",
            f"Se procesaron {len(saved)} productos correctamente.",
        )
        self.refresh_catalog()

    def search_products(self, _text: str) -> None:
        self.apply_filters()

    def export_catalog(self) -> None:
        from gui.excel_category_dialog import ExcelCategorySelectionDialog

        products = list(self.all_products)
        if not products:
            QMessageBox.information(
                self,
                "Exportar catálogo",
                "No hay productos disponibles para exportar.",
            )
            return

        categories = {
            category
            for product in products
            for category in self._product_categories(product)
        }
        filtered_products = self._filtered_products()
        filtered_categories = {
            category
            for product in filtered_products
            for category in self._product_categories(product)
        }
        if self.selected_categories:
            initial_selected = set(self.selected_categories)
        elif self.stock_only or self.search_box.text().strip():
            initial_selected = filtered_categories
        else:
            initial_selected = categories

        category_dialog = ExcelCategorySelectionDialog(
            categories,
            products,
            self,
            initial_selected_categories=initial_selected,
            stock_only=self.stock_only,
            on_export=self._export_selected_format,
        )
        category_dialog.exec()

    def export_excel(self) -> None:
        """Compatibilidad para llamadas existentes: abre el selector de formatos."""
        self.export_catalog()

    def _export_selected_format(
        self,
        format_name: str,
        products: list[Product],
    ) -> bool:
        exporters = {
            "excel": (
                "Excel",
                "catalogo.xlsx",
                "Excel (*.xlsx)",
            ),
            "csv": (
                "CSV",
                "catalogo.csv",
                "CSV (*.csv)",
            ),
            "pdf": (
                "PDF",
                "catalogo.pdf",
                "PDF (*.pdf)",
            ),
        }
        export_spec = exporters.get(str(format_name).strip().casefold())
        if export_spec is None:
            raise ValueError("Formato de exportación no válido.")

        normalized_format = str(format_name).strip().casefold()
        label, default_name, file_filter = export_spec
        filename, _ = QFileDialog.getSaveFileName(
            self,
            f"Guardar {label}",
            default_name,
            file_filter,
        )
        if not filename:
            return False

        if normalized_format == "excel":
            from exporters.excel_exporter import ExcelExporter

            ExcelExporter.export(products, filename)
        elif normalized_format == "csv":
            from exporters.csv_exporter import CSVExporter

            CSVExporter.export(products, filename)
        else:
            from exporters.pdf_exporter import PDFExporter

            PDFExporter.export(products, filename)
        return True

    def export_pdf(self) -> None:
        from exporters.pdf_exporter import PDFExporter

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar PDF",
            "catalogo.pdf",
            "PDF (*.pdf)",
        )
        if filename:
            PDFExporter.export(self.controller.get_products(), filename)

    def export_csv(self) -> None:
        from exporters.csv_exporter import CSVExporter

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar CSV",
            "catalogo.csv",
            "CSV (*.csv)",
        )
        if filename:
            CSVExporter.export(self.controller.get_products(), filename)

    def _set_initial_window_geometry(self) -> None:
        initial_width = (
            self.INITIAL_WINDOW_WIDTH + self._category_sidebar_open_width
        )
        self.resize(initial_width, self.INITIAL_WINDOW_HEIGHT)
        self._center_initial_window()

    def _center_initial_window(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available_geometry = screen.availableGeometry()
        frame_geometry = self.frameGeometry()
        frame_geometry.moveCenter(available_geometry.center())
        self.move(frame_geometry.topLeft())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "category_scroll") and hasattr(self, "table"):
            self._sync_category_scrollbar_with_table()

    @staticmethod
    def _wait_for_thread(thread: QThread | None) -> None:
        """Espera a que un worker de GUI termine antes de destruir la ventana."""
        if thread is None or not thread.isRunning():
            return
        thread.requestInterruption()
        thread.quit()
        thread.wait()

    def closeEvent(self, event) -> None:
        if self.scraping_dialog is not None:
            self.scraping_dialog.close()
        if self.history_dialog is not None:
            self.history_dialog.close()
        if self.image_review_dialog is not None:
            self.image_review_dialog.close()
        self.image_review_service.close()

        self._wait_for_thread(self.catalog_load_thread)
        self._wait_for_thread(self.catalog_bootstrap_thread)

        super().closeEvent(event)
