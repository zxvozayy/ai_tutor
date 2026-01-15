# app/main.py

import sys

# ✅ Load .env BEFORE importing anything that reads env vars
from dotenv import load_dotenv, find_dotenv
path = find_dotenv(usecwd=True) or find_dotenv()
load_dotenv(path, override=True)

from PySide6 import QtWidgets
from app.ui.main_window import MainWindow
from app.ui.login_dialog import LoginDialog
from app.engines.gemini_engine import GeminiEngine


def run_app():
    app = QtWidgets.QApplication(sys.argv)

    # Auth first
    dlg = LoginDialog()
    if dlg.exec() != QtWidgets.QDialog.Accepted:
        return

    engine = GeminiEngine()
    w = MainWindow(engine)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()