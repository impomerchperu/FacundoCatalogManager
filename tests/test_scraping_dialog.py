from PySide6.QtWidgets import QApplication, QMessageBox

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
