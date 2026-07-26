from PySide6.QtWidgets import QMainWindow, QLabel


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Facundo Catalog Manager"
        )

        self.resize(900, 600)

        etiqueta = QLabel(
            "Sistema de gestión de catálogos"
        )

        self.setCentralWidget(etiqueta)