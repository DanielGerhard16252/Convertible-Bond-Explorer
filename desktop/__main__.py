import sys
from PySide6.QtWidgets import QApplication

from shared.config import load_app_environment


def main() -> None:
    load_app_environment()
    from desktop.main_window import MainWindow

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
