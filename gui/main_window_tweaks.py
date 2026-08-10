from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QSizePolicy


def _configure_toggle_button(cls, button, *texts):
    """Configura filtros con 16 px y ancho fijo para todos sus estados."""
    font = button.font()
    font.setPointSize(16)
    button.setFont(font)
    button.setSizePolicy(
        QSizePolicy.Policy.Fixed,
        QSizePolicy.Policy.Fixed,
    )
    button.setStyleSheet(
        "QPushButton { font-size: 16px; padding: 4px 12px; }\n"
        + cls.ACTIVE_BUTTON_STYLE,
    )

    metrics = QFontMetrics(font)
    bold_font = QFont(font)
    bold_font.setBold(True)
    bold_metrics = QFontMetrics(bold_font)
    required_width = max(
        max(
            metrics.horizontalAdvance(text),
            bold_metrics.horizontalAdvance(text),
        )
        for text in texts
    ) + 24
    button.setFixedWidth(required_width)
    button.setFixedHeight(40)


def _set_toggle_button_width(cls, button, *texts):
    """Mantiene exactamente el mismo ancho al activar o desactivar."""
    font = button.font()
    metrics = QFontMetrics(font)
    bold_font = QFont(font)
    bold_font.setBold(True)
    bold_metrics = QFontMetrics(bold_font)
    required_width = max(
        max(
            metrics.horizontalAdvance(text),
            bold_metrics.horizontalAdvance(text),
        )
        for text in texts
    ) + 24
    button.setFixedWidth(required_width)
    button.setFixedHeight(40)


def _category_button_width(cls, button, text):
    """Calcula el ancho mínimo del texto de categoría a 13 px."""
    font = button.font()
    font.setPointSize(13)
    bold_font = QFont(font)
    bold_font.setBold(True)
    metrics = QFontMetrics(font)
    bold_metrics = QFontMetrics(bold_font)
    return max(
        metrics.horizontalAdvance(text),
        bold_metrics.horizontalAdvance(text),
    ) + 20


def _fit_category_button(cls, button, text):
    """Ajusta cada botón de categoría al texto y conserva el ancho."""
    font = button.font()
    font.setPointSize(13)
    button.setFont(font)
    button.setText(text)
    button.setToolTip(text)
    button.setSizePolicy(
        QSizePolicy.Policy.Fixed,
        QSizePolicy.Policy.Fixed,
    )
    width = cls._category_button_width(button, text)
    button.setFixedWidth(width)
    button.setFixedHeight(30)
    return width


def apply_main_window_tweaks(main_window_class):
    """Aplica los ajustes visuales antes de crear MainWindow."""
    main_window_class.TOGGLE_FONT_SIZE = 16
    main_window_class.TOGGLE_BUTTON_HORIZONTAL_PADDING = 24
    main_window_class.TOGGLE_BUTTON_HEIGHT = 40
    main_window_class.CATEGORY_FONT_SIZE = 13
    main_window_class.CATEGORY_BUTTON_HORIZONTAL_PADDING = 20
    main_window_class.CATEGORY_BUTTON_VERTICAL_PADDING = 4
    main_window_class.CATEGORY_HORIZONTAL_SPACING = 1
    main_window_class.CATEGORY_VERTICAL_SPACING = 1
    main_window_class._configure_toggle_button = classmethod(
        _configure_toggle_button,
    )
    main_window_class._set_toggle_button_width = classmethod(
        _set_toggle_button_width,
    )
    main_window_class._category_button_width = classmethod(
        _category_button_width,
    )
    main_window_class._fit_category_button = classmethod(
        _fit_category_button,
    )
    return main_window_class
