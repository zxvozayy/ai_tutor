# app/ui/login_dialog.py
from PySide6 import QtWidgets
from app.services.db_supabase import sign_in, sign_up, load_session_if_any

class LoginDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sign in")
        self.setModal(True)

        self.email = QtWidgets.QLineEdit()
        self.email.setPlaceholderText("Email")

        self.password = QtWidgets.QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)

        self.signup_chk = QtWidgets.QCheckBox("Create new account")
        self.status = QtWidgets.QLabel("")

        btn = QtWidgets.QPushButton("Continue")
        btn.clicked.connect(self._continue)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.email)
        layout.addWidget(self.password)
        layout.addWidget(self.signup_chk)
        layout.addWidget(btn)
        layout.addWidget(self.status)

        # try silent restore
        if load_session_if_any():
            self.accept()

    def _continue(self):
        e = self.email.text().strip()
        p = self.password.text().strip()
        try:
            if self.signup_chk.isChecked():
                sign_up(e, p)  # may require email confirm depending on project settings
            sign_in(e, p)      # sets session + postgrest auth
            self.accept()
        except Exception as ex:
            self.status.setText(f"Auth error: {ex}")
