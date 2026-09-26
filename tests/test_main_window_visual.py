from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
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

    button.deleteLater()


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

    host.deleteLater()


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

def test_category_reflow_releases_running_guard():
    _qapp()

    from PySide6.QtWidgets import QScrollArea, QVBoxLayout

    window = MainWindow.__new__(MainWindow)
    window._category_reflow_running = False
    window._category_last_viewport_width = 0
    window.category_scroll = QScrollArea()
    window.category_scroll.resize(400, 80)
    container = QWidget()
    window.category_layout = QVBoxLayout(container)
    button = QPushButton("Todos")
    button.setProperty("category_text", "Todos")
    window.category_buttons = [button]
    window.category_scroll.setWidget(container)

    window._reflow_category_buttons()

    assert window._category_reflow_running is False

    window.category_scroll.deleteLater()

def test_hiding_category_filter_invalidates_layout_width_cache():
    _qapp()

    window = MainWindow.__new__(MainWindow)
    window.categories_visible = True
    window._category_last_viewport_width = 800
    window.category_toggle_button = QPushButton()
    window.category_scroll = QScrollArea()

    window.toggle_categories_visibility(False)

    assert window._category_last_viewport_width == 0

    window.category_scroll.deleteLater()
    window.category_toggle_button.deleteLater()
