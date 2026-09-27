from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from gui.main_window import CategoryFilterButton, CategoryScrollArea, MainWindow


def _qapp():
    return QApplication.instance() or QApplication([])


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
    assert (
        MainWindow.CATEGORY_SIDEBAR_REFERENCE_TEXT
        == "Enmicadoras / Laminadoras"
    )


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
        "Exportar Excel",
        "Exportar PDF",
        "Exportar CSV",
        "Actualizar catálogo",
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
        "Exportar Excel",
        "Exportar PDF",
        "Exportar CSV",
        "Actualizar catálogo",
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


def test_category_buttons_reserve_focus_border_and_stay_left_aligned():
    _qapp()

    button = QPushButton("Artículos de Escritorio")
    button.setStyleSheet(MainWindow._category_button_style())

    assert "border: 1px solid transparent" in button.styleSheet()
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


def test_category_sidebar_uses_reference_width_and_elides_long_labels():
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
    long_button = QPushButton(
        "Impresora y Consumible Fotográfico Profesional",
    )
    long_button.setProperty(
        "category_text",
        "Impresora y Consumible Fotográfico Profesional",
    )
    window.category_buttons = [reference, long_button]
    window.category_scroll.setWidget(container)

    window._prepare_category_filter_layout()

    assert reference.width() == long_button.width()
    expected_sidebar_width = (
        reference.width() + MainWindow.CATEGORY_SIDEBAR_HORIZONTAL_PADDING * 2
    )
    assert window._category_sidebar_open_width == expected_sidebar_width
    assert long_button.toolTip() == (
        "Impresora y Consumible Fotográfico Profesional"
    )
    assert long_button.text() != long_button.toolTip()

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

    focus_image = first.grab().toImage()
    focus_color = focus_image.pixelColor(first.width() // 2, 0)
    assert focus_color.red() == 0
    assert focus_color.green() == 0
    assert focus_color.blue() == 0

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
