from gui.main_window import MainWindow


def test_main_window_visual_metrics_keep_compact_hierarchy():
    assert MainWindow.SEARCH_FONT_SIZE == 16
    assert MainWindow.SEARCH_HEIGHT == 38
    assert MainWindow.COUNTER_FONT_SIZE == 13
    assert MainWindow.ACTION_BUTTON_FONT_SIZE == 13
    assert MainWindow.ACTION_BUTTON_HEIGHT == 34
    assert MainWindow.CATEGORY_FONT_SIZE == 13
    assert MainWindow.CATEGORY_BUTTON_HORIZONTAL_PADDING == 8
    assert MainWindow.CATEGORY_BUTTON_HEIGHT == 28
