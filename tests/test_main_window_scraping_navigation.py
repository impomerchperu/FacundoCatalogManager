from types import SimpleNamespace

from gui.main_window import MainWindow


def test_open_scraping_brings_existing_running_dialog_to_front():
    calls = []

    class Thread:
        def isRunning(self):
            return True

    dialog = SimpleNamespace(
        scraping_thread=Thread(),
        showNormal=lambda: calls.append("showNormal"),
        raise_=lambda: calls.append("raise"),
        activateWindow=lambda: calls.append("activate"),
    )
    window = MainWindow.__new__(MainWindow)
    window.scraping_dialog = dialog

    MainWindow.open_scraping(window)

    assert calls == ["showNormal", "raise", "activate"]


def test_show_catalog_after_scraping_refreshes_only_when_pending():
    calls = []
    dialog = SimpleNamespace(
        hide=lambda: calls.append("hide"),
    )
    window = SimpleNamespace(
        scraping_refresh_pending=True,
        scraping_dialog=dialog,
        catalog_button=SimpleNamespace(setText=lambda text: calls.append(text)),
        refresh_catalog=lambda: calls.append("refresh"),
        raise_=lambda: calls.append("raise"),
        activateWindow=lambda: calls.append("activate"),
        table=SimpleNamespace(setFocus=lambda: calls.append("focus")),
    )

    MainWindow._show_catalog_after_scraping(window)

    assert calls == [
        "refresh",
        "Actualizar catálogo",
        "hide",
        "raise",
        "activate",
        "focus",
    ]
    assert window.scraping_refresh_pending is False
