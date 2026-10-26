from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from gui.main_window import (
    CategoryFilterButton,
    CategoryScrollArea,
    MainWindow,
    SearchLineEdit,
)
from gui.product_table import ProductTable
from models.product import Product
from services.scraping.category_name_normalizer import display_category_name


def _qapp():
    return QApplication.instance() or QApplication([])


class _Controller:
    def get_products(self):
        return []


def test_main_window_visual_metrics_keep_compact_hierarchy():
    assert MainWindow.SEARCH_FONT_SIZE == 16
    assert MainWindow.SEARCH_HEIGHT == 38
    assert MainWindow.COUNTER_FONT_SIZE == 13
    assert MainWindow.ACTION_BUTTON_FONT_SIZE == 13
    assert MainWindow.ACTION_BUTTON_HEIGHT == 34
    assert MainWindow.CATEGORY_FONT_SIZE == 13
    assert MainWindow.ACTION_BUTTON_HORIZONTAL_PADDING == 4
    assert MainWindow.TOGGLE_BUTTON_HORIZONTAL_PADDING == 4
    assert MainWindow.CATEGORY_BUTTON_HORIZONTAL_PADDING == 4
    assert MainWindow.CATEGORY_BUTTON_HEIGHT == 28
    assert MainWindow.TOP_CONTROLS_SPACING == 4
    assert MainWindow.CATEGORY_SIDEBAR_SPACING == 4
    assert MainWindow.CATEGORY_SIDEBAR_HORIZONTAL_PADDING == 4
    assert MainWindow.INITIAL_WINDOW_WIDTH == 1200
    assert MainWindow.INITIAL_WINDOW_HEIGHT == 700


def test_filter_toggle_width_allows_normal_and_bold_text():
    _qapp()

    button = QPushButton("Filtrar Categorías")
    MainWindow._configure_toggle_button(
        button,
        "Filtrar Categorías",
        "Ocultar Categorías",
    )

    normal_font = button.font()
    bold_font = QFont(normal_font)
    bold_font.setBold(True)
    metrics = QFontMetrics(normal_font)
    bold_metrics = QFontMetrics(bold_font)
    widest_text = max(
        metrics.horizontalAdvance("Filtrar Categorías"),
        metrics.horizontalAdvance("Ocultar Categorías"),
        bold_metrics.horizontalAdvance("Filtrar Categorías"),
        bold_metrics.horizontalAdvance("Ocultar Categorías"),
    )

    assert MainWindow.TOGGLE_BUTTON_HORIZONTAL_PADDING == 4
    assert button.width() >= widest_text + 10
    assert "border: 1px solid #cbddea" in button.styleSheet()

    button.deleteLater()


def test_hiding_categories_enables_even_table_column_distribution():
    _qapp()

    class _DistributionSpy:
        def __init__(self):
            self.enabled = False

        def set_even_column_distribution(self, enabled):
            self.enabled = enabled

    window = MainWindow.__new__(MainWindow)
    window.category_toggle_button = QPushButton()
    window.category_toggle_button.setCheckable(True)
    window._category_sidebar_open_width = 120
    window.category_sidebar = QWidget()
    window.category_scroll = QWidget()
    window.table = _DistributionSpy()
    window.categories_visible = True

    MainWindow.toggle_categories_visibility(window, False)
    assert window.categories_visible is False
    assert window.table.enabled is True

    MainWindow.toggle_categories_visibility(window, True)
    assert window.categories_visible is True
    assert window.table.enabled is False

    window.category_toggle_button.deleteLater()
    window.category_sidebar.deleteLater()
    window.category_scroll.deleteLater()


def test_search_clear_icon_remains_visible_and_clears_the_field():
    _qapp()
    search = SearchLineEdit()
    search.resize(320, MainWindow.SEARCH_HEIGHT)
    search.show()
    QApplication.processEvents()

    assert search.clear_button.isVisible()
    assert not search.clear_button.icon().isNull()

    search.setText("producto")
    QApplication.processEvents()
    assert search.clear_button.isVisible()

    search.clear_button.click()
    QApplication.processEvents()
    assert search.text() == ""
    assert search.clear_button.isVisible()
    search.close()


def test_top_controls_keep_category_toggle_next_to_stock_filter_and_search():
    _qapp()

    window = MainWindow.__new__(MainWindow)
    window.catalog_bootstrap_blocked_buttons = []
    window.search_box = QLineEdit()
    window.table = QTableWidget()
    window.catalog_bootstrap_blocked_buttons = []
    host = QWidget()
    layout = QVBoxLayout(host)

    MainWindow.create_filter_controls(window, layout)

    filter_layout = layout.itemAt(0).layout()
    assert filter_layout is not None
    top_controls = filter_layout.itemAt(0).layout()
    assert isinstance(top_controls, QGridLayout)

    assert top_controls.itemAtPosition(0, 0).widget() is (
        window.category_toggle_button
    )
    assert top_controls.itemAtPosition(0, 1).widget() is window.stock_filter_button
    assert top_controls.itemAtPosition(0, 2).widget() is window.search_box
    assert top_controls.itemAtPosition(0, 3).widget() is (
        window.top_actions_container
    )
    assert window.category_sidebar.isVisible() is False
    assert not hasattr(window, "category_sidebar_placeholder")
    assert (
        window.category_scroll.verticalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
    assert (
        window.category_scroll.verticalScrollBar().singleStep()
        == window.table.verticalScrollBar().singleStep()
    )
    assert window.search_box.minimumWidth() == 0
    assert window.top_actions_container.sizePolicy().horizontalPolicy() == (
        window.top_actions_container.sizePolicy().horizontalPolicy().Fixed
    )
    action_layout = window.top_actions_container.layout()
    assert action_layout is not None
    expected_action_width = (
        sum(
            action_layout.itemAt(index).widget().width()
            for index in range(action_layout.count())
            if action_layout.itemAt(index).widget() is not None
        )
        + max(0, action_layout.count() - 1) * MainWindow.TOP_CONTROLS_SPACING
    )
    assert window.top_actions_container.width() == expected_action_width

    action_widgets = [
        window.top_actions_container.layout().itemAt(index).widget()
        for index in range(window.top_actions_container.layout().count())
    ]
    assert [widget.text() for widget in action_widgets] == [
        "Imágenes (0)",
        "Exportar",
        "Importar",
        "Nuevo",
        "Editar",
        "Eliminar",
        "Actualizar Catálogo",
        "Historial",
    ]

    window.search_box.deleteLater()
    window.top_actions_container.deleteLater()
    window.category_sidebar.deleteLater()
    window.table.deleteLater()
    host.deleteLater()


def test_action_buttons_are_grouped_for_top_right_layout():
    _qapp()

    window = MainWindow.__new__(MainWindow)
    window.catalog_bootstrap_blocked_buttons = []
    host = QWidget()
    layout = QHBoxLayout(host)

    MainWindow._add_action_buttons(window, layout)

    labels = [
        layout.itemAt(index).widget().text()
        for index in range(layout.count())
        if layout.itemAt(index).widget() is not None
    ]

    assert labels == [
        "Imágenes (0)",
        "Exportar",
        "Importar",
        "Nuevo",
        "Editar",
        "Eliminar",
        "Actualizar Catálogo",
        "Historial",
    ]
    assert len(window.catalog_bootstrap_blocked_buttons) == 1
    assert all(
        "border: 1px solid #cbddea" in button.styleSheet()
        for button in [
            layout.itemAt(index).widget()
            for index in range(layout.count())
            if layout.itemAt(index).widget() is not None
        ]
    )

    host.deleteLater()


def test_image_review_button_keeps_height_and_uses_shared_active_style():
    _qapp()

    class _ReviewService:
        def available(self):
            return [
                {
                    "id": "review-1",
                    "kind": "replacement",
                    "code": "FB-100",
                },
            ]

    class _TableSpy:
        def set_gallery_overrides(self, overrides):
            self.overrides = overrides

    window = MainWindow.__new__(MainWindow)
    button = QPushButton("Imágenes (0)")
    button.setCheckable(True)
    MainWindow._configure_action_button(button)
    button.setFixedWidth(115)
    initial_height = button.height()
    window.image_review_button = button
    window.image_review_service = _ReviewService()
    window.table = _TableSpy()

    MainWindow._refresh_image_review_state(window)

    assert button.text() == "Imágenes (1)"
    assert button.isChecked()
    assert button.height() == initial_height == MainWindow.ACTION_BUTTON_HEIGHT
    assert button.minimumHeight() == button.maximumHeight()
    assert "QPushButton:checked" in button.styleSheet()
    assert "background-color: #d8edf7" in button.styleSheet()
    assert "#fff7d6" not in button.styleSheet()
    button.deleteLater()


def test_category_buttons_use_bold_font_only_when_checked():
    _qapp()
    button = CategoryFilterButton("Oficina")
    button.setCheckable(True)

    assert not button.font().bold()
    button.setChecked(True)
    assert button.font().bold()
    button.setChecked(False)
    assert not button.font().bold()
    button.deleteLater()


def test_apply_filters_resets_product_scrollbar_to_top():
    _qapp()

    class _FilterTable:
        def __init__(self):
            self.scrollbar = QScrollBar()
            self.scrollbar.setRange(0, 100)
            self.scrollbar.setValue(75)
            self.visible_products = []
            self.search_text = ""

        def show_only_products(self, products):
            self.visible_products = list(products)

        def set_search_text(self, text):
            self.search_text = text

        def verticalScrollBar(self):
            return self.scrollbar

    window = MainWindow.__new__(MainWindow)
    window.all_products = [
        Product(code="FB-100", name="Producto de prueba", category="Oficina"),
    ]
    window.search_box = QLineEdit()
    window.selected_categories = set()
    window.stock_only = False
    window.table = _FilterTable()
    window.product_counter = QLabel()

    window.search_box.setText("FB-100")
    MainWindow.apply_filters(window)
    assert window.table.scrollbar.value() == 0
    assert window.table.search_text == "FB-100"

    window.table.scrollbar.setValue(85)
    window.search_box.setText("sin coincidencias")
    MainWindow.apply_filters(window)
    assert window.table.scrollbar.value() == 0
    assert window.table.visible_products == []

    window.table.scrollbar.deleteLater()
    window.product_counter.deleteLater()


def test_category_buttons_reserve_focus_border_and_stay_left_aligned():
    _qapp()

    button = QPushButton("Artículos de Escritorio")
    button.setStyleSheet(MainWindow._category_button_style())

    assert "border: none" in button.styleSheet()
    assert "padding: 0px 4px" in button.styleSheet()
    assert "text-align: left" in button.styleSheet()
    assert "background: transparent" in button.styleSheet()

    button.deleteLater()


def test_category_button_width_matches_real_horizontal_padding():
    _qapp()

    button = QPushButton()
    text = "Enmicadoras / Laminadoras"
    width = MainWindow._fit_category_button(button, text)

    font = button.font()
    bold_font = QFont(font)
    bold_font.setBold(True)
    bold_width = QFontMetrics(bold_font).horizontalAdvance(text)

    assert MainWindow.CATEGORY_BUTTON_HORIZONTAL_PADDING == 4
    assert width >= bold_width + 10
    assert button.width() == width

    button.deleteLater()


def test_all_categories_button_uses_explicit_plural_label():
    _qapp()

    button = QPushButton("Todas las categorías")
    button.setProperty("category_text", "Todas las categorías")

    assert button.text() == "Todas las categorías"
    assert button.property("category_text") == "Todas las categorías"

    button.deleteLater()


def test_category_sidebar_keeps_fixed_reference_width_and_full_short_labels():
    _qapp()

    window = MainWindow.__new__(MainWindow)
    window.categories_visible = False
    window.category_sidebar = QWidget()
    window.category_scroll = QScrollArea()
    container = QWidget()
    window.category_layout = QVBoxLayout(container)
    reference = QPushButton("Enmicadoras / Laminadoras")
    reference.setProperty("category_text", "Enmicadoras / Laminadoras")
    full_label = "Artículos de Oficina"
    full_button = QPushButton(full_label)
    full_button.setProperty("category_text", full_label)
    long_label = "Impresora y Consumible Fotográfico Profesional"
    long_button = QPushButton(long_label)
    long_button.setProperty("category_text", long_label)
    window.category_buttons = [reference, full_button, long_button]
    window.category_scroll.setWidget(container)

    window._prepare_category_filter_layout()

    assert reference.width() == full_button.width() == long_button.width()
    expected_sidebar_width = (
        reference.width() + MainWindow.CATEGORY_SIDEBAR_HORIZONTAL_PADDING * 2
    )
    assert window._category_sidebar_open_width == expected_sidebar_width
    assert reference.text() == MainWindow.CATEGORY_SIDEBAR_REFERENCE_TEXT
    assert full_button.text() == full_label
    assert long_button.toolTip() == long_label
    assert long_button.text() != long_label

    window.category_scroll.deleteLater()
    window.category_sidebar.deleteLater()


def test_category_sidebar_reserves_scrollbar_width_when_visible():
    _qapp()

    window = MainWindow.__new__(MainWindow)
    window.categories_visible = True
    window.category_sidebar = QWidget()
    window.category_scroll = CategoryScrollArea()
    window.category_scroll.setWidgetResizable(True)
    container = QWidget()
    container.setMinimumHeight(1200)
    window.category_scroll.setWidget(container)
    window.category_sidebar.resize(240, 220)
    window.category_sidebar_layout = QVBoxLayout(window.category_sidebar)
    window.category_sidebar_layout.setContentsMargins(4, 0, 4, 0)
    window.category_sidebar_layout.addWidget(window.category_scroll)

    window._category_sidebar_button_width = 190
    window._category_sidebar_open_width = 198
    window.category_sidebar.show()
    window.category_scroll.show()
    _qapp().processEvents()

    scrollbar = window.category_scroll.verticalScrollBar()
    _qapp().processEvents()
    assert scrollbar.maximum() > 0

    MainWindow._sync_category_sidebar_width_with_scrollbar(
        window,
        maximum=scrollbar.maximum(),
    )

    expected_width = (
        window._category_sidebar_button_width
        + (2 * MainWindow.CATEGORY_SIDEBAR_HORIZONTAL_PADDING)
        + scrollbar.sizeHint().width()
    )
    assert window._category_sidebar_open_width == expected_width
    assert window.category_sidebar.width() == expected_width

    window.category_scroll.deleteLater()
    window.category_sidebar.deleteLater()


def test_category_scrollbar_mirrors_product_table_scrollbar():
    _qapp()

    window = MainWindow.__new__(MainWindow)
    window.search_box = QLineEdit()
    window.table = QTableWidget()
    window.catalog_bootstrap_blocked_buttons = []
    host = QWidget()
    layout = QVBoxLayout(host)

    MainWindow.create_filter_controls(window, layout)

    table_scrollbar = window.table.verticalScrollBar()
    category_scrollbar = window.category_scroll.verticalScrollBar()

    assert category_scrollbar.singleStep() == table_scrollbar.singleStep()
    assert category_scrollbar.font() == table_scrollbar.font()
    assert type(category_scrollbar.style()) is type(table_scrollbar.style())
    assert category_scrollbar.sizeHint().width() == table_scrollbar.sizeHint().width()
    assert (
        window.category_scroll.verticalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
    assert (
        window.category_scroll.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert isinstance(window.category_scroll, CategoryScrollArea)
    assert (
        window.category_scroll.viewport().styleSheet()
        == "background-color: #ffffff;"
    )
    assert (
        window.category_sidebar.styleSheet()
        == "#category_sidebar { background-color: #ffffff; }"
    )
    assert (
        window.category_container.styleSheet()
        == "#category_container { background-color: #ffffff; }"
    )

    window.category_scroll.deleteLater()
    window.category_sidebar.deleteLater()
    window.table.deleteLater()
    window.search_box.deleteLater()
    host.deleteLater()


def test_category_buttons_support_arrow_navigation_and_focus_frame():
    _qapp()

    host = QWidget()
    layout = QVBoxLayout(host)
    buttons = [
        CategoryFilterButton("Todas las categorías"),
        CategoryFilterButton("Artículos de Escritorio"),
        CategoryFilterButton("Enmicadoras / Laminadoras"),
    ]
    for button in buttons:
        button.setStyleSheet(MainWindow._category_button_style())
        layout.addWidget(button)

    host.show()
    _qapp().processEvents()

    first = buttons[0]
    second = buttons[1]
    third = buttons[2]
    first_width = first.width()
    second_width = second.width()
    third_width = third.width()

    category_style = MainWindow._category_button_style()
    assert "border: none" in category_style
    assert "padding: 0px 4px" in category_style
    assert "text-align: left" in category_style
    assert "QPushButton:focus" not in category_style
    assert "border: 1px solid #000000" not in category_style
    assert first.focusPolicy() == Qt.FocusPolicy.StrongFocus

    first.setFocus()
    _qapp().processEvents()
    assert first.hasFocus()
    focused_width = first.width()
    assert focused_width == first_width

    focus_frame = first.findChild(QFrame, "category_focus_frame")
    assert focus_frame is not None
    assert focus_frame.isVisible()
    assert focus_frame.geometry() == first.rect().adjusted(1, 1, -2, -2)
    assert focus_frame.testAttribute(
        Qt.WidgetAttribute.WA_TransparentForMouseEvents,
    )
    assert "border: 1px solid #000000" in focus_frame.styleSheet()

    first.clearFocus()
    _qapp().processEvents()
    assert not focus_frame.isVisible()

    down_event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Down,
        Qt.KeyboardModifier.NoModifier,
    )
    first.keyPressEvent(down_event)
    assert second.hasFocus()

    down_event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Down,
        Qt.KeyboardModifier.NoModifier,
    )
    second.keyPressEvent(down_event)
    assert third.hasFocus()

    up_event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Up,
        Qt.KeyboardModifier.NoModifier,
    )
    third.keyPressEvent(up_event)
    assert second.hasFocus()

    assert first.width() == first_width
    assert second.width() == second_width
    assert third.width() == third_width
    assert first.text() == "Todas las categorías"
    assert second.text() == "Artículos de Escritorio"
    assert third.text() == "Enmicadoras / Laminadoras"

    first.deleteLater()
    second.deleteLater()
    third.deleteLater()
    host.deleteLater()


def test_category_keyboard_navigation_never_scrolls_horizontally():
    _qapp()

    scroll = CategoryScrollArea()
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(1)
    buttons = []

    for index in range(12):
        button = CategoryFilterButton(f"Categoría {index:02d}")
        button.setStyleSheet(MainWindow._category_button_style())
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        button.setFixedWidth(210)
        button.setFixedHeight(MainWindow.CATEGORY_BUTTON_HEIGHT)
        layout.addWidget(button)
        buttons.append(button)

    content.adjustSize()
    scroll.setWidgetResizable(False)
    scroll.setWidget(content)
    scroll.resize(230, 100)
    scroll.show()
    _qapp().processEvents()

    assert scroll.verticalScrollBar().isVisible()

    first_x = buttons[0].x()
    first = buttons[0]
    first.setFocus()
    _qapp().processEvents()

    for index in range(1, 10):
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Down,
            Qt.KeyboardModifier.NoModifier,
        )
        buttons[index - 1].keyPressEvent(event)
        assert buttons[index].hasFocus()
        assert buttons[index].x() == first_x
        assert scroll.horizontalScrollBar().value() == 0

        top = buttons[index].mapTo(scroll.viewport(), buttons[index].rect().topLeft()).y()
        bottom = buttons[index].mapTo(
            scroll.viewport(),
            buttons[index].rect().bottomLeft(),
        ).y()
        margin = CategoryScrollArea.FOCUS_FRAME_MARGIN
        assert top >= margin
        assert bottom <= scroll.viewport().height() - margin

    assert scroll.verticalScrollBar().value() > 0

    scroll.deleteLater()
    content.deleteLater()

def test_category_scroll_area_rejects_horizontal_content_drift():
    _qapp()

    scroll = CategoryScrollArea()
    content = QWidget()
    content.setMinimumWidth(600)
    content.setMinimumHeight(1200)
    scroll.setWidgetResizable(False)
    scroll.setWidget(content)
    scroll.resize(220, 300)
    scroll.show()
    _qapp().processEvents()

    horizontal_bar = scroll.horizontalScrollBar()
    horizontal_bar.setValue(0)
    scroll.scrollContentsBy(25, 30)

    assert horizontal_bar.value() == 0
    assert scroll.verticalScrollBar().value() >= 0

    scroll.deleteLater()
    content.deleteLater()


def test_category_toggle_width_matches_sidebar_width_while_sidebar_is_hidden():
    _qapp()

    window = MainWindow.__new__(MainWindow)
    window.categories_visible = False
    window.category_sidebar = QWidget()
    window.category_scroll = QScrollArea()
    container = QWidget()
    window.category_layout = QVBoxLayout(container)
    reference = QPushButton("Enmicadoras / Laminadoras")
    reference.setProperty(
        "category_text",
        "Enmicadoras / Laminadoras",
    )
    window.category_buttons = [reference]
    window.category_toggle_button = QPushButton("Filtrar Categorías")
    window.category_toggle_button.setCheckable(True)
    MainWindow._configure_toggle_button(
        window.category_toggle_button,
        "Filtrar Categorías",
        "Ocultar Categorías",
    )
    window.category_scroll.setWidget(container)
    window.category_sidebar.setVisible(False)

    window._prepare_category_filter_layout()

    assert not window.category_sidebar.isVisible()
    assert (
        window.category_toggle_button.width()
        == window._category_sidebar_open_width
    )

    window.category_scroll.deleteLater()
    window.category_sidebar.deleteLater()
    window.category_toggle_button.deleteLater()


def test_category_filter_layout_is_vertical_and_prepared_while_closed():
    _qapp()

    window = MainWindow.__new__(MainWindow)
    window.categories_visible = False
    window.category_sidebar = QWidget()
    window.category_sidebar.resize(120, 400)
    window.category_toggle_button = QPushButton("Filtrar Categorías")
    MainWindow._configure_toggle_button(
        window.category_toggle_button,
        "Filtrar Categorías",
        "Ocultar Categorías",
    )
    window.category_scroll = QScrollArea()
    window.category_scroll.setWidgetResizable(True)
    window.category_scroll.resize(120, 400)
    container = QWidget()
    window.category_layout = QVBoxLayout(container)
    window.category_layout.setContentsMargins(0, 0, 0, 0)
    button = QPushButton("Todas las categorías")
    button.setProperty("category_text", "Todas las categorías")
    window.category_buttons = [button]
    window.category_scroll.setWidget(container)
    window._category_sidebar_closed_width = window.category_toggle_button.width()

    window._prepare_category_filter_layout()

    assert window.category_layout.count() == 1
    assert window.category_layout.itemAt(0).widget() is button
    assert window._category_sidebar_open_width >= button.width()

    window.category_scroll.deleteLater()
    window.category_sidebar.deleteLater()


def test_category_filter_toggle_keeps_sidebar_hidden_until_activated():
    _qapp()

    window = MainWindow.__new__(MainWindow)
    window.categories_visible = False
    window.category_toggle_button = QPushButton()
    MainWindow._configure_toggle_button(
        window.category_toggle_button,
        "Filtrar Categorías",
        "Ocultar Categorías",
    )
    window.category_scroll = QScrollArea()
    window.category_sidebar = QWidget()
    window.category_scroll.setParent(window.category_sidebar)
    window.category_sidebar.resize(100, 300)
    window._category_sidebar_open_width = 220
    window.category_toggle_button.setFixedWidth(220)
    window.category_sidebar.setVisible(False)
    window.category_scroll.setVisible(False)

    assert not window.category_sidebar.isVisible()
    assert window.category_toggle_button.width() == 220

    window.toggle_categories_visibility(True)
    assert window.category_scroll.isVisible()
    assert window.category_sidebar.isVisible()
    assert window.category_sidebar.width() == 220
    assert window.category_toggle_button.width() == 220
    assert window.category_toggle_button.text() == "Ocultar Categorías"

    window.toggle_categories_visibility(False)
    assert not window.category_scroll.isVisible()
    assert not window.category_sidebar.isVisible()
    assert window.category_toggle_button.width() == 220
    assert window.category_toggle_button.text() == "Filtrar Categorías"

    window.category_scroll.deleteLater()
    window.category_sidebar.deleteLater()
    window.category_toggle_button.deleteLater()


def test_main_window_initial_geometry_includes_hidden_sidebar_width():
    _qapp()

    window = QMainWindow()
    window.INITIAL_WINDOW_WIDTH = 1200
    window.INITIAL_WINDOW_HEIGHT = 700
    window._category_sidebar_open_width = 220
    window._center_initial_window = (
        lambda: MainWindow._center_initial_window(window)
    )

    MainWindow._set_initial_window_geometry(window)

    screen = QApplication.primaryScreen()
    assert screen is not None
    available = screen.availableGeometry()
    assert window.width() == 1420
    assert window.height() == 700
    assert window.frameGeometry().center() == available.center()

    window.deleteLater()


def test_main_window_starts_with_categories_active_and_expected_geometry():
    _qapp()

    window = MainWindow.__new__(MainWindow)
    window.categories_visible = False
    window._category_sidebar_open_width = 220
    window.INITIAL_WINDOW_WIDTH = 1200
    window.INITIAL_WINDOW_HEIGHT = 700
    window.category_toggle_button = QPushButton("Filtrar Categorías")
    window.category_toggle_button.setCheckable(True)
    MainWindow._configure_toggle_button(
        window.category_toggle_button,
        "Filtrar Categorías",
        "Ocultar Categorías",
    )
    window.category_sidebar = QWidget()
    window.category_scroll = QScrollArea()
    window.category_sidebar.setVisible(False)
    window.category_scroll.setVisible(False)

    MainWindow.toggle_categories_visibility(window, True)

    assert window.categories_visible is True
    assert window.category_sidebar.isVisible() is True
    assert window.category_scroll.isVisible() is True
    assert window.category_toggle_button.text() == "Ocultar Categorías"
    assert window.category_toggle_button.width() == 220
    assert window.category_sidebar.width() == 220
    assert window.category_toggle_button.isChecked() is True

    window.toggle_categories_visibility(False)
    assert window.categories_visible is False
    assert window.category_toggle_button.isChecked() is False
    assert window.category_toggle_button.text() == "Filtrar Categorías"
    assert not window.category_sidebar.isVisible()
    assert not window.category_scroll.isVisible()

    window.category_scroll.deleteLater()
    window.category_sidebar.deleteLater()
    window.category_toggle_button.deleteLater()

def test_main_window_exposes_edit_between_new_and_delete():
    _qapp()
    window = MainWindow.__new__(MainWindow)
    window.catalog_bootstrap_blocked_buttons = []
    host = QWidget()
    layout = QHBoxLayout(host)
    MainWindow._add_action_buttons(window, layout)

    labels = [
        layout.itemAt(index).widget().text()
        for index in range(layout.count())
        if layout.itemAt(index).widget() is not None
    ]

    assert "Importar" in labels
    assert labels.index("Editar") == labels.index("Nuevo") + 1
    assert labels.index("Eliminar") == labels.index("Editar") + 1

    host.deleteLater()



def test_inline_stock_by_color_edit_updates_color_name_and_total():
    _qapp()
    table = ProductTable(_Controller())
    product = Product(
        code="FB-6002",
        name="Producto",
        stock=15,
        color_stock={"Rojo": 10, "Azul": 5},
    )

    MainWindow._update_product_from_cell(
        product,
        table.STOCK_COLUMN,
        "Fucsia: 11\nAzul: 6",
        table,
    )

    assert product.color_stock == {"Fucsia": 11, "Azul": 6}
    assert product.stock == 17
    old_background, old_indicator = ProductTable._stock_color_style("Rojo")
    new_background, new_indicator = ProductTable._stock_color_style("Fucsia")
    assert (new_background, new_indicator) != (old_background, old_indicator)
    table.close()


def test_inline_stock_by_color_edit_rejects_malformed_rows():
    _qapp()
    table = ProductTable(_Controller())
    product = Product(
        code="FB-6003",
        name="Producto",
        stock=10,
        color_stock={"Rojo": 10},
    )

    try:
        MainWindow._update_product_from_cell(
            product,
            table.STOCK_COLUMN,
            "Rojo sin cantidad",
            table,
        )
    except ValueError as error:
        assert "Color: cantidad" in str(error)
    else:
        raise AssertionError("El stock por color mal formado debería rechazarse")
    table.close()


def test_rebuild_category_filters_preserves_full_category_names():
    _qapp()
    window = MainWindow.__new__(MainWindow)
    window.all_products = [
        Product(
            code="FB-101",
            name="Producto oficina",
            category="Artículos de Oficina",
        ),
        Product(
            code="FB-102",
            name="Producto escritorio",
            category="Artículos de Escritorio",
        ),
    ]
    window.selected_categories = set()
    container = QWidget()
    window.category_container = container
    window.category_layout = QVBoxLayout(container)
    window.category_scroll = QScrollArea()
    window.category_scroll.setWidget(container)
    window.categories_visible = False
    window.all_categories_button = CategoryFilterButton("Todas las categorías")
    window.all_categories_button.setCheckable(True)
    window.category_buttons = [window.all_categories_button]

    window.rebuild_category_filters()

    names = {
        str(button.property("category_text")): button.text()
        for button in window.category_buttons
        if button is not window.all_categories_button
    }
    assert names == {
        "Artículos de Escritorio": "Artículos de Escritorio",
        "Artículos de Oficina": "Artículos de Oficina",
    }
    window.category_scroll.deleteLater()


def test_display_category_names_remove_redundant_articulos_de_prefix():
    assert display_category_name("Artículos de Escritorio") == "Escritorio"
    assert display_category_name("Artículos de Oficina") == "Oficina"
    assert display_category_name("Artículos Personales") == "Artículos Personales"


def test_category_filter_button_can_draw_right_aligned_quantity():
    _qapp()
    button = CategoryFilterButton("Artículos de Escritorio")
    button.setProperty("category_text", "Artículos de Escritorio")
    button.setProperty("category_display_text", "Artículos de Escritorio")
    button.setProperty("category_count", 523)
    button.setStyleSheet(MainWindow._category_button_style())
    button.resize(220, MainWindow.CATEGORY_BUTTON_HEIGHT)
    button.show()
    QApplication.processEvents()

    assert button.property("category_count") == 523
    assert not button.grab().isNull()
    button.close()


def test_category_sidebar_reserves_width_for_right_aligned_counts():
    _qapp()
    window = MainWindow.__new__(MainWindow)
    window.categories_visible = False
    window.category_scroll = QScrollArea()
    container = QWidget()
    window.category_layout = QVBoxLayout(container)
    button = CategoryFilterButton("Artículos de Escritorio")
    button.setProperty("category_text", "Artículos de Escritorio")
    button.setProperty("category_display_text", "Artículos de Escritorio")
    button.setProperty("category_count", 523)
    window.category_buttons = [button]
    window.category_scroll.setWidget(container)

    window._prepare_category_filter_layout()

    assert window._category_sidebar_button_width >= (
        QFontMetrics(button.font()).horizontalAdvance("Artículos de Escritorio")
        + (2 * MainWindow.CATEGORY_BUTTON_HORIZONTAL_PADDING)
    )
    assert button.width() == window._category_sidebar_button_width
    assert button.text() == "Artículos de Escritorio"
    window.category_scroll.deleteLater()
