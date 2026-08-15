import sys
import threading

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from database.db_manager import DBManager
from gui.main_window import MainWindow
from services.catalog_bootstrap_service import CatalogBootstrapService

app = QApplication(sys.argv)

window = MainWindow()
window.show()


def catalog_requires_bootstrap() -> bool:
    """Indica si todavía no existe un catálogo inicial persistente."""
    db = DBManager()
    try:
        initialized = db.fetch_all(
            "SELECT value FROM catalog_metadata WHERE key=?",
            ("initialized",),
        )
        if initialized and initialized[0]["value"] == "1":
            return False

        rows = db.fetch_all("SELECT COUNT(*) AS total FROM products")
        return not rows or int(rows[0]["total"]) == 0
    finally:
        db.close()


def start_initial_catalog_bootstrap() -> None:
    """Carga el catálogo inicial sin bloquear la interfaz gráfica."""
    if not catalog_requires_bootstrap():
        window.refresh_catalog()
        return

    window.scraping_scheduler.stop()
    state: dict[str, object] = {
        "finished": False,
        "error": None,
        "result": None,
    }

    def bootstrap() -> None:
        try:
            service = CatalogBootstrapService()
            state["result"] = service.bootstrap()
        except Exception as error:  # noqa: BLE001
            state["error"] = str(error)
        finally:
            state["finished"] = True

    threading.Thread(
        target=bootstrap,
        name="catalog-bootstrap",
        daemon=True,
    ).start()

    poll_timer = QTimer(window)
    poll_timer.setInterval(250)

    def check_bootstrap() -> None:
        if not state["finished"]:
            return

        poll_timer.stop()
        error = state["error"]
        if error:
            window.product_counter.setText("No se pudo cargar el catálogo inicial")
            QMessageBox.warning(
                window,
                "Carga inicial del catálogo",
                "No fue posible crear el catálogo inicial.\n\n"
                f"Detalle: {error}",
            )
        else:
            window.refresh_catalog()
            window.start_scraping_scheduler()

    poll_timer.timeout.connect(check_bootstrap)
    poll_timer.start()


QTimer.singleShot(0, start_initial_catalog_bootstrap)

sys.exit(app.exec())
