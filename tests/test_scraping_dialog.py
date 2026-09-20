from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from gui.main_window import MainWindow
from gui.scraping_dialog import ScrapingDialog
from services.scraping.scraping_session import ScrapingSessionResult


def _qapp():
    return QApplication.instance() or QApplication([])


def _result(*, success: bool = True) -> ScrapingSessionResult:
    result = ScrapingSessionResult(
        processed=2,
        created=0,
        updated=0,
        unchanged=2,
        categories_processed=1,
        expected_category_occurrences=2,
        products_found=2,
        products_unique=2,
        products_multiple_categories=0,
        category_occurrence_gap=0,
        coverage_complete=True,
        errors=[] if success else ["error"],
    )
    return result


def test_scraping_dialog_shows_session_result_without_attribute_error(monkeypatch):
    _qapp()
    dialog = ScrapingDialog()
    shown = {}

    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args: shown.setdefault("message", args[2]),
    )

    dialog.show_result(_result())

    assert "Estado: COMPLETADA" in shown["message"]
    assert "Categorías: 1" in shown["message"]
    assert "Apariciones esperadas por categorías: 2" in shown["message"]
    assert "Brecha por categorías: 0" in shown["message"]

    dialog.close()


def test_scraping_dialog_remains_visible_as_independent_window(monkeypatch):
    app = _qapp()
    main_window = QWidget()
    dialog = ScrapingDialog()
    main_window.show()
    dialog.show()

    assert dialog.parentWidget() is None
    assert dialog.windowFlags() & Qt.WindowType.Window

    monkeypatch.setattr(
        "PySide6.QtCore.QThread.start",
        lambda self: None,
    )

    dialog.start_scraping()
    app.processEvents()

    assert dialog.isVisible()
    assert main_window.isVisible()

    dialog.close()
    main_window.close()
    app.processEvents()


def test_main_window_creates_scraping_as_independent_window(monkeypatch):
    created = []

    class FakeSignal:
        def connect(self, callback):
            del callback

    class FakeDialog:
        finished_success = FakeSignal()
        finished = FakeSignal()

        def setModal(self, value):
            del value

        def show(self):
            pass

        def raise_(self):
            pass

        def activateWindow(self):
            pass

    def factory(*args):
        created.append(args)
        return FakeDialog()

    monkeypatch.setattr("gui.main_window.ScrapingDialog", factory)

    window = MainWindow.__new__(MainWindow)
    window.scraping_dialog = None

    MainWindow.open_scraping(window)

    assert created == [()]
    assert isinstance(window.scraping_dialog, FakeDialog)

def _main_window(monkeypatch, scheduled=None):
    _qapp()

    class FakeProductTable(QWidget):
        def __init__(self, controller):
            super().__init__()
            del controller

    class FakeTimer:
        @staticmethod
        def singleShot(delay, callback):
            if scheduled is not None:
                scheduled.append((delay, callback))

    monkeypatch.setattr(
        "gui.main_window.ProductController",
        lambda: object(),
    )
    monkeypatch.setattr("gui.main_window.ProductTable", FakeProductTable)
    monkeypatch.setattr("gui.main_window.QTimer", FakeTimer)

    return MainWindow()


def test_main_window_defers_initial_catalog_load_until_event_loop(monkeypatch):
    scheduled = []
    window = _main_window(monkeypatch, scheduled)

    assert window.product_counter.text() == "Cargando catálogo..."
    assert len(scheduled) == 1
    delay, callback = scheduled[0]
    assert delay == 0
    assert callback.__self__ is window
    assert callback.__func__ is MainWindow._load_initial_catalog

    window.close()
    _qapp().processEvents()


def test_main_window_refreshes_catalog_and_history_after_success(monkeypatch):
    window = _main_window(monkeypatch)

    calls = []

    def refresh_catalog():
        calls.append("catalog")

    class FakeHistory:
        def __init__(self):
            self.load_count = 0

        def load_history(self):
            self.load_count += 1

        def close(self):
            pass

    class FakeScrapingDialog:
        def __init__(self):
            self.window_title = None

        def setWindowTitle(self, title):
            self.window_title = title

        def raise_(self):
            pass

        def activateWindow(self):
            pass

        def close(self):
            pass

    history = FakeHistory()
    scraping_dialog = FakeScrapingDialog()

    window.refresh_catalog = refresh_catalog
    window.history_dialog = history
    window.scraping_dialog = scraping_dialog

    window.scraping_finished()

    assert calls == ["catalog"]
    assert history.load_count == 1
    assert scraping_dialog.window_title == "Actualización completada"
    assert window.windowTitle() == "Actualización completada"

    window.close()
    _qapp().processEvents()


def test_main_window_reuses_open_history_window(monkeypatch):
    window = _main_window(monkeypatch)

    class FakeHistory:
        def __init__(self):
            self.load_count = 0
            self.normalized = 0
            self.raised = 0
            self.activated = 0
            self.closed = 0

        def load_history(self):
            self.load_count += 1

        def isMinimized(self):
            return True

        def showNormal(self):
            self.normalized += 1

        def raise_(self):
            self.raised += 1

        def activateWindow(self):
            self.activated += 1

        def close(self):
            self.closed += 1

    history = FakeHistory()
    window.history_dialog = history

    window.open_scraping_history()

    assert history.load_count == 1
    assert history.normalized == 1
    assert history.raised == 1
    assert history.activated == 1

    window.close()
    assert history.closed == 1
    _qapp().processEvents()
