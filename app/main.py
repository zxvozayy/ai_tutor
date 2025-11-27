# app/main.py
import sys
from PySide6 import QtWidgets
from app.ui.main_window import MainWindow
from app.ui.login_dialog import LoginDialog
from app.engines.gemini_engine import GeminiEngine
# app/__init__.py
from dotenv import load_dotenv, find_dotenv
# Prefer the current working directory first; fall back to walking up
path = find_dotenv(usecwd=True) or find_dotenv()
load_dotenv(path)

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
