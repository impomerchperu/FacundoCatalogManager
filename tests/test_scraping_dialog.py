from PySide6.QtWidgets import QApplication, QWidget

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


def test_scraping_dialog_shows_session_result_without_attribute_error():
    _qapp()
    dialog = ScrapingDialog()
    dialog.show_result(_result())

    assert "Estado: COMPLETADA" in dialog.summary_label.text()
    assert "Categorías: 1" in dialog.summary_label.text()
    assert "Esperadas: 2" in dialog.summary_label.text()
    assert "Brecha: 0" in dialog.summary_label.text()

    dialog.close()


def test_scraping_dialog_hides_during_running_scraping(monkeypatch):
    app = _qapp()
    main_window = QWidget()
    dialog = ScrapingDialog(main_window)
    main_window.show()
    dialog.show()

    monkeypatch.setattr(
        "PySide6.QtCore.QThread.start",
        lambda self: None,
    )

    dialog.start_scraping()
    app.processEvents()

    assert not dialog.isVisible()
    assert main_window.isVisible()

    dialog.close()
    main_window.close()
    app.processEvents()

def test_scraping_dialog_reports_category_and_enrichment_progress():
    _qapp()
    dialog = ScrapingDialog()
    dialog.elapsed_timer.start()

    dialog.update_progress(1, 48)
    assert dialog.progress.value() == 2
    assert "Recorrido de categorías: 1/24" in dialog.status_label.text()
    assert "2%" in dialog.status_label.text()

    dialog.update_progress(24, 48)
    assert dialog.progress.value() == 50
    assert "24/24" in dialog.status_label.text()
    assert "preparando enriquecimiento" in dialog.status_label.text()

    dialog.update_progress(25, 48)
    assert dialog.progress.value() == 52
    assert "Enriquecimiento: 1/24" in dialog.status_label.text()

    dialog.update_progress(47, 48)
    assert dialog.progress.value() == 97
    assert "Enriquecimiento: 23/24" in dialog.status_label.text()

    dialog.close()
