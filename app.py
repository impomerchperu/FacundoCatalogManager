import sys

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from services.catalog_bootstrap_service import CatalogBootstrapService

app = QApplication(sys.argv)

# La GUI nunca depende del scraper para arrancar. Si una base existente perdió
# la tabla products pero conserva el historial de cambios descargados, se
# reconstruye localmente una sola vez antes de mostrar la ventana.
CatalogBootstrapService().restore_from_change_history()

window = MainWindow()
window.show()

sys.exit(app.exec())
