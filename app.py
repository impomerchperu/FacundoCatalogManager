import sys

from PySide6.QtWidgets import QApplication

from database.db_manager import DBManager
from gui.main_window import MainWindow
from services.catalog_bootstrap_service import CatalogBootstrapService

app = QApplication(sys.argv)

# La base de datos local es la fuente permanente del catálogo.
# La recuperación histórica solo se ejecuta una vez como reparación de una
# instalación existente; después, cada scraping actualiza la misma catalog.db
# y la GUI simplemente carga ese catálogo persistido.
db = DBManager()
try:
    CatalogBootstrapService(db=db).bootstrap()
finally:
    db.close()

window = MainWindow()
window.show()

sys.exit(app.exec())
