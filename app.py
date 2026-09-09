import sys

from PySide6.QtWidgets import QApplication

from database.db_manager import DBManager
from gui.main_window import MainWindow
from services.catalog_bootstrap_service import CatalogBootstrapService

app = QApplication(sys.argv)

# La GUI arranca desde el último scraping completo exitoso ya persistido.
# Esta reconciliación es local, idempotente y no realiza peticiones web.
db = DBManager()
try:
    CatalogBootstrapService(db=db).reconcile_latest_successful_run()
finally:
    db.close()

window = MainWindow()
window.show()

sys.exit(app.exec())
