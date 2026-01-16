# app/ui/login_dialog.py
from PySide6 import QtWidgets, QtGui, QtCore
from app.services.db_supabase import sign_in, sign_up, load_session_if_any


class LoginDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sign in")
        self.setModal(True)
        self.setFixedSize(420, 520)

        # Login window icon
        self.setWindowIcon(QtGui.QIcon("app/resources/images/ai_tutor_icon.png"))

        self._apply_style()

        # -------- Outer layout (center card) --------
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(0)

        # Card frame
        self.card = QtWidgets.QFrame()
        self.card.setObjectName("Card")
        card_layout = QtWidgets.QVBoxLayout(self.card)
        card_layout.setContentsMargins(26, 26, 26, 26)
        card_layout.setSpacing(10)

        outer.addWidget(self.card)

        # -------- Header (logo + title) --------
        logo = QtWidgets.QLabel()
        logo.setObjectName("Logo")
        logo.setAlignment(QtCore.Qt.AlignCenter)
        logo.setFixedHeight(88)
        logo.setContentsMargins(0, 6, 0, 6)

        pix = QtGui.QPixmap("app/resources/images/ai_tutor_icon.png")
        if not pix.isNull():
            pix = pix.scaled(60, 60, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            logo.setPixmap(pix)
        else:
            logo.setText("AI Tutor")

        title = QtWidgets.QLabel("Welcome back")
        title.setObjectName("Title")
        title.setAlignment(QtCore.Qt.AlignCenter)

        subtitle = QtWidgets.QLabel("Sign in to continue.")
        subtitle.setObjectName("Subtitle")
        subtitle.setAlignment(QtCore.Qt.AlignCenter)

        card_layout.addWidget(logo)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)

        # -------- Form fields --------
        self.email = QtWidgets.QLineEdit()
        self.email.setPlaceholderText("Email")
        self.email.setObjectName("Input")
        self.email.setClearButtonEnabled(True)

        self.password = QtWidgets.QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setObjectName("Input")
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)

        card_layout.addWidget(self.email)
        card_layout.addWidget(self.password)

        # -------- Options row --------
        options_row = QtWidgets.QHBoxLayout()
        options_row.setContentsMargins(0, 0, 0, 0)
        options_row.setSpacing(10)

        self.signup_chk = QtWidgets.QCheckBox("Create new account")
        self.signup_chk.setObjectName("Check")

        options_row.addWidget(self.signup_chk)
        options_row.addStretch(1)
        card_layout.addLayout(options_row)

        # -------- Status label --------
        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("Status")
        self.status.setWordWrap(True)
        self.status.setAlignment(QtCore.Qt.AlignCenter)
        card_layout.addWidget(self.status)

        # Button spacing
        card_layout.addSpacing(4)

        # -------- Button --------
        self.btn = QtWidgets.QPushButton("Continue")
        self.btn.setObjectName("PrimaryBtn")
        self.btn.setDefault(True)
        self.btn.clicked.connect(self._continue)
        card_layout.addWidget(self.btn)

        # Enter key triggers login
        self.email.returnPressed.connect(self._continue)
        self.password.returnPressed.connect(self._continue)

        # Try silent session restore
        if load_session_if_any():
            self.accept()

    def _apply_style(self):
        self.setStyleSheet("""
        QDialog {
            background: #f0f7f4;
            color: #184e77;
            font-family: "Segoe UI";
            font-size: 14px;
        }

        QFrame#Card {
            background: #ffffff;
            border: 1px solid #b5e48c;
            border-radius: 18px;
        }

        QLabel#Title {
            font-size: 22px;
            font-weight: 800;
            color: #184e77;
            margin-top: 6px;
        }

        QLabel#Subtitle {
            color: #34a0a4;
            margin-bottom: 6px;
        }

        QLineEdit#Input {
            background: #ffffff;
            border: 1px solid #b5e48c;
            border-radius: 12px;
            padding: 10px 12px;
            min-height: 40px;
            color: #184e77;
        }

        QLineEdit#Input:focus {
            border: 1px solid #168aad;
        }

        QCheckBox#Check {
            color: #184e77;
            spacing: 10px;
        }

        QLabel#Status {
            color: #e74c3c;
            min-height: 18px;
            padding-top: 2px;
        }

        QPushButton#PrimaryBtn {
            background: #52b69a;
            color: #184e77;
            border: none;
            border-radius: 12px;
            padding: 10px;
            min-height: 42px;
            font-weight: 800;
        }

        QPushButton#PrimaryBtn:hover {
            background: #34a0a4;
        }

        QPushButton#PrimaryBtn:pressed {
            background: #168aad;
        }

        QPushButton#PrimaryBtn:disabled {
            background: rgba(82,182,154,0.45);
            color: rgba(24,78,119,0.55);
        }
        """)

    def _continue(self):
        e = self.email.text().strip()
        p = self.password.text().strip()

        if not e or not p:
            self.status.setText("Please enter both email and password.")
            return

        self.btn.setEnabled(False)
        self.status.setText("")

        try:
            if self.signup_chk.isChecked():
                # Create new account
                sign_up(e, p)
                try:
                    # Try to sign in immediately
                    sign_in(e, p)
                    self.accept()
                except Exception:
                    # If sign-in fails, user may need to confirm email
                    self.status.setText("Account created. Please confirm your email, then sign in.")
                    self.btn.setEnabled(True)
                return

            # Regular sign in
            sign_in(e, p)
            self.accept()

        except Exception as ex:
            self.status.setText(f"Auth error: {ex}")
            self.btn.setEnabled(True)
        finally:
            # Re-enable button if not already accepted
            if not self.result():
                self.btn.setEnabled(True)