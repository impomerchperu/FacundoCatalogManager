import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from config.runtime_paths import get_bundle_root
from gui.main_window import MainWindow


APP_ICON_PATH = get_bundle_root() / "resources" / "facundo.ico"


def main() -> None:
    app = QApplication(sys.argv)

    if APP_ICON_PATH.is_file():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH)))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
