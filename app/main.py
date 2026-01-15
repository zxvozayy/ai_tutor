# app/main.py
"""
AI Language Tutor - Main Entry Point
Handles login and initializes the application.
"""

import sys
from PySide6 import QtWidgets

from app.engines.gemini_engine import GeminiEngine
from app.ui.main_window import MainWindow
from app.ui.login_dialog import LoginDialog


def run_app():
    """Initialize and run the application."""
    app = QtWidgets.QApplication(sys.argv)

    # 1. Show login dialog first
    login_dialog = LoginDialog()
    if login_dialog.exec() != QtWidgets.QDialog.Accepted:
        # User cancelled login or failed authentication
        sys.exit(0)

    # 2. Initialize AI engine (after successful login)
    try:
        engine = GeminiEngine()
        print("✅ AI Engine initialized successfully")
    except ValueError as e:
        # Missing API keys
        QtWidgets.QMessageBox.critical(
            None,
            "Configuration Error",
            f"{e}\n\n"
            "Please add one of these to your .env file:\n"
            "• GEMINI_API_KEY (from https://aistudio.google.com)\n"
            "• GROQ_API_KEY (from https://console.groq.com)\n\n"
            "Groq is recommended - it's free and has higher limits!"
        )
        sys.exit(1)
    except Exception as e:
        QtWidgets.QMessageBox.critical(
            None,
            "Initialization Error",
            f"Failed to initialize AI engine:\n{e}"
        )
        sys.exit(1)

    # 3. Create and show main window
    main_window = MainWindow(engine)
    main_window.show()

    # 4. Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()