from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
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
    window.table = QWidget()
    window.catalog_bootstrap_blocked_buttons = []
    host = QWidget()
    layout = QVBoxLayout(host)

    MainWindow.create_filter_controls(window, layout)

    filter_layout = layout.itemAt(0).layout()
    assert filter_layout is not None
    top_controls = filter_layout.itemAt(0).layout()
    assert top_controls is not None

    widgets = [
        top_controls.itemAt(index).widget()
        for index in range(top_controls.count())
    ]
    assert widgets[0] is window.category_toggle_button
    assert widgets[1] is window.stock_filter_button
    assert widgets[2] is window.search_box
    assert widgets[3] is window.top_actions_container
    assert window.category_sidebar.isVisible() is False

    action_widgets = [
        window.top_actions_container.layout().itemAt(index).widget()
        for index in range(window.top_actions_container.layout().count())
    ]
    assert [widget.text() for widget in action_widgets] == [
        "Nuevo",
        "Editar",
        "Eliminar",
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
        "Nuevo",
        "Editar",
        "Eliminar",
        "Exportar Excel",
        "Exportar PDF",
        "Exportar CSV",
        "Actualizar catálogo",
        "Historial",
    ]
    assert len(window.catalog_bootstrap_blocked_buttons) == 4
    assert all(
        "border: 1px solid #cbddea" in button.styleSheet()
        for button in [
            layout.itemAt(index).widget()
            for index in range(layout.count())
        ]
        if layout.itemAt(index).widget() is not None
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
    button = QPushButton("Todos")
    button.setProperty("category_text", "Todos")
    window.category_buttons = [button]
    window.category_scroll.setWidget(container)
    window._category_sidebar_closed_width = window.category_toggle_button.width()

    window._prepare_category_filter_layout()

    assert window.category_layout.count() == 1
    assert window.category_layout.itemAt(0).widget() is button
    assert window._category_sidebar_open_width >= button.width()

    window.category_scroll.deleteLater()
    window.category_sidebar.deleteLater()


def test_category_filter_toggle_shows_sidebar_and_gives_table_space_back():
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
    window.category_sidebar.resize(100, 300)
    window._category_sidebar_closed_width = window.category_toggle_button.width()
    window._category_sidebar_open_width = 220

    window.toggle_categories_visibility(True)
    assert window.category_scroll.isVisible()
    assert window.category_sidebar.width() == 220
    assert window.category_toggle_button.text() == "Ocultar Categorías"

    window.toggle_categories_visibility(False)
    assert not window.category_scroll.isVisible()
    assert not window.category_sidebar.isVisible()
    assert window.category_sidebar.width() == 0
    assert window.category_toggle_button.text() == "Filtrar Categorías"

    window.category_scroll.deleteLater()
    window.category_sidebar.deleteLater()
    window.category_toggle_button.deleteLater()
