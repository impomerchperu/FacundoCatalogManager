from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics
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

from gui.main_window import MainWindow


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


def test_category_buttons_are_borderless_and_left_aligned():
    _qapp()

    button = QPushButton("Artículos de Escritorio")
    button.setStyleSheet(MainWindow._category_button_style())

    assert "border: none" in button.styleSheet()
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
    window.category_scroll.deleteLater()
    window.category_sidebar.deleteLater()
    window.category_toggle_button.deleteLater()
