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
