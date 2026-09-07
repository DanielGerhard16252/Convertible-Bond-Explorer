import sys
from pathlib import Path

from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication


def load_app_environment() -> None:
    source_root = Path(__file__).resolve().parents[1]
    bundle_root = Path(getattr(sys, "_MEIPASS", source_root))
    load_dotenv(bundle_root / ".env")


load_app_environment()

from desktop.main_window import MainWindow  # noqa: E402


def main() -> None:
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
