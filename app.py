import sys

from PySide6.QtWidgets import QApplication

from database.db_manager import DBManager
from gui.main_window import MainWindow
from services.catalog_bootstrap_service import CatalogBootstrapService

app = QApplication(sys.argv)

# La GUI arranca desde la mejor fuente local disponible:
# 1) último scraping FULL exitoso con cobertura completa;
# 2) historial persistido de cambios, si no existe un run completo utilizable.
db = DBManager()
try:
    CatalogBootstrapService(db=db).bootstrap()
finally:
    db.close()

window = MainWindow()
window.show()

sys.exit(app.exec())
